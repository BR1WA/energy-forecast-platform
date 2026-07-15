import math
import time
from datetime import datetime

class SimulationService:
    def __init__(self):
        self.is_running = False
        self.start_time = None
        self.day_part = "evening"
        self.occupants = 2
        self.temperature = 25.0
        self.ac_level = "medium"
        self.washing_machine = False
        self.solar = "off"

    def configure_simulation(self, config: dict):
        self.day_part = config.get("day_part", self.day_part)
        self.occupants = config.get("occupants", self.occupants)
        self.temperature = config.get("temperature", self.temperature)
        self.ac_level = config.get("ac_level", self.ac_level)
        self.washing_machine = config.get("washing_machine", self.washing_machine)
        self.solar = config.get("solar", self.solar)
        return {"status": "configured"}

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
