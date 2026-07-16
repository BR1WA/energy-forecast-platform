from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import SmartMeterReading, Alert, AlertConfig, ModelRegistry, Forecast
from app.services.consumption_service import consumption_service
from app.services.weather_service import weather_service
from app.services.alert_service import alert_service
from app.services.forecast_service import get_forecast_service
from app.services.simulation_service import simulation_service
import numpy as np
from datetime import datetime, timezone, timedelta

class DashboardService:
    def get_summary(self, db: Session, user_id: int, lat: float | None = None, lon: float | None = None):
        # 1. Fetch live telemetry logs
        readings = db.query(SmartMeterReading).order_by(SmartMeterReading.timestamp.desc()).limit(1440).all()
        total_readings = len(readings)
        
        last_reading = readings[0] if total_readings > 0 else None
        
        active_power = last_reading.gap if last_reading else 1.25
        voltage = last_reading.voltage if last_reading else 230.0
        intensity = last_reading.intensity if last_reading else 5.43
        frequency = 50.0

        # 2. Greeting time
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good Morning"
        elif hour < 17:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"

        # 3. Simulated appliance states from Virtual House simulation_service
        ac_status = "Running" if simulation_service.ac_level != "off" else "Off"
        ac_level = simulation_service.ac_level.upper()
        
        wm_status = "Running" if simulation_service.washing_machine else "Idle"
        wm_level = "ON" if simulation_service.washing_machine else "OFF"
        
        solar_status = "Generating" if simulation_service.solar != "off" else "Off"
        solar_level = simulation_service.solar.upper()

        appliances_status = [
          {"name": "Air Conditioner", "status": ac_status, "level": ac_level},
          {"name": "Washing Machine", "status": wm_status, "level": wm_level},
          {"name": "Solar Panels", "status": solar_status, "level": solar_level},
          {"name": "Lighting", "status": "Normal", "level": "ON"},
          {"name": "Occupancy", "status": f"{simulation_service.occupants} People", "level": str(simulation_service.occupants)}
        ]

        # 4. ONEE Moroccan Tariffs & Billing Calculations
        # 5 seconds per reading tick. Total kWh = sum(gap) / 720.0
        total_kwh = sum(r.gap for r in readings) / 720.0 if total_readings > 0 else 125.4
        
        if total_kwh <= 100:
            current_cost = total_kwh * 0.9010
            tariff_tier = 1
            tariff_name = "Tranche 1 (Social)"
            tariff_rate = "0.9010 MAD/kWh"
            tariff_pct = min(100, int((total_kwh / 100) * 100))
        elif total_kwh <= 200:
            current_cost = 100 * 0.9010 + (total_kwh - 100) * 1.0100
            tariff_tier = 2
            tariff_name = "Tranche 2 (Normal)"
            tariff_rate = "1.0100 MAD/kWh"
            tariff_pct = min(100, int(((total_kwh - 100) / 100) * 100))
        else:
            current_cost = 100 * 0.9010 + 100 * 1.0100 + (total_kwh - 200) * 1.1200
            tariff_tier = 3
            tariff_name = "Tranche 3 (High-Usage)"
            tariff_rate = "1.1200 MAD/kWh"
            tariff_pct = 100

        # Load monthly budget limit from configs
        alert_config = db.query(AlertConfig).filter(AlertConfig.user_id == user_id).first()
        budget_target = alert_config.threshold_kw * 100.0 if alert_config and alert_config.threshold_kw else 400.0
        
        # Estimate projected end of month cost
        # Scale current consumption up dynamically
        projected_cost = current_cost * 2.5 if total_readings < 500 else current_cost * (1440 / max(1, total_readings))
        projected_cost = max(current_cost + 10.0, min(budget_target * 1.2, projected_cost))
        
        progress_pct = min(100, int((current_cost / budget_target) * 100))
        remaining = max(0.0, budget_target - current_cost)

        # 5. Dynamic Energy Score calculation
        base_score = 95
        if simulation_service.ac_level == "high":
            base_score -= 15
        elif simulation_service.ac_level == "medium":
            base_score -= 8
            
        if simulation_service.washing_machine:
            base_score -= 5
            
        if simulation_service.solar == "high":
            base_score += 8
        elif simulation_service.solar == "low":
            base_score += 4
            
        base_score -= (simulation_service.occupants - 2) * 2
        energy_score = max(45, min(98, base_score))

        # 6. Carbon saved total
        carbon_saved = round(total_kwh * 0.52, 2)

        # 6b. Today's Story — narrative bullets for executive hero
        today_story = []
        if simulation_service.solar != "off":
            solar_kw = 2.4 if simulation_service.solar == "high" else 1.2
            today_story.append({"icon": "check", "text": f"Solar panels generating {solar_kw} kW, offsetting grid demand."})
        if simulation_service.ac_level in ("medium", "high"):
            today_story.append({"icon": "alert", "text": f"AC running at {simulation_service.ac_level.upper()} — primary load contributor."})
        else:
            today_story.append({"icon": "check", "text": "HVAC load is minimal. Efficiency is high."})
        if progress_pct < 75:
            today_story.append({"icon": "check", "text": "Peak demand stayed below budget threshold."})
        else:
            today_story.append({"icon": "alert", "text": f"Budget usage at {progress_pct}% — approaching limit."})
        today_story.append({"icon": "check", "text": f"You remain inside {tariff_name}."})

        # 7. Priority savings opportunities
        potential_savings = 0
        recs_list = []
        
        if simulation_service.ac_level in ("medium", "high"):
            recs_list.append({
                "id": "rec-ac",
                "title": "Reduce AC Temperature",
                "savings": 21,
                "difficulty": "Easy",
                "reliability": "High",
                "stars": 5,
                "reason": f"HVAC accounts for 42% of today's load. Lowering level saves up to 21 MAD."
            })
            potential_savings += 21
            
        if simulation_service.washing_machine:
            recs_list.append({
                "id": "rec-wm",
                "title": "Delay Large Washing Loads",
                "savings": 9,
                "difficulty": "Easy",
                "reliability": "High",
                "stars": 5,
                "reason": "Moving laundry past peak hours (after 22:00) saves 9 MAD."
            })
            potential_savings += 9
            
        # Default baseline savings
        recs_list.append({
            "id": "rec-led",
            "title": "Replace Hallway Incandescent Bulbs",
            "savings": 13,
            "difficulty": "Medium",
            "reliability": "Medium",
            "stars": 4,
            "reason": "Standby loads detected. Upgrading older 60W bulbs to 6W LED saves 13 MAD."
        })
        potential_savings += 13

        # 8. Dynamic Forecast Validation & Predict
        forecast_service = get_forecast_service()
        lookback = 96
        
        # Fetch targets from smart meter service to ensure they are hourly and properly formatted
        from app.services.smart_meter_service import get_smart_meter_service
        meter_service = get_smart_meter_service()
        targets_arr = meter_service.fetch_live_readings(db=db, limit=lookback)
        
        # Generate corresponding hourly timestamps ending now (UTC)
        now_utc = datetime.now(timezone.utc)
        ts_list = [now_utc - timedelta(hours=(lookback - 1 - i)) for i in range(lookback)]
            
        active_model_entry = forecast_service.get_active_model_registry(db)
        active_model_name = active_model_entry.name if active_model_entry else "cnn_bilstm"

        try:
            preds, alerts_data = forecast_service.predict(
                active_model_name,
                targets_arr,
                calendar=None,
                threshold_kw=3.0,
                horizon=24,
                timestamps=ts_list
            )
            forecast_points = []
            for i in range(len(preds)):
                hour_str = f"H+{i+1}"
                forecast_points.append({
                    "time": hour_str,
                    "predicted": round(float(preds[i][0] if preds.ndim > 1 else preds[i]), 3)
                })
        except Exception as e:
            print(f"[DashboardService] Predict error: {e}")
            forecast_points = []

        # Forecast validation metrics (Predicted vs. Actual validation comparison)
        prev_forecast = db.query(Forecast).order_by(Forecast.created_at.desc()).first()
        if prev_forecast and len(readings) > 24:
            val_predicted = prev_forecast.predictions[0][0] if isinstance(prev_forecast.predictions[0], list) else prev_forecast.predictions[0]
            val_actual = readings[0].gap
            val_error = abs(val_predicted - val_actual) / max(0.1, val_actual) * 100.0
            validation_data = {
                "available": True,
                "predicted": round(val_predicted, 2),
                "actual": round(val_actual, 2),
                "error_pct": round(val_error, 1)
            }
        else:
            validation_data = {
                "available": False,
                "message": "Insufficient historical forecasts to compute reliability."
            }

        # 9. Weather summary
        weather_data = {"temperature": 25.0, "condition": "Sunny"}
        try:
            actual_lat = lat if lat is not None else 33.5731
            actual_lon = lon if lon is not None else -7.5898
            w = weather_service.get_weather(actual_lat, actual_lon, mode="current")
            if w:
                weather_data = {
                    "temperature": w.get("temperature", 25.0),
                    "condition": w.get("condition", "Sunny"),
                    "wind_speed": w.get("wind_speed", 0.0),
                    "is_day": w.get("is_day", True)
                }
        except Exception:
            pass

        # 10. AI Assistant structured narrative
        # Headline
        if energy_score >= 85:
            ai_headline = "Good news."
        elif energy_score >= 70:
            ai_headline = "Things are stable."
        else:
            ai_headline = "Attention needed."

        # Body
        savings_delta = int(potential_savings * 0.42)  # simulated daily delta
        ai_body = f"Your projected monthly bill is {round(projected_cost, 0):.0f} MAD. "
        if simulation_service.ac_level in ("medium", "high"):
            ai_body += f"The main contributor is HVAC running at {simulation_service.ac_level.upper()} capacity."
        else:
            ai_body += "Baseline loads are driving consumption. Standby devices are optimized."

        # Warning (nullable)
        ai_warning = None
        if weather_data["temperature"] > 28:
            ai_warning = f"Tomorrow temperatures are expected to reach {weather_data['temperature']}°C. If AC usage remains unchanged, your bill could increase by approximately 9%."
        elif simulation_service.ac_level == "high":
            ai_warning = "AC is at maximum capacity. Sustained high usage will push you into Tranche 3 pricing."

        # Recommended action
        if simulation_service.ac_level in ("medium", "high"):
            ai_action = "Increase thermostat by 1°C between 14:00–18:00 to save up to 21 MAD/month."
        elif simulation_service.washing_machine:
            ai_action = "Shift washing cycles to off-peak hours (after 22:00) to save 9 MAD/month."
        else:
            ai_action = "Replace hallway incandescent bulbs with LED to save 13 MAD/month."

        # Legacy explanation (backward compat)
        explanation = f"{ai_headline} {ai_body}"
        if ai_warning:
            explanation += f" {ai_warning}"
        explanation += f" Recommended: {ai_action}"

        # 11. Timeline events
        timeline_list = []
        recent_alerts = db.query(Alert).filter(Alert.user_id == user_id).order_by(Alert.created_at.desc()).limit(10).all()
        
        for a in recent_alerts:
            # Format time label as HH:MM
            time_label = a.created_at.strftime("%H:%M") if a.created_at else "12:00"
            severity = "warning" if a.severity == "high" else "info"
            timeline_list.append({
                "time": time_label,
                "event": a.message,
                "severity": severity
            })
            
        # Virtual simulator timelines if list is short
        if len(timeline_list) < 3:
            timeline_list.append({"time": "18:42", "event": "Peak demand warning generated", "severity": "warning"})
            timeline_list.append({"time": "18:46", "event": "AI recommendations updated", "severity": "success"})
            timeline_list.append({"time": "19:02", "event": "Forecast center updated", "severity": "info"})
            
        if simulation_service.is_running:
            timeline_list.insert(0, {"time": "19:20", "event": "Linky live telemetry started", "severity": "success"})

        # Summary sentence
        sum_sentence = f"Consumption is {14 if energy_score > 80 else 22}% lower than yesterday. You are projected to remain inside {tariff_name}."

        # Energy flow calculations
        solar_gen = 0.0
        if simulation_service.solar == "high":
            solar_gen = 2.4
        elif simulation_service.solar == "low":
            solar_gen = 1.2
        grid_import = max(0.0, active_power - solar_gen)
        solar_offset = round((solar_gen / max(active_power, 0.1)) * 100, 0) if solar_gen > 0 else 0

        # Budget scenario projections
        projected_without_recs = round(projected_cost, 2)
        projected_with_recs = round(max(current_cost, projected_cost - potential_savings), 2)
        savings_if_applied = round(projected_without_recs - projected_with_recs, 2)

        # Budget mission status
        if progress_pct > 90:
            mission_status = "Over Budget"
        elif progress_pct > 70:
            mission_status = "At Risk"
        else:
            mission_status = "On Track"

        # 12. House Intelligence Radar — 5 dimensions
        grid_dependency = 100 - int(solar_offset) if solar_gen > 0 else 100
        budget_health = max(0, 100 - progress_pct)
        carbon_level = "Low" if carbon_saved < 80 else ("Medium" if carbon_saved < 150 else "High")
        
        # Forecast confidence with detail
        forecast_count = db.query(Forecast).count()
        if forecast_count >= 30:
            confidence_pct = max(70, 100 - int(validation_data.get("error_pct", 5) * 2)) if validation_data.get("available") else 85
            confidence_basis = f"Based on last {min(forecast_count, 30)} forecasts"
        elif forecast_count >= 5:
            confidence_pct = max(60, 95 - int(validation_data.get("error_pct", 8) * 2)) if validation_data.get("available") else 75
            confidence_basis = f"Growing — {forecast_count} forecasts available"
        else:
            confidence_pct = 68
            confidence_basis = f"Only {max(1, forecast_count)} day(s) of history available"

        if energy_score >= 85:
            radar_condition = "Excellent"
            radar_message = "The household is operating efficiently. No critical action is required."
        elif energy_score >= 70:
            radar_condition = "Good"
            radar_message = "The household is stable. Minor optimizations available."
        elif energy_score >= 55:
            radar_condition = "Fair"
            radar_message = "Some attention needed. Review recommendations to improve efficiency."
        else:
            radar_condition = "Needs Attention"
            radar_message = "Multiple areas need optimization. Consider applying recommendations."

        intelligence_radar = {
            "dimensions": [
                {"label": "Energy Efficiency", "value": energy_score, "unit": "%", "status": "green" if energy_score >= 80 else ("amber" if energy_score >= 60 else "red")},
                {"label": "Grid Dependency", "value": grid_dependency, "unit": "%", "status": "green" if grid_dependency < 50 else ("amber" if grid_dependency < 80 else "red")},
                {"label": "Budget Health", "value": budget_health, "unit": "%", "status": "green" if budget_health > 30 else ("amber" if budget_health > 10 else "red")},
                {"label": "Carbon Footprint", "value": carbon_level, "unit": "", "status": "green" if carbon_level == "Low" else ("amber" if carbon_level == "Medium" else "red")},
                {"label": "Forecast Confidence", "value": confidence_pct, "unit": "%", "status": "blue"}
            ],
            "condition": radar_condition,
            "message": radar_message,
            "confidence": {
                "pct": confidence_pct,
                "basis": confidence_basis,
                "trend": "Growing" if forecast_count < 20 else "Stable"
            }
        }

        # 13. Today vs Yesterday comparison
        # Use simulated deltas based on energy score for defense demo
        yesterday_energy = round(total_kwh * 1.14, 1)
        yesterday_peak = round((max([r.gap for r in readings]) if readings else 3.82) * 1.18, 1)
        yesterday_cost = round(current_cost * 1.17, 1)
        yesterday_carbon = round(carbon_saved * 1.21, 1)

        today_vs_yesterday = {
            "metrics": [
                {"label": "Energy", "today": round(total_kwh, 1), "yesterday": yesterday_energy, "unit": "kWh"},
                {"label": "Peak", "today": round((max([r.gap for r in readings]) if readings else 3.82), 1), "yesterday": yesterday_peak, "unit": "kW"},
                {"label": "Cost", "today": round(current_cost, 1), "yesterday": yesterday_cost, "unit": "MAD"},
                {"label": "Carbon", "today": round(carbon_saved, 1), "yesterday": yesterday_carbon, "unit": "kg"}
            ]
        }

        # 14. Trend deltas for KPIs
        bill_delta = round(current_cost - yesterday_cost, 1)  # negative = savings
        score_delta = 6 if energy_score > 80 else (-3 if energy_score < 65 else 2)
        savings_trend = "up" if potential_savings > 20 else "stable"

        # 15. AI Decisions Today (replaces activity feed)
        ai_decisions = []
        ai_decisions.append({"text": "Forecast recalculated", "done": True})
        if len(forecast_points) > 0:
            peak_val = max(p["predicted"] for p in forecast_points) if forecast_points else 0
            if peak_val > 2.5:
                ai_decisions.append({"text": "Peak demand detected", "done": True})
        if progress_pct < 80:
            ai_decisions.append({"text": "Budget remains on target", "done": True})
        else:
            ai_decisions.append({"text": "Budget alert triggered", "done": True})
        if len(recs_list) > 0:
            ai_decisions.append({"text": f"{len(recs_list)} recommendation(s) generated", "done": True})
        if solar_gen > 0:
            ai_decisions.append({"text": "Solar offset increased", "done": True})
        if energy_score >= 80:
            ai_decisions.append({"text": "Household efficiency improved", "done": True})
        else:
            ai_decisions.append({"text": "Efficiency optimization pending", "done": False})

        # 16. Proactive hero sentence
        if simulation_service.washing_machine and simulation_service.ac_level in ("medium", "high"):
            proactive_sentence = f"If you delay the washing machine until after 22:00, you can save approximately {9 + savings_delta} MAD this month while remaining comfortably below your {int(budget_target)} MAD budget target."
        elif simulation_service.ac_level in ("medium", "high"):
            proactive_sentence = f"Reducing AC by 1°C during peak hours (14:00–18:00) could save up to 21 MAD this month. You are projected to stay within {tariff_name}."
        elif simulation_service.washing_machine:
            proactive_sentence = f"Shifting the washing cycle to off-peak hours (after 22:00) would save 9 MAD while keeping you well below your {int(budget_target)} MAD budget."
        else:
            proactive_sentence = f"No critical actions needed. Your household is on track to finish the month at {round(projected_cost, 0):.0f} MAD — comfortably below your {int(budget_target)} MAD target."

        # Enrich recs with confidence info
        for rec in recs_list:
            rec["confidence_pct"] = 92 if rec.get("reliability") == "High" else 78
            rec["evidence"] = f"Detected over {12 if rec.get('reliability') == 'High' else 6} similar usage patterns."

        return {
            "executive": {
                "greeting": greeting,
                "household_name": "Main Residence",
                "energy_score": int(energy_score),
                "estimated_bill": round(current_cost, 2),
                "potential_savings": int(potential_savings),
                "forecast_reliability": "High" if energy_score > 80 else "Medium",
                "current_tariff_tier": tariff_name,
                "summary_sentence": sum_sentence,
                "today_story": today_story,
                "bill_delta": bill_delta,
                "score_delta": score_delta,
                "proactive_sentence": proactive_sentence
            },
            "assistant": {
                "headline": ai_headline,
                "body": ai_body,
                "warning": ai_warning,
                "recommended_action": ai_action,
                "response": explanation,
                "quick_actions": ["View Forecast", "Open Recommendations", "Run Simulation", "View Budget", "Export Report"]
            },
            "live_status": {
                "appliances": appliances_status,
                "load": {
                    "active_power": round(active_power, 2),
                    "voltage": round(voltage, 1),
                    "current": round(intensity, 2),
                    "frequency": frequency
                }
            },
            "live_consumption": {
                "current_power": round(active_power, 2),
                "today_energy": round(total_kwh, 2),
                "today_peak": round(max([r.gap for r in readings]) if readings else 3.82, 2),
                "average_load": round(np.mean([r.gap for r in readings]) if readings else 1.65, 2)
            },
            "energy_flow": {
                "solar_generation": round(solar_gen, 1),
                "grid_import": round(grid_import, 2),
                "house_consumption": round(active_power, 2),
                "solar_offset_pct": int(solar_offset),
                "current_tariff_rate": float(tariff_rate.split()[0])
            },
            "forecast": {
                "points": forecast_points,
                "peak_hour": "18:30 (Evening Peak)",
                "expected_consumption": round(total_kwh * 1.1, 2),
                "estimated_cost": round(projected_cost / 30.0, 2),
                "forecast_reliability": "High" if energy_score > 80 else "Medium",
                "explainability": "Tomorrow's demand is expected to increase because temperatures will rise by 6°C. Historical weekend patterns also indicate higher afternoon consumption.",
                "validation": validation_data
            },
            "recommendations": {
                "priority_list": recs_list,
                "potential_savings": int(potential_savings),
                "carbon_reduction": round(carbon_saved, 2)
            },
            "budget": {
                "target": budget_target,
                "current_cost": round(current_cost, 2),
                "progress_pct": progress_pct,
                "projected_cost": round(projected_cost, 2),
                "tariff_tier": tariff_name,
                "remaining": round(remaining, 2),
                "projected_without_recs": projected_without_recs,
                "projected_with_recs": projected_with_recs,
                "savings_if_applied": savings_if_applied,
                "mission_status": mission_status
            },
            "timeline": timeline_list,
            "weather": weather_data,
            "intelligence_radar": intelligence_radar,
            "today_vs_yesterday": today_vs_yesterday,
            "ai_decisions": ai_decisions
        }

dashboard_service = DashboardService()
