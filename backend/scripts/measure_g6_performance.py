"""Create a deterministic PostgreSQL fixture and emit Product V1 latency/query evidence."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from time import perf_counter

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Alert, AlertConfig, Forecast, SmartMeterReading, User
from app.routers.analytics import get_summary
from app.routers.forecast import get_forecast_history
from app.services.account_export_service import build_account_archive
from app.services.alert_service import alert_service
from app.services.auth_service import hash_password
from app.services.consumption_service import consumption_service
from app.services.site_service import ensure_default_site, get_default_meter


READING_COUNT = int(os.getenv("G6_BENCHMARK_READINGS", "20000"))
FORECAST_COUNT = int(os.getenv("G6_BENCHMARK_FORECASTS", "600"))
ALERT_COUNT = int(os.getenv("G6_BENCHMARK_ALERTS", "1000"))
REPEATS = int(os.getenv("G6_BENCHMARK_REPEATS", "12"))


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999) - 1))]


def seed(db: Session) -> tuple[User, datetime, datetime]:
    user = User(
        email="g6-benchmark@example.test",
        password_hash=hash_password("benchmark-password"),
        role="user",
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    site = ensure_default_site(db, user.id)
    site.timezone = "UTC"
    meter = get_default_meter(db, user.id)
    assert meter is not None
    meter.source_type = "push"
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=10)
    start = end - timedelta(minutes=READING_COUNT - 1)
    rows = [
        {
            "meter_id": meter.id,
            "timestamp": start + timedelta(minutes=index),
            "gap": 1.0 + (index % 120) / 100,
            "grp": 0.1,
            "voltage": 230.0,
            "intensity": 5.0,
            "sub_metering_1": 0.0,
            "sub_metering_2": 0.0,
            "sub_metering_3": 0.0,
            "energy_kwh": index / 60,
            "source": "push",
            "quality": "validated",
        }
        for index in range(READING_COUNT)
    ]
    db.bulk_insert_mappings(SmartMeterReading, rows)
    predictions_24 = [[1.2, 0.9, 1.6] for _ in range(24)]
    predictions_168 = [[1.3, 1.0, 1.7] for _ in range(168)]
    db.bulk_insert_mappings(Forecast, [
        {
            "user_id": user.id,
            "site_id": site.id,
            "model_name": "global_tft_168h" if index % 2 else "global_tft_24h",
            "horizon": 168 if index % 2 else 24,
            "predictions": predictions_168 if index % 2 else predictions_24,
            "input_snapshot": {"method": "benchmark", "forecast_origin": end.isoformat()},
            "created_at": end - timedelta(minutes=index),
        }
        for index in range(FORECAST_COUNT)
    ])
    db.bulk_insert_mappings(Alert, [
        {
            "user_id": user.id,
            "site_id": site.id,
            "alert_type": "high_consumption",
            "rule_key": f"benchmark:{index}",
            "severity": "high",
            "message": "Controlled benchmark alert",
            "created_at": end - timedelta(minutes=index),
        }
        for index in range(ALERT_COUNT)
    ])
    db.add(AlertConfig(user_id=user.id, site_id=site.id, threshold_kw=99, missing_data_minutes=5))
    meter.last_seen_at = end
    db.commit()
    return user, start, end


def main() -> None:
    if engine.dialect.name != "postgresql":
        raise SystemExit("G6 performance evidence must run against PostgreSQL")
    query_count = 0

    def count_query(*_args) -> None:
        nonlocal query_count
        query_count += 1

    event.listen(engine, "before_cursor_execute", count_query)
    results: dict[str, dict] = {}
    with Session(engine) as db:
        existing = db.query(User).filter(User.email == "g6-benchmark@example.test").one_or_none()
        if existing is not None:
            db.delete(existing)
            db.commit()
        user, start, end = seed(db)

        def measure(operation) -> dict:
            nonlocal query_count
            durations: list[float] = []
            counts: list[int] = []
            for _ in range(REPEATS + 1):
                db.expire_all()
                query_count = 0
                started = perf_counter()
                value = operation()
                durations.append((perf_counter() - started) * 1000)
                counts.append(query_count)
                if hasattr(value, "close"):
                    value.close()
                db.rollback()
            durations, counts = durations[1:], counts[1:]
            return {
                "p50_ms": round(median(durations), 2),
                "p95_ms": round(percentile(durations, 0.95), 2),
                "query_count_min": min(counts),
                "query_count_max": max(counts),
            }

        # Capture the unindexed baseline in this disposable database, then restore
        # the exact indexes installed by the migration before measuring all gates.
        db.execute(text("DROP INDEX ix_forecasts_user_created"))
        db.execute(text("DROP INDEX ix_alerts_user_created"))
        db.commit()
        results["forecast_history_before_index"] = measure(
            lambda: get_forecast_history(horizon_hours=None, db=db, current_user=user)
        )
        before_forecast_plan = db.execute(text(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) "
            "SELECT id, created_at FROM forecasts WHERE user_id = :user_id "
            "ORDER BY created_at DESC, id DESC LIMIT 20"
        ), {"user_id": user.id}).scalars().all()
        db.execute(text("CREATE INDEX ix_forecasts_user_created ON forecasts (user_id, created_at, id)"))
        db.execute(text("CREATE INDEX ix_alerts_user_created ON alerts (user_id, created_at, id)"))
        db.commit()

        cases = {
            "dashboard_batch": lambda: (
                consumption_service.get_current_consumption(db, user.id),
                consumption_service.get_period_summary(db, user.id, "today"),
                alert_service.get_recent_alerts(db, user.id),
            ),
            "consumption_30d": lambda: consumption_service.get_period_summary(db, user.id, "custom", start, end),
            "raw_readings_page_200": lambda: consumption_service.get_readings_page(db, user.id, "custom", start, end, None, 200),
            "reports_summary": lambda: get_summary(current_user=user, db=db),
            "forecast_history": lambda: get_forecast_history(horizon_hours=None, db=db, current_user=user),
            "alert_worker": lambda: alert_service.evaluate_missing_push_data(db, end + timedelta(minutes=20)),
            "account_export": lambda: build_account_archive(db, user),
        }
        for name, operation in cases.items():
            results[name] = measure(operation)

        plans = {"forecast_history_before_index": list(before_forecast_plan)}
        for name, sql, params in [
            (
                "reading_range",
                "SELECT * FROM smart_meter_readings WHERE meter_id = :meter_id AND timestamp >= :start AND timestamp <= :end ORDER BY timestamp",
                {"meter_id": get_default_meter(db, user.id).id, "start": start, "end": end},
            ),
            (
                "forecast_history",
                "SELECT id, created_at FROM forecasts WHERE user_id = :user_id ORDER BY created_at DESC, id DESC LIMIT 20",
                {"user_id": user.id},
            ),
        ]:
            plan_rows = db.execute(text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}"), params).scalars().all()
            plans[name] = list(plan_rows)

        payload = {
            "dataset": {"readings": READING_COUNT, "forecasts": FORECAST_COUNT, "alerts": ALERT_COUNT, "repeats": REPEATS},
            "results": results,
            "plans": plans,
        }
        output = Path(os.getenv("G6_BENCHMARK_OUTPUT", "g6-performance.json"))
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        db.delete(user)
        db.commit()


if __name__ == "__main__":
    main()
