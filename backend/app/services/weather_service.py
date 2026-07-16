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
        # Round coordinates to 2 decimals to prevent cache fragmentation
        rounded_lat = round(latitude, 2)
        rounded_lon = round(longitude, 2)
        cache_key = f"weather:{rounded_lat}:{rounded_lon}:{mode}"
        
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
        return {
            "temperature": 18.0,
            "condition": "Clear",
            "wind_speed": 5.0,
            "is_day": True
        }

    def _fetch_forecast(self, lat: float, lon: float):
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code,wind_speed_10m,is_day"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                current = data.get("current", {})
                
                temp = current.get("temperature_2m", 22.0)
                wcode = current.get("weather_code", 0)
                wind = current.get("wind_speed_10m", 0.0)
                is_day_val = current.get("is_day", 1)
                is_day = bool(is_day_val)
                
                wmo_code_map = {
                    0: "Clear Sky",
                    1: "Mainly Clear",
                    2: "Partly Cloudy",
                    3: "Overcast",
                    45: "Fog",
                    48: "Rime Fog",
                    51: "Light Drizzle",
                    53: "Moderate Drizzle",
                    55: "Dense Drizzle",
                    61: "Slight Rain",
                    63: "Moderate Rain",
                    65: "Heavy Rain",
                    71: "Snow",
                    73: "Moderate Snow",
                    75: "Heavy Snow",
                    80: "Rain Showers",
                    81: "Rain Showers",
                    82: "Heavy Rain Showers",
                    95: "Thunderstorm"
                }
                condition = wmo_code_map.get(wcode, "Unknown")
                
                return {
                    "temperature": float(temp),
                    "condition": condition,
                    "wind_speed": float(wind),
                    "is_day": is_day
                }
            else:
                logger.error(f"Open-Meteo API returned status code {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Error fetching weather from Open-Meteo: {e}", exc_info=True)
            
        # Fallback
        return {
            "temperature": 22.0,
            "condition": "Unavailable",
            "wind_speed": 0.0,
            "is_day": True
        }

weather_service = WeatherService()
