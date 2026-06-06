"""
build_dim_weather.py — Pull historical daily weather data for ERCOT zones.

Uses the Open-Meteo Historical Weather API (free, no API key required).
Each ERCOT zone is represented by a major city within that zone.
Outputs dim_weather.csv for use in Power BI star schema.

Source: https://open-meteo.com/en/docs/historical-weather-api
"""

import requests
import pandas as pd
import time
import os

# ── ERCOT Zone → Representative City Mapping ────────────────────────────────
# Each zone is mapped to a major city at the center of that zone's geography.
ZONE_CITIES = {
    "COAST":         {"city": "Houston",        "lat": 29.76, "lon": -95.37},
    "EAST":          {"city": "Tyler",          "lat": 32.35, "lon": -95.30},
    "FAR_WEST":      {"city": "Midland",        "lat": 31.99, "lon": -102.08},
    "NORTH":         {"city": "Dallas",         "lat": 32.78, "lon": -96.80},
    "NORTH_C":       {"city": "Waco",           "lat": 31.55, "lon": -97.15},
    "SOUTH_C":       {"city": "Austin",         "lat": 30.27, "lon": -97.74},
    "SOUTHERN":      {"city": "Corpus Christi", "lat": 27.80, "lon": -97.40},
    "WEST":          {"city": "Abilene",        "lat": 32.45, "lon": -99.73},
}

# ── Date Range (match your ERCOT fact table) ─────────────────────────────────
START_DATE = "2020-01-01"
END_DATE = "2024-12-31"

# ── API Configuration ────────────────────────────────────────────────────────
BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "windspeed_10m_max",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
]


def fetch_zone_weather(zone: str, info: dict) -> pd.DataFrame:
    """Fetch daily weather for one zone from Open-Meteo."""
    params = {
        "latitude": info["lat"],
        "longitude": info["lon"],
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": ",".join(DAILY_VARS),
        "temperature_unit": "fahrenheit",
        "windspeed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "America/Chicago",
    }

    print(f"  Fetching {zone} ({info['city']})...", end=" ")
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    daily = data["daily"]
    df = pd.DataFrame({
        "date":                  pd.to_datetime(daily["time"]),
        "zone":                  zone,
        "city":                  info["city"],
        "temp_max_f":            daily["temperature_2m_max"],
        "temp_min_f":            daily["temperature_2m_min"],
        "temp_mean_f":           daily["temperature_2m_mean"],
        "feels_like_max_f":      daily["apparent_temperature_max"],
        "feels_like_min_f":      daily["apparent_temperature_min"],
        "wind_max_mph":          daily["windspeed_10m_max"],
        "precip_total_in":       daily["precipitation_sum"],
        "rain_in":               daily["rain_sum"],
        "snow_in":               daily["snowfall_sum"],
    })

    # ── Derived columns ──────────────────────────────────────────────────
    df["temp_range_f"] = df["temp_max_f"] - df["temp_min_f"]

    # Temperature severity categories (useful for dashboard filters)
    df["temp_category"] = pd.cut(
        df["temp_mean_f"],
        bins=[-999, 20, 32, 50, 70, 85, 100, 999],
        labels=[
            "Extreme Cold (<20°F)",
            "Freezing (20-32°F)",
            "Cold (32-50°F)",
            "Mild (50-70°F)",
            "Warm (70-85°F)",
            "Hot (85-100°F)",
            "Extreme Heat (100°F+)",
        ],
    )

    # Precipitation flag
    df["had_precipitation"] = (df["precip_total_in"] > 0).astype(int)
    df["had_snow"] = (df["snow_in"] > 0).astype(int)

    print(f"{len(df)} days")
    return df


def main():
    print(f"Pulling weather data: {START_DATE} to {END_DATE}\n")

    frames = []
    for zone, info in ZONE_CITIES.items():
        df = fetch_zone_weather(zone, info)
        frames.append(df)
        time.sleep(1)  # Be polite to the free API

    weather = pd.concat(frames, ignore_index=True)

    # ── Summary stats ────────────────────────────────────────────────────
    print(f"\nTotal rows: {len(weather):,}")
    print(f"Date range: {weather['date'].min().date()} to {weather['date'].max().date()}")
    print(f"Zones: {weather['zone'].nunique()}")
    print(f"\nTemperature extremes:")
    print(f"  Coldest: {weather['temp_min_f'].min():.1f}°F "
          f"({weather.loc[weather['temp_min_f'].idxmin(), 'zone']} — "
          f"{weather.loc[weather['temp_min_f'].idxmin(), 'date'].date()})")
    print(f"  Hottest: {weather['temp_max_f'].max():.1f}°F "
          f"({weather.loc[weather['temp_max_f'].idxmax(), 'zone']} — "
          f"{weather.loc[weather['temp_max_f'].idxmax(), 'date'].date()})")

    # ── Save ─────────────────────────────────────────────────────────────
    output_path = os.path.join(os.path.dirname(__file__), "dim_weather.csv")
    weather.to_csv(output_path, index=False)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
