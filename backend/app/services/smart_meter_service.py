"""
Smart Meter Service — simulates real-time telemetry from Enedis Linky.
"""
import numpy as np
import datetime
from datetime import timezone

class SmartMeterService:
    """Simulates smart meter readings fetched from utility API (e.g., Enedis Linky)."""

    def fetch_live_readings(self, meter_id: str = "LNK-4829-1092") -> np.ndarray:
        """
        Generates 96 hours of hourly historical readings representing the lookback window.
        
        Returns:
            np.ndarray of shape (96, 7) representing:
            [Global_active_power, Global_reactive_power, Voltage, Global_intensity, Sub_metering_1, Sub_metering_2, Sub_metering_3]
        """
        # Diurnal pattern generation based on current time
        now = datetime.datetime.now(timezone.utc)
        
        readings = []
        for h in range(96):
            # Hour of day for this step
            step_time = now - datetime.timedelta(hours=(95 - h))
            hour = step_time.hour
            is_weekend = step_time.weekday() in [5, 6]
            
            # Base active power (kW)
            # Peak hours: 7 AM - 9 AM, 6 PM - 10 PM
            if 7 <= hour <= 9 or 18 <= hour <= 22:
                base_power = 2.5 + np.sin(hour) * 0.5
                if is_weekend:
                    base_power += 0.5
            else:
                base_power = 0.8 + np.cos(hour) * 0.2
            
            # Add some pseudo-random noise
            noise = np.random.uniform(-0.15, 0.15)
            gap = max(0.2, base_power + noise)
            
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

_service = None

def get_smart_meter_service() -> SmartMeterService:
    global _service
    if _service is None:
        _service = SmartMeterService()
    return _service
