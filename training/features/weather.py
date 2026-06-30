import requests
import pandas as pd

class WeatherFetcher:
    """
    Fetches historical weather data from Open-Meteo for a given location and time period.
    Free, no API key required.
    """
    def __init__(self, latitude=48.8566, longitude=2.3522, timezone="auto"):
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.base_url = "https://archive-api.open-meteo.com/v1/archive"

    def fetch_historical(self, start_date, end_date):
        """
        Fetches hourly historical weather data.
        start_date, end_date: strings in 'YYYY-MM-DD' format.
        """
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,cloud_cover,surface_pressure",
            "timezone": self.timezone
        }
        
        response = requests.get(self.base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        hourly = data["hourly"]
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(hourly["time"]),
            "temperature": hourly["temperature_2m"],
            "humidity": hourly["relative_humidity_2m"],
            "wind_speed": hourly["wind_speed_10m"],
            "precipitation": hourly["precipitation"],
            "cloud_cover": hourly["cloud_cover"],
            "pressure": hourly["surface_pressure"]
        })
        
        # Forward fill missing values (very rare in Open-Meteo but good practice)
        df = df.ffill().bfill()
        return df

    def merge_with_electricity(self, df_elec, df_weather):
        """
        Merges electrical dataset with weather dataset on timestamp.
        Assumes both dataframes have a 'timestamp' column.
        """
        # Ensure timestamps match (e.g. hourly frequency)
        df_merged = pd.merge(df_elec, df_weather, on="timestamp", how="left")
        # Forward fill any missing weather observations
        df_merged = df_merged.ffill().bfill()
        return df_merged
