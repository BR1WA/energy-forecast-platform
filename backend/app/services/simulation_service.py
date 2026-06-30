import math
import time
from datetime import datetime

class SimulationService:
    def __init__(self):
        self.is_running = False
        self.start_time = None

    def start_simulation(self):
        self.is_running = True
        self.start_time = time.time()
        return {"status": "started"}

    def stop_simulation(self):
        self.is_running = False
        return {"status": "stopped"}

    def get_status(self):
        return {
            "is_running": self.is_running,
            "uptime": time.time() - self.start_time if self.is_running else 0
        }

    def reset_simulation(self):
        self.is_running = False
        self.start_time = None
        return {"status": "reset"}

    def get_simulated_consumption(self, steps=24):
        """Generates dummy sine wave consumption data for UI testing."""
        base = 2.0
        return [{"timestamp": datetime.now().isoformat(), "kw": base + math.sin(i / 3.0)} for i in range(steps)]

simulation_service = SimulationService()
