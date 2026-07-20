"""Site-scoped consumption, tariff, and budget calculations."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import chain
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import EnergyBudget, Meter, Site, SiteSettings, SmartMeterReading


MAX_POWER_GAP_SECONDS = 2 * 60 * 60
PERIOD_ALIASES = {"day": "today", "week": "7d"}
PERIODS = {"live", "today", "7d", "month", "year", "all", "custom"}


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
    def _readings_for_user(
        db: Session, user_id: int, before: datetime | None = None, site_id: int | None = None,
    ):
        query = (
            db.query(SmartMeterReading, Meter)
            .join(Meter, SmartMeterReading.meter_id == Meter.id)
            .join(Site, Meter.site_id == Site.id)
            .filter(Site.user_id == user_id, Meter.is_primary.is_(True))
        )
        if before is not None:
            query = query.filter(SmartMeterReading.timestamp < before)
        if site_id is not None:
            query = query.filter(Site.id == site_id)
        return query.order_by(Meter.id, SmartMeterReading.timestamp).all()

    @staticmethod
    def _primary_readings_query(db: Session, user_id: int):
        return (
            db.query(SmartMeterReading)
            .join(Meter, SmartMeterReading.meter_id == Meter.id)
            .join(Site, Meter.site_id == Site.id)
            .filter(Site.user_id == user_id, Meter.is_primary.is_(True))
        )

    @staticmethod
    def _zone_for_site(site: Site) -> ZoneInfo:
        try:
            return ZoneInfo(site.timezone)
        except (KeyError, ValueError):
            return ZoneInfo("UTC")

    def _period_bounds(
        self,
        db: Session,
        user_id: int,
        timeframe: str,
        start: datetime | None,
        end: datetime | None,
        now: datetime,
    ) -> tuple[str, Site, ZoneInfo, datetime, datetime]:
        timeframe = PERIOD_ALIASES.get(timeframe, timeframe)
        if timeframe not in PERIODS:
            raise ValueError("timeframe must be live, today, 7d, month, year, all, or custom")
        site = db.query(Site).filter(Site.user_id == user_id).one_or_none()
        if site is None:
            raise ValueError("No site is configured")
        zone = self._zone_for_site(site)
        now_utc = _as_utc(now)
        local_now = now_utc.astimezone(zone)

        if timeframe == "custom":
            if start is None or end is None:
                raise ValueError("custom timeframe requires start and end")
            if start.tzinfo is None or end.tzinfo is None:
                raise ValueError("custom start and end must include a timezone offset")
            period_start, period_end = _as_utc(start), _as_utc(end)
            if period_end <= period_start:
                raise ValueError("custom end must be after start")
            if period_end - period_start > timedelta(days=366 * 5):
                raise ValueError("custom range cannot exceed 5 years")
        elif timeframe == "live":
            period_start, period_end = now_utc - timedelta(minutes=15), now_utc
        elif timeframe == "today":
            period_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
            period_end = now_utc
        elif timeframe == "7d":
            local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
            period_start, period_end = local_start.astimezone(timezone.utc), now_utc
        elif timeframe == "month":
            period_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
            period_end = now_utc
        elif timeframe == "year":
            period_start = local_now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
            period_end = now_utc
        else:
            first_timestamp = self._primary_readings_query(db, user_id).with_entities(
                func.min(SmartMeterReading.timestamp)
            ).scalar()
            period_start = _as_utc(first_timestamp) if first_timestamp else now_utc
            last_timestamp = self._primary_readings_query(db, user_id).with_entities(
                func.max(SmartMeterReading.timestamp)
            ).scalar()
            period_end = max(period_start, _as_utc(last_timestamp)) if last_timestamp else now_utc
        return timeframe, site, zone, period_start, period_end

    @staticmethod
    def _granularity(period_start: datetime, period_end: datetime) -> tuple[str, int]:
        seconds = max(0, (period_end - period_start).total_seconds())
        if seconds <= 2 * 3600:
            return "minute", 60
        if seconds <= 2 * 86400:
            return "15_minutes", 15 * 60
        if seconds <= 14 * 86400:
            return "hour", 3600
        if seconds <= 90 * 86400:
            return "day", 86400
        if seconds <= 2 * 366 * 86400:
            return "week", 7 * 86400
        return "month", 30 * 86400

    @staticmethod
    def _bucket_timestamp(timestamp: datetime, period_start: datetime, bucket_seconds: int) -> datetime:
        offset = max(0, (_as_utc(timestamp) - period_start).total_seconds())
        return period_start + timedelta(seconds=int(offset // bucket_seconds) * bucket_seconds)

    def get_period_summary(
        self,
        db: Session,
        user_id: int,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        now: datetime | None = None,
    ) -> dict:
        now_utc = _as_utc(now or datetime.now(timezone.utc))
        timeframe, site, zone, period_start, period_end = self._period_bounds(
            db, user_id, timeframe, start, end, now_utc
        )
        meter = (
            db.query(Meter)
            .filter(Meter.site_id == site.id, Meter.is_primary.is_(True))
            .one_or_none()
        )
        granularity, bucket_seconds = self._granularity(period_start, period_end)
        if meter is None:
            return self._empty_period(timeframe, site, period_start, period_end, granularity)

        base_query = self._primary_readings_query(db, user_id)
        settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).one_or_none()
        previous = base_query.filter(SmartMeterReading.timestamp < period_start).order_by(
            SmartMeterReading.timestamp.desc()
        ).first()
        in_period = base_query.filter(
            SmartMeterReading.timestamp >= period_start,
            SmartMeterReading.timestamp <= period_end,
        ).order_by(SmartMeterReading.timestamp.asc())
        following = base_query.filter(SmartMeterReading.timestamp > period_end).order_by(
            SmartMeterReading.timestamp.asc()
        ).first()

        buckets: dict[datetime, dict] = defaultdict(
            lambda: {"sum_kw": 0.0, "count": 0, "min_kw": None, "max_kw": None, "energy_kwh": 0.0}
        )
        source_counts: dict[str, int] = defaultdict(int)
        records = chain(([previous] if previous else []), in_period.yield_per(1000), ([following] if following else []))
        last_reading = None
        total_kwh = 0.0
        covered_seconds = 0.0
        peak_kw = 0.0
        peak_at = None
        tariff_totals = {
            "total_kwh": 0.0, "total_cost": 0.0, "peak_kwh": 0.0,
            "off_peak_kwh": 0.0, "daily": defaultdict(lambda: {"kwh": 0.0, "cost": 0.0}),
        }

        for reading in records:
            timestamp = _as_utc(reading.timestamp)
            if period_start <= timestamp <= period_end:
                bucket = buckets[self._bucket_timestamp(timestamp, period_start, bucket_seconds)]
                bucket["sum_kw"] += reading.gap
                bucket["count"] += 1
                bucket["min_kw"] = reading.gap if bucket["min_kw"] is None else min(bucket["min_kw"], reading.gap)
                bucket["max_kw"] = reading.gap if bucket["max_kw"] is None else max(bucket["max_kw"], reading.gap)
                source_counts[reading.source] += 1
                if reading.gap >= peak_kw:
                    peak_kw = reading.gap
                    peak_at = timestamp

            if last_reading is not None:
                interval_start, interval_end = _as_utc(last_reading.timestamp), timestamp
                elapsed = (interval_end - interval_start).total_seconds()
                clipped_start, clipped_end = max(interval_start, period_start), min(interval_end, period_end)
                clipped_seconds = (clipped_end - clipped_start).total_seconds()
                if elapsed > 0 and clipped_seconds > 0:
                    direct_energy = None
                    if last_reading.energy_kwh is not None and reading.energy_kwh is not None:
                        difference = reading.energy_kwh - last_reading.energy_kwh
                        if difference >= 0:
                            direct_energy = difference
                    if direct_energy is not None or elapsed <= MAX_POWER_GAP_SECONDS:
                        interval_energy = direct_energy if direct_energy is not None else (
                            (last_reading.gap + reading.gap) / 2 * elapsed / 3600
                        )
                        clipped_energy = interval_energy * clipped_seconds / elapsed
                        total_kwh += clipped_energy
                        covered_seconds += clipped_seconds
                        if settings is not None:
                            self._add_interval(
                                tariff_totals, clipped_start, clipped_end, clipped_energy, settings, zone
                            )
                        energy_bucket = buckets[self._bucket_timestamp(clipped_start, period_start, bucket_seconds)]
                        energy_bucket["energy_kwh"] += clipped_energy
            last_reading = reading

        latest = base_query.order_by(SmartMeterReading.timestamp.desc()).first()
        freshness = self._freshness(latest, meter, now_utc)
        duration_seconds = max(0.0, (period_end - period_start).total_seconds())
        points = [
            {
                "timestamp": timestamp.isoformat(),
                "average_kw": round(values["sum_kw"] / values["count"], 4) if values["count"] else 0.0,
                "min_kw": round(values["min_kw"], 4) if values["min_kw"] is not None else None,
                "max_kw": round(values["max_kw"], 4) if values["max_kw"] is not None else None,
                "energy_kwh": round(values["energy_kwh"], 5),
                "sample_count": values["count"],
            }
            for timestamp, values in sorted(buckets.items())
        ]
        sample_count = sum(source_counts.values())
        return {
            "timeframe": timeframe,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "site_name": site.name,
            "timezone": site.timezone,
            "granularity": granularity,
            "total_kwh": round(total_kwh, 4),
            "estimated_cost": round(tariff_totals["total_cost"], 2),
            "currency": settings.currency if settings else "MAD",
            "average_kw": round(total_kwh / (covered_seconds / 3600), 4) if covered_seconds else 0.0,
            "peak_kw": round(peak_kw, 4),
            "peak_at": peak_at.isoformat() if peak_at else None,
            "coverage_pct": round(min(100.0, covered_seconds / duration_seconds * 100), 1) if duration_seconds else 0.0,
            "sample_count": sample_count,
            "sources": [{"source": source, "count": count} for source, count in sorted(source_counts.items())],
            "freshness": freshness,
            "points": points,
        }

    @staticmethod
    def _freshness(reading: SmartMeterReading | None, meter: Meter, now: datetime) -> dict:
        expected = meter.expected_interval_seconds or 60
        if reading is None:
            return {
                "status": "empty", "age_seconds": None, "expected_interval_seconds": expected,
                "last_seen_at": None, "source": None, "quality": None,
            }
        timestamp = _as_utc(reading.timestamp)
        age = int(max(0, (now - timestamp).total_seconds()))
        if reading.source == "csv":
            status = "historical"
        else:
            status = "fresh" if age <= max(expected * 3, 300) else "stale"
        return {
            "status": status,
            "age_seconds": age,
            "expected_interval_seconds": expected,
            "last_seen_at": timestamp.isoformat(),
            "source": reading.source,
            "quality": reading.quality,
        }

    @staticmethod
    def _empty_period(timeframe: str, site: Site, start: datetime, end: datetime, granularity: str) -> dict:
        return {
            "timeframe": timeframe, "period_start": start.isoformat(), "period_end": end.isoformat(),
            "site_name": site.name, "timezone": site.timezone, "granularity": granularity, "total_kwh": 0.0,
            "estimated_cost": 0.0, "currency": "MAD", "average_kw": 0.0, "peak_kw": 0.0, "peak_at": None,
            "coverage_pct": 0.0, "sample_count": 0, "sources": [],
            "freshness": {"status": "empty", "age_seconds": None, "expected_interval_seconds": None,
                          "last_seen_at": None, "source": None, "quality": None},
            "points": [],
        }

    @staticmethod
    def _settings_for_user(db: Session, user_id: int, site_id: int | None = None) -> dict[int, SiteSettings]:
        query = (
            db.query(SiteSettings)
            .join(Site, SiteSettings.site_id == Site.id)
            .filter(Site.user_id == user_id)
        )
        if site_id is not None:
            query = query.filter(Site.id == site_id)
        return {
            settings.site_id: settings
            for settings in query.all()
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

    def _month_calculation(self, db: Session, user_id: int, month: str, site_id: int | None = None) -> dict:
        settings_by_site = self._settings_for_user(db, user_id, site_id)
        if not settings_by_site:
            return self._empty_month(month)
        default_settings = next(iter(settings_by_site.values()))
        site_windows: dict[int, tuple[ZoneInfo, datetime, datetime]] = {}
        for settings_site_id, settings in settings_by_site.items():
            try:
                zone = ZoneInfo(settings.site.timezone if settings.site else "UTC")
            except Exception:
                zone = ZoneInfo("UTC")
            start_local, end_local = _month_bounds(month, zone)
            site_windows[settings_site_id] = (zone, start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc))
        records = self._readings_for_user(db, user_id, site_id=site_id)
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
        possible_seconds = 0.0
        meter_count = 0
        for readings in by_meter.values():
            if not readings:
                continue
            meter_count += 1
            meter_settings = settings_by_site.get(readings[0][1].site_id, default_settings)
            zone, start, end = site_windows[meter_settings.site_id]
            possible_seconds += max(0.0, (min(datetime.now(timezone.utc), end) - start).total_seconds())
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
                self._add_interval(totals, clipped_start, clipped_end, clipped_energy, meter_settings, zone)
                totals["covered_seconds"] += clipped_seconds
                totals["peak_kw"] = max(totals["peak_kw"], previous.gap, current.gap)

        try:
            default_zone = ZoneInfo(default_settings.site.timezone if default_settings.site else "UTC")
        except Exception:
            default_zone = ZoneInfo("UTC")
        default_start, default_end = _month_bounds(month, default_zone)
        period_end = min(datetime.now(default_zone), default_end)
        days_elapsed = max(1, (period_end.date() - default_start.date()).days + 1)
        days_in_month = (default_end.date() - default_start.date()).days
        budget_query = db.query(EnergyBudget).filter(EnergyBudget.user_id == user_id)
        budget = budget_query.filter(EnergyBudget.site_id == site_id).first() if site_id is not None else budget_query.first()
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
            "coverage_pct": round(min(100.0, totals["covered_seconds"] / possible_seconds * 100) if possible_seconds and meter_count else 0.0, 1),
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

    def get_monthly_summary(
        self, db: Session, user_id: int, month: str | None = None, site_id: int | None = None,
    ) -> dict:
        site = db.query(Site).filter(Site.user_id == user_id).one_or_none()
        now = datetime.now(timezone.utc)
        selected_month = month or (
            now.astimezone(self._zone_for_site(site)).strftime("%Y-%m") if site else now.strftime("%Y-%m")
        )
        current = self._month_calculation(db, user_id, selected_month, site_id)
        year, month_number = (int(part) for part in selected_month.split("-"))
        previous_month = f"{year - 1}-12" if month_number == 1 else f"{year}-{month_number - 1:02d}"
        previous = self._month_calculation(db, user_id, previous_month, site_id)
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
        reading = self._primary_readings_query(db, user_id).order_by(
            SmartMeterReading.timestamp.desc()
        ).first()
        if not reading:
            return {"kw": 0, "status": "empty", "source": None, "age_seconds": None}
        timestamp = _as_utc(reading.timestamp)
        return {
            "kw": reading.gap,
            "status": "normal" if reading.gap < 4.0 else "high",
            "voltage": reading.voltage,
            "intensity": reading.intensity,
            "sub_metering_1": reading.sub_metering_1,
            "sub_metering_2": reading.sub_metering_2,
            "sub_metering_3": reading.sub_metering_3,
            "timestamp": timestamp.isoformat(),
            "source": reading.source,
            "age_seconds": int(max(0, (datetime.now(timezone.utc) - timestamp).total_seconds())),
        }

    def get_history(self, db: Session, user_id: int, hours: int = 24):
        readings = self._primary_readings_query(db, user_id).order_by(
            SmartMeterReading.timestamp.desc()
        ).limit(hours * 60).all()
        return [{"kw": reading.gap, "timestamp": _as_utc(reading.timestamp).isoformat()} for reading in reversed(readings)]

    def get_chart_history(self, db: Session, user_id: int, timeframe: str) -> list[dict]:
        """Compatibility chart shape; new clients should use ``/period``."""
        summary = self.get_period_summary(db, user_id, timeframe)
        return [
            {"kw": point["average_kw"], "timestamp": point["timestamp"]}
            for point in summary["points"]
        ]

    def get_statistics(self, db: Session, user_id: int):
        summary = self.get_monthly_summary(db, user_id)
        return {**summary, "average_daily": summary["average_daily_kwh"], "peak": summary["peak_kw"]}

    def export_month_csv(self, db: Session, user_id: int, month: str | None = None) -> str:
        summary = self.get_monthly_summary(db, user_id, month)
        site = db.query(Site).filter(Site.user_id == user_id).one_or_none()
        settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).one_or_none() if site else None
        zone = self._zone_for_site(site) if site else ZoneInfo("UTC")
        local_start, local_end = _month_bounds(summary["month"], zone)
        period = self.get_period_summary(
            db,
            user_id,
            "custom",
            local_start.astimezone(timezone.utc),
            local_end.astimezone(timezone.utc),
        ) if site else None
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["generated_at_utc", datetime.now(timezone.utc).isoformat()])
        writer.writerow(["site", site.name if site else "Not configured"])
        writer.writerow(["timezone", site.timezone if site else "UTC"])
        writer.writerow(["month", summary["month"]])
        writer.writerow(["currency", settings.currency if settings else "MAD"])
        writer.writerow(["peak_rate_per_kwh", settings.peak_rate if settings else ""])
        writer.writerow(["off_peak_rate_per_kwh", settings.off_peak_rate if settings else ""])
        writer.writerow(["peak_hours", f"{settings.peak_start_hour}:00-{settings.peak_end_hour}:00" if settings else ""])
        writer.writerow(["sources", ";".join(item["source"] for item in period["sources"]) if period else ""])
        writer.writerow(["coverage_percent", summary["coverage_pct"]])
        writer.writerow(["total_kwh", summary["total_kwh"]])
        writer.writerow(["estimated_cost", summary["total_cost"]])
        writer.writerow(["calculation", "Interval-integrated primary-meter energy using configured site tariff"])
        writer.writerow([])
        writer.writerow(["date", "energy_kwh", "estimated_cost", "currency"])
        for day in summary["daily"]:
            writer.writerow([day["date"], day["kwh"], day["cost"], settings.currency if settings else "MAD"])
        return output.getvalue()


consumption_service = ConsumptionService()
