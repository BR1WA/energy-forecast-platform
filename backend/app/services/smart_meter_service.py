"""
Smart Meter Service — simulates real-time telemetry from Enedis Linky.
"""
import numpy as np
import datetime
from datetime import timezone
import socket
import ipaddress
from urllib.parse import urlparse

def is_safe_url(url: str, allow_private: bool = False) -> bool:
    try:
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ("http", "https"):
            return False
            
        hostname = parsed_url.hostname
        if not hostname:
            return False
            
        if allow_private:
            return True
            
        addr_info = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
        return True
    except Exception as e:
        print(f"[SSRF Protection] Error validating URL {url}: {e}")
        return False

class SmartMeterService:
    """Simulates smart meter readings fetched from utility API or real API."""

    def fetch_live_readings(self, meter_id: str = "LNK-4829-1092", db = None) -> np.ndarray:
        """
        Generates 96 hours of hourly historical readings representing the lookback window.
        
        Returns:
            np.ndarray of shape (96, 7) representing:
            [Global_active_power, Global_reactive_power, Voltage, Global_intensity, Sub_metering_1, Sub_metering_2, Sub_metering_3]
        """
        # Diurnal pattern generation based on current time
        now = datetime.datetime.now(timezone.utc)
        
        # Fetch settings for sensor_type
        from app.models.settings import SystemSettings
        
        close_db = False
        if db is None:
            from app.database import SessionLocal
            db = SessionLocal()
            close_db = True
            
        try:
            settings_db = db.query(SystemSettings).first()
            sensor_type = settings_db.sensor_type if settings_db else "simulator"
            sensor_api_url = settings_db.sensor_api_url if settings_db else None
        finally:
            if close_db:
                db.close()

        if sensor_type == "real_api" and sensor_api_url:
            from app.config import get_settings
            app_settings = get_settings()
            allow_private = getattr(app_settings, "DEBUG", True)
            
            if is_safe_url(sensor_api_url, allow_private=allow_private):
                import requests
                try:
                    response = requests.get(sensor_api_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        # Expecting data format matching our numpy array or similar. 
                        # If it's a real API, parse it here. For now, fallback to simulator if error.
                        if 'readings' in data:
                            return np.array(data['readings'], dtype=float)
                except Exception as e:
                    print(f"[SmartMeterService] Failed to fetch from real API, falling back to simulator: {e}")
            else:
                print(f"[SmartMeterService] Blocked unsafe sensor API URL: {sensor_api_url}")

        # Simulator (Normalized for Moroccan average households)
        # Moroccan homes use significantly less electricity.
        readings = []
        for h in range(96):
            # Hour of day for this step
            step_time = now - datetime.timedelta(hours=(95 - h))
            hour = step_time.hour
            is_weekend = step_time.weekday() in [5, 6]
            
            # Base active power (kW) - Moroccan Household Scale
            # Peak hours: 7 AM - 9 AM, 6 PM - 10 PM
            if 7 <= hour <= 9 or 18 <= hour <= 22:
                base_power = 0.35 + np.sin(hour) * 0.08
                if is_weekend:
                    base_power += 0.05
            else:
                base_power = 0.16 + np.cos(hour) * 0.03
            
            # Add some pseudo-random noise
            noise = np.random.uniform(-0.04, 0.04)
            gap = max(0.08, base_power + noise)
            
            # Reactive power is roughly 10% of active power
            grp = max(0.05, gap * 0.1 + np.random.uniform(-0.02, 0.02))
            
            # Voltage fluctuates around 235V, drops slightly when demand is high
            voltage = 235.0 - (gap * 1.5) + np.random.uniform(-0.5, 0.5)
            
            # Global intensity (A) = (GAP * 1000) / Voltage
            gi = (gap * 1000.0) / voltage
            
            # Sub-meterings (in Wh equivalent, scaled to kW active power)
            sub1 = 0.0
            sub2 = 0.0
            sub3 = 0.0
            
            # Kitchen (Sub1) active during cooking hours
            if 11 <= hour <= 13 or 18 <= hour <= 20:
                sub1 = max(0.0, gap * 5.0 + np.random.uniform(-1.0, 1.0))
            
            # Laundry (Sub2) active mostly during weekends/mornings
            if is_weekend and (9 <= hour <= 15):
                sub2 = max(0.0, gap * 8.0 + np.random.uniform(-1.0, 1.0))
            elif 8 <= hour <= 11:
                sub2 = max(0.0, gap * 3.0 + np.random.uniform(-0.5, 0.5))
                
            # HVAC / Water Heater (Sub3) active based on time
            sub3 = max(0.0, gap * 12.0 + np.random.uniform(-2.0, 2.0))
            
            readings.append([
                float(gap),
                float(grp),
                float(voltage),
                float(gi),
                float(sub1),
                float(sub2),
                float(sub3)
            ])
            
        return np.array(readings)

    def fetch_single_live_reading(self) -> dict:
        import random
        now = datetime.datetime.now(timezone.utc)
        hour = now.hour
        is_weekend = now.weekday() in [5, 6]
        
        # Base active power (kW) - Moroccan Household Scale
        if 7 <= hour <= 9 or 18 <= hour <= 22:
            base_power = 0.38 + random.uniform(-0.06, 0.06)
            if is_weekend:
                base_power += 0.04
        else:
            base_power = 0.16 + random.uniform(-0.02, 0.02)
        
        gap = max(0.08, base_power)
        grp = max(0.02, gap * 0.08 + random.uniform(-0.01, 0.01))
        voltage = 232.0 + random.uniform(-2.0, 2.0) - (gap * 1.0)
        gi = (gap * 1000.0) / voltage
        
        # Sub-meterings (Wh equivalents, active load)
        sub1 = max(0.0, gap * 6.2 + random.uniform(-0.5, 0.5)) if (11 <= hour <= 13 or 18 <= hour <= 20) else max(0.0, random.uniform(0.0, 0.2))
        sub2 = max(0.0, gap * 5.5 + random.uniform(-0.5, 0.5)) if (is_weekend and 9 <= hour <= 15) else max(0.0, random.uniform(0.0, 0.1))
        sub3 = max(0.0, gap * 14.2 + random.uniform(-1.0, 1.0))
        
        return {
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "gap": round(gap, 3),
            "grp": round(grp, 3),
            "voltage": round(voltage, 1),
            "intensity": round(gi, 2),
            "sub_metering_1": round(sub1, 1),
            "sub_metering_2": round(sub2, 1),
            "sub_metering_3": round(sub3, 1)
        }

_service = None

def get_smart_meter_service() -> SmartMeterService:
    global _service
    if _service is None:
        _service = SmartMeterService()
    return _service
