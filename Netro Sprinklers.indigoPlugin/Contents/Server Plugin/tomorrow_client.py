"""Tomorrow.io weather API client for automated weather reporting.

This module provides the TomorrowClient class that fetches current weather
and daily forecasts from the Tomorrow.io API and transforms them into the
format expected by the Netro report_weather endpoint.

Tomorrow.io returns metric units by default (Celsius, mm, m/s, hPa).
The client returns weather data in metric, and callers are responsible for
converting to US units when needed (for Netro API v1).

Note:
    This module does not import indigo directly. Plugin integration is
    achieved through a logger callback passed to the constructor.
"""

import logging
from datetime import date
import traceback
from typing import Any, Dict, List, Optional

import requests


# =============================================================================
# Tomorrow.io Weather Code to Netro Condition Mapping
# =============================================================================
#
# Netro conditions: 0=Clear, 1=Cloudy, 2=Rain, 3=Snow, 4=Wind
#
# Tomorrow.io v4 weather codes:
# https://docs.tomorrow.io/reference/data-layers-weather-codes

_TOMORROW_TO_NETRO_CONDITION: Dict[int, int] = {
    # Clear / Sunny
    1000: 0,  # Clear, Sunny
    1100: 0,  # Mostly Clear
    # Cloudy
    1101: 1,  # Partly Cloudy
    1102: 1,  # Mostly Cloudy
    1001: 1,  # Cloudy
    # Fog (treat as cloudy)
    2000: 1,  # Fog
    2100: 1,  # Light Fog
    # Rain
    4000: 2,  # Drizzle
    4001: 2,  # Rain
    4200: 2,  # Light Rain
    4201: 2,  # Heavy Rain
    # Snow
    5000: 3,  # Snow
    5001: 3,  # Flurries
    5100: 3,  # Light Snow
    5101: 3,  # Heavy Snow
    # Freezing Rain (treat as rain)
    6000: 2,  # Freezing Drizzle
    6001: 2,  # Freezing Rain
    6200: 2,  # Light Freezing Rain
    6201: 2,  # Heavy Freezing Rain
    # Ice Pellets (treat as snow)
    7000: 3,  # Ice Pellets
    7101: 3,  # Heavy Ice Pellets
    7102: 3,  # Light Ice Pellets
    # Thunderstorm (treat as rain)
    8000: 2,  # Thunderstorm
}

# Default condition when code is unknown — Cloudy is the safest default
# for irrigation: it won't suppress watering like Rain/Snow, but won't
# assume clear skies either.
_DEFAULT_CONDITION = 1  # Cloudy


# =============================================================================
# TomorrowClient
# =============================================================================

class TomorrowClient:
    """Client for fetching weather data from Tomorrow.io API.

    Fetches current weather conditions and transforms them into the dict
    format expected by Netro's report_weather endpoint (metric units).

    Args:
        api_key: Tomorrow.io API key
        location: Location string (lat,lon or place name)
        logger: Logger instance for debug/error output
        timeout: HTTP request timeout in seconds
    """

    REALTIME_URL = "https://api.tomorrow.io/v4/weather/realtime"
    FORECAST_URL = "https://api.tomorrow.io/v4/weather/forecast"

    def __init__(
        self,
        api_key: str,
        location: str,
        logger: logging.Logger,
        timeout: int = 10,
    ):
        self.api_key = api_key
        self.location = location
        self.logger = logger
        self.timeout = timeout

    def fetch_current_weather(self) -> Optional[Dict[str, Any]]:
        """Fetch current weather from Tomorrow.io and return Netro-format dict.

        Returns weather data in metric units suitable for Netro API v2.
        For v1 devices, the caller should convert to US units.

        Returns:
            Dict with Netro weather fields (metric):
                - condition (int): 0=Clear, 1=Cloudy, 2=Rain, 3=Snow, 4=Wind
                - date (str): YYYY-MM-DD
                - t (float): Current temperature in Celsius
                - humidity (int): Relative humidity 0-100
                - rain (float): Precipitation intensity in mm/hr
                - rain_prob (int): Precipitation probability 0-100
                - wind_speed (float): Wind speed in m/s
                - pressure (float): Surface pressure in hPa
            None if the request fails.
        """
        try:
            params = {
                "location": self.location,
                "apikey": self.api_key,
                "units": "metric",
            }

            self.logger.debug(
                f"Fetching weather from Tomorrow.io for location: {self.location}"
            )

            response = requests.get(
                self.REALTIME_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            return self._transform_response(data)

        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            self.logger.error(f"Tomorrow.io API error (HTTP {status})")
            self.logger.debug(f"Tomorrow.io error details: {exc}")
            return None
        except requests.exceptions.ConnectionError:
            self.logger.error(
                "Could not connect to Tomorrow.io API - check internet connection"
            )
            return None
        except requests.exceptions.Timeout:
            self.logger.error("Tomorrow.io API request timed out")
            return None
        except Exception as exc:
            self.logger.error(f"Unexpected error fetching weather: {exc}")
            self.logger.debug(f"Weather fetch traceback:\n{traceback.format_exc()}")
            return None

    def _transform_response(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform Tomorrow.io API response to Netro weather format.

        Args:
            data: Raw JSON response from Tomorrow.io realtime endpoint

        Returns:
            Netro-format weather dict (metric) or None on parse error
        """
        try:
            values = data["data"]["values"]
        except (KeyError, TypeError):
            self.logger.error(
                "Unexpected Tomorrow.io response structure - missing data.values"
            )
            return None

        # Map Tomorrow.io weather code to Netro condition
        weather_code = values.get("weatherCode")
        if weather_code is None:
            self.logger.debug("Tomorrow.io response missing weatherCode, defaulting to Cloudy")
            weather_code = 1001
        condition = _TOMORROW_TO_NETRO_CONDITION.get(weather_code, _DEFAULT_CONDITION)

        # Check for high wind — override condition to Wind if speed is very high
        wind_speed = values.get("windSpeed")
        if wind_speed is not None and wind_speed > 15.0 and condition in (0, 1):
            # >15 m/s (~34 mph, Beaufort 7 near-gale); only override clear/cloudy
            condition = 4

        weather_data = {
            "condition": condition,
            "date": date.today().strftime("%Y-%m-%d"),
        }

        # Temperature (required by Netro)
        temp = values.get("temperature")
        if temp is not None:
            weather_data["t"] = round(float(temp), 1)
        else:
            self.logger.error("Tomorrow.io response missing temperature")
            return None

        # Optional fields
        humidity = values.get("humidity")
        if humidity is not None:
            weather_data["humidity"] = int(round(float(humidity)))

        precip_intensity = values.get("precipitationIntensity")
        if precip_intensity is not None:
            # Tomorrow.io returns mm/hr (intensity). Netro expects total mm but
            # we only have current intensity, not accumulation. Passed as-is —
            # this is an approximation that may overstate rainfall during heavy rain.
            weather_data["rain"] = round(float(precip_intensity), 1)

        precip_prob = values.get("precipitationProbability")
        if precip_prob is not None:
            weather_data["rain_prob"] = int(round(float(precip_prob)))

        if wind_speed is not None:
            weather_data["wind_speed"] = round(float(wind_speed), 1)

        pressure = values.get("pressureSurfaceLevel")
        if pressure is not None:
            weather_data["pressure"] = round(float(pressure), 1)

        self.logger.debug(
            f"Tomorrow.io weather: {weather_data['t']}C, "
            f"condition={condition} (code {weather_code}), "
            f"humidity={weather_data.get('humidity', 'N/A')}%"
        )

        return weather_data

    def fetch_forecast(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch daily forecast from Tomorrow.io and return list of Netro-format dicts.

        Returns up to 6 days of daily forecast data (today + 5 days ahead)
        in metric units suitable for Netro API v2.

        Returns:
            List of Netro weather dicts (one per day), each containing:
                - date (str): YYYY-MM-DD
                - condition (int): 0=Clear, 1=Cloudy, 2=Rain, 3=Snow, 4=Wind
                - t (float): Average temperature in Celsius
                - t_max (float): Maximum temperature in Celsius
                - t_min (float): Minimum temperature in Celsius
                - t_dew (float): Dew point in Celsius
                - humidity (int): Average relative humidity 0-100
                - rain (float): Total rainfall accumulation in mm
                - rain_prob (int): Maximum precipitation probability 0-100
                - wind_speed (float): Average wind speed in m/s
                - pressure (float): Average surface pressure in hPa
            None if the request fails.
        """
        try:
            params = {
                "location": self.location,
                "apikey": self.api_key,
                "units": "metric",
                "timesteps": "1d",
            }

            self.logger.debug(
                f"Fetching forecast from Tomorrow.io for location: {self.location}"
            )

            response = requests.get(
                self.FORECAST_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            return self._transform_forecast_response(data)

        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            self.logger.error(f"Tomorrow.io forecast API error (HTTP {status})")
            self.logger.debug(f"Tomorrow.io forecast error details: {exc}")
            return None
        except requests.exceptions.ConnectionError:
            self.logger.error(
                "Could not connect to Tomorrow.io API - check internet connection"
            )
            return None
        except requests.exceptions.Timeout:
            self.logger.error("Tomorrow.io forecast API request timed out")
            return None
        except Exception as exc:
            self.logger.error(f"Unexpected error fetching forecast: {exc}")
            self.logger.debug(f"Forecast fetch traceback:\n{traceback.format_exc()}")
            return None

    def _transform_forecast_response(
        self, data: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Transform Tomorrow.io forecast response to list of Netro weather dicts.

        Args:
            data: Raw JSON response from Tomorrow.io forecast endpoint

        Returns:
            List of Netro-format weather dicts (metric), one per day.
            None on parse error. Empty list if no daily data.
        """
        try:
            daily = data["timelines"]["daily"]
        except (KeyError, TypeError):
            self.logger.error(
                "Unexpected Tomorrow.io forecast structure - missing timelines.daily"
            )
            return None

        forecasts = []
        for day in daily:
            values = day.get("values", {})

            # Temperature average is required
            temp_avg = values.get("temperatureAvg")
            if temp_avg is None:
                time_str = day.get("time", "unknown")
                self.logger.warning(
                    f"Forecast day {time_str} missing temperatureAvg, skipping"
                )
                continue

            # Extract date from ISO timestamp (e.g. "2026-04-10T05:00:00Z" → "2026-04-10")
            forecast_date = day.get("time", "")[:10]

            # Map weather code to Netro condition
            weather_code = values.get("weatherCodeMax")
            if weather_code is None:
                weather_code = 1001
            condition = _TOMORROW_TO_NETRO_CONDITION.get(weather_code, _DEFAULT_CONDITION)

            # Wind override: use max wind speed for threshold check
            wind_speed_max = values.get("windSpeedMax")
            if wind_speed_max is not None and wind_speed_max > 15.0 and condition in (0, 1):
                condition = 4

            weather_data: Dict[str, Any] = {
                "date": forecast_date,
                "condition": condition,
                "t": round(float(temp_avg), 1),
            }

            # Optional fields
            temp_max = values.get("temperatureMax")
            if temp_max is not None:
                weather_data["t_max"] = round(float(temp_max), 1)

            temp_min = values.get("temperatureMin")
            if temp_min is not None:
                weather_data["t_min"] = round(float(temp_min), 1)

            dew_point = values.get("dewPointAvg")
            if dew_point is not None:
                weather_data["t_dew"] = round(float(dew_point), 1)

            humidity = values.get("humidityAvg")
            if humidity is not None:
                weather_data["humidity"] = int(round(float(humidity)))

            rain = values.get("rainAccumulationSum")
            if rain is not None:
                weather_data["rain"] = round(float(rain), 1)

            rain_prob = values.get("precipitationProbabilityMax")
            if rain_prob is not None:
                weather_data["rain_prob"] = int(round(float(rain_prob)))

            wind_speed = values.get("windSpeedAvg")
            if wind_speed is not None:
                weather_data["wind_speed"] = round(float(wind_speed), 1)

            pressure = values.get("pressureSurfaceLevelAvg")
            if pressure is not None:
                weather_data["pressure"] = round(float(pressure), 1)

            forecasts.append(weather_data)

        self.logger.debug(
            f"Tomorrow.io forecast: {len(forecasts)} days, "
            f"dates {forecasts[0]['date']} to {forecasts[-1]['date']}"
            if forecasts else "Tomorrow.io forecast: no days returned"
        )

        return forecasts
