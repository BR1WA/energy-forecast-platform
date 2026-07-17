"""Site-scoped consumption, tariff, and budget calculations."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models import EnergyBudget, Meter, Site, SiteSettings, SmartMeterReading


MAX_POWER_GAP_SECONDS = 2 * 60 * 60


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _month_bounds(month: str, zone: ZoneInfo) -> tuple[datetime, datetime]:
    year, month_number = (int(part) for part in month.split("-"))
    start = datetime(year, month_number, 1, tzinfo=zone)
    end = datetime(year + 1, 1, 1, tzinfo=zone) if month_number == 12 else datetime(year, month_number + 1, 1, tzinfo=zone)
    return start, end


def _is_peak(hour: int, settings: SiteSettings) -> bool:
    if settings.peak_start_hour == settings.peak_end_hour:
        return False
    if settings.peak_start_hour < settings.peak_end_hour:
        return settings.peak_start_hour <= hour < settings.peak_end_hour
    return hour >= settings.peak_start_hour or hour < settings.peak_end_hour


class ConsumptionService:
    @staticmethod
    def _readings_for_user(db: Session, user_id: int, before: datetime | None = None):
        query = (
            db.query(SmartMeterReading, Meter)
            .join(Meter, SmartMeterReading.meter_id == Meter.id)
            .join(Site, Meter.site_id == Site.id)
            .filter(Site.user_id == user_id)
        )
        if before is not None:
            query = query.filter(SmartMeterReading.timestamp < before)
        return query.order_by(Meter.id, SmartMeterReading.timestamp).all()

    @staticmethod
    def _settings_for_user(db: Session, user_id: int) -> dict[int, SiteSettings]:
        return {
            settings.site_id: settings
            for settings in (
                db.query(SiteSettings)
                .join(Site, SiteSettings.site_id == Site.id)
                .filter(Site.user_id == user_id)
                .all()
            )
        }

    def _add_interval(
        self,
        totals: dict,
        start: datetime,
        end: datetime,
        energy_kwh: float,
        settings: SiteSettings,
        zone: ZoneInfo,
    ) -> None:
        if energy_kwh <= 0 or end <= start:
            return
        total_seconds = (end - start).total_seconds()
        cursor = start
        while cursor < end:
            local = cursor.astimezone(zone)
            next_hour = (local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).astimezone(timezone.utc)
            segment_end = min(end, next_hour)
            seconds = (segment_end - cursor).total_seconds()
            segment_kwh = energy_kwh * seconds / total_seconds
            rate = settings.peak_rate if _is_peak(local.hour, settings) else settings.off_peak_rate
            day = local.date().isoformat()
            totals["total_kwh"] += segment_kwh
            totals["total_cost"] += segment_kwh * rate
            totals["peak_kwh" if _is_peak(local.hour, settings) else "off_peak_kwh"] += segment_kwh
            totals["daily"][day]["kwh"] += segment_kwh
            totals["daily"][day]["cost"] += segment_kwh * rate
            cursor = segment_end

    def _month_calculation(self, db: Session, user_id: int, month: str) -> dict:
        settings_by_site = self._settings_for_user(db, user_id)
        if not settings_by_site:
            return self._empty_month(month)
        default_settings = next(iter(settings_by_site.values()))
        try:
            zone = ZoneInfo(default_settings.site.timezone if default_settings.site else "UTC")
        except Exception:
            zone = ZoneInfo("UTC")
        start_local, end_local = _month_bounds(month, zone)
        start, end = start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
        records = self._readings_for_user(db, user_id, before=end)
        by_meter: dict[int, list[tuple[SmartMeterReading, Meter]]] = defaultdict(list)
        for reading, meter in records:
            by_meter[meter.id].append((reading, meter))

        totals = {
            "total_kwh": 0.0,
            "total_cost": 0.0,
            "peak_kwh": 0.0,
            "off_peak_kwh": 0.0,
            "covered_seconds": 0.0,
            "daily": defaultdict(lambda: {"kwh": 0.0, "cost": 0.0}),
            "peak_kw": 0.0,
        }
        for readings in by_meter.values():
            for previous_pair, current_pair in zip(readings, readings[1:]):
                previous, meter = previous_pair
                current, _ = current_pair
                interval_start, interval_end = _as_utc(previous.timestamp), _as_utc(current.timestamp)
                if interval_end <= start or interval_start >= end or interval_end <= interval_start:
                    continue
                elapsed_seconds = (interval_end - interval_start).total_seconds()
                direct_energy = None
                if previous.energy_kwh is not None and current.energy_kwh is not None:
                    difference = current.energy_kwh - previous.energy_kwh
                    if difference >= 0:
                        direct_energy = difference
                if direct_energy is None:
                    if elapsed_seconds > MAX_POWER_GAP_SECONDS:
                        continue
                    interval_energy = ((previous.gap + current.gap) / 2) * elapsed_seconds / 3600
                else:
                    interval_energy = direct_energy

                clipped_start, clipped_end = max(interval_start, start), min(interval_end, end)
                clipped_seconds = (clipped_end - clipped_start).total_seconds()
                clipped_energy = interval_energy * clipped_seconds / elapsed_seconds
                meter_settings = settings_by_site.get(meter.site_id, default_settings)
                self._add_interval(totals, clipped_start, clipped_end, clipped_energy, meter_settings, zone)
                totals["covered_seconds"] += clipped_seconds
                totals["peak_kw"] = max(totals["peak_kw"], previous.gap, current.gap)

        now_local = datetime.now(zone)
        period_end = min(now_local, end_local)
        possible_seconds = max(0.0, (period_end - start_local).total_seconds())
        days_elapsed = max(1, (period_end.date() - start_local.date()).days + 1)
        days_in_month = (end_local.date() - start_local.date()).days
        budget = db.query(EnergyBudget).filter(EnergyBudget.user_id == user_id).first()
        budget_target = budget.monthly_budget_mad if budget else None
        projected_cost = totals["total_cost"] / days_elapsed * days_in_month if totals["total_cost"] else 0.0
        tariff = {
            "currency": default_settings.currency,
            "peak_rate": default_settings.peak_rate,
            "off_peak_rate": default_settings.off_peak_rate,
            "peak_start_hour": default_settings.peak_start_hour,
            "peak_end_hour": default_settings.peak_end_hour,
        }
        return {
            "month": month,
            "total_kwh": round(totals["total_kwh"], 4),
            "total_cost": round(totals["total_cost"], 2),
            "peak_kw": round(totals["peak_kw"], 3),
            "average_daily_kwh": round(totals["total_kwh"] / days_elapsed, 3),
            "days_elapsed": days_elapsed,
            "days_in_month": days_in_month,
            "coverage_pct": round(min(100.0, totals["covered_seconds"] / possible_seconds * 100) if possible_seconds else 0.0, 1),
            "peak_kwh": round(totals["peak_kwh"], 4),
            "off_peak_kwh": round(totals["off_peak_kwh"], 4),
            "daily": [
                {"date": date, "kwh": round(value["kwh"], 4), "cost": round(value["cost"], 2)}
                for date, value in sorted(totals["daily"].items())
            ],
            "tariff": tariff,
            "budget": {
                "target_mad": budget_target,
                "spent_mad": round(totals["total_cost"], 2),
                "remaining_mad": round(max(0.0, budget_target - totals["total_cost"]), 2) if budget_target is not None else None,
                "progress_pct": round(totals["total_cost"] / budget_target * 100, 1) if budget_target and budget_target > 0 else None,
                "projected_mad": round(projected_cost, 2),
            },
        }

    @staticmethod
    def _empty_month(month: str) -> dict:
        return {
            "month": month, "total_kwh": 0.0, "total_cost": 0.0, "peak_kw": 0.0,
            "average_daily_kwh": 0.0, "days_elapsed": 0, "days_in_month": 0,
            "coverage_pct": 0.0, "peak_kwh": 0.0, "off_peak_kwh": 0.0,
            "daily": [], "tariff": {},
            "budget": {"target_mad": None, "spent_mad": 0.0, "remaining_mad": None, "progress_pct": None, "projected_mad": 0.0},
        }

    def get_monthly_summary(self, db: Session, user_id: int, month: str | None = None) -> dict:
        now = datetime.now(timezone.utc)
        selected_month = month or now.strftime("%Y-%m")
        current = self._month_calculation(db, user_id, selected_month)
        year, month_number = (int(part) for part in selected_month.split("-"))
        previous_month = f"{year - 1}-12" if month_number == 1 else f"{year}-{month_number - 1:02d}"
        previous = self._month_calculation(db, user_id, previous_month)
        current["previous_month"] = {
            "month": previous["month"],
            "total_kwh": previous["total_kwh"],
            "total_cost": previous["total_cost"],
        }
        current["comparison_pct"] = (
            round((current["total_kwh"] - previous["total_kwh"]) / previous["total_kwh"] * 100, 1)
            if previous["total_kwh"] else None
        )
        return current

    def get_current_consumption(self, db: Session, user_id: int):
        reading = self._readings_for_user(db, user_id)[-1][0] if self._readings_for_user(db, user_id) else None
        if not reading:
            return {"kw": 0, "status": "empty", "source": None, "age_seconds": None}
        timestamp = _as_utc(reading.timestamp)
        return {
            "kw": reading.gap,
            "status": "normal" if reading.gap < 4.0 else "high",
            "voltage": reading.voltage,
            "intensity": reading.intensity,
            "timestamp": timestamp.isoformat(),
            "source": reading.source,
            "age_seconds": int(max(0, (datetime.now(timezone.utc) - timestamp).total_seconds())),
        }

    def get_history(self, db: Session, user_id: int, hours: int = 24):
        readings = self._readings_for_user(db, user_id)[-hours * 60:]
        return [{"kw": reading.gap, "timestamp": _as_utc(reading.timestamp).isoformat()} for reading, _ in reversed(readings)]

    def get_statistics(self, db: Session, user_id: int):
        summary = self.get_monthly_summary(db, user_id)
        return {**summary, "average_daily": summary["average_daily_kwh"], "peak": summary["peak_kw"]}

    def export_month_csv(self, db: Session, user_id: int, month: str | None = None) -> str:
        summary = self.get_monthly_summary(db, user_id, month)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["month", summary["month"]])
        writer.writerow(["total_kwh", summary["total_kwh"]])
        writer.writerow(["total_cost", summary["total_cost"]])
        writer.writerow([])
        writer.writerow(["date", "energy_kwh", "cost"])
        for day in summary["daily"]:
            writer.writerow([day["date"], day["kwh"], day["cost"]])
        return output.getvalue()


consumption_service = ConsumptionService()
