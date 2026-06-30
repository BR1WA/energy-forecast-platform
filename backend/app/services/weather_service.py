from datetime import datetime, timedelta
import requests
import logging

logger = logging.getLogger(__name__)

class WeatherService:
    def __init__(self):
        # In-memory TTL Cache
        self.cache = {}
        # TTL for forecast (1 hour)
        self.forecast_ttl = timedelta(hours=1)

    def get_weather(self, latitude: float, longitude: float, mode: str = "current"):
        """
        Fetches weather data using Open-Meteo with TTL caching.
        mode can be "current", "historical", or "forecast".
        """
        cache_key = f"{latitude}_{longitude}_{mode}"
        
        # Check cache
        if cache_key in self.cache:
            cached_data, expiry = self.cache[cache_key]
            if expiry is None or datetime.now() < expiry:
                return cached_data

        # Fetch data
        if mode == "historical":
            data = self._fetch_historical(latitude, longitude)
            # Indefinite cache for historical
            self.cache[cache_key] = (data, None)
        else:
            data = self._fetch_forecast(latitude, longitude)
            self.cache[cache_key] = (data, datetime.now() + self.forecast_ttl)
            
        return data

    def _fetch_historical(self, lat: float, lon: float):
        # Dummy implementation for scaffolding
        return {"temperature": 18.0, "condition": "Clear"}

    def _fetch_forecast(self, lat: float, lon: float):
        # Dummy implementation for scaffolding
        return {"temperature": 22.0, "condition": "Sunny"}

weather_service = WeatherService()
