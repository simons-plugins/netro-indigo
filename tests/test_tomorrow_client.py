"""Unit tests for tomorrow_client.py module.

Tests verify the TomorrowClient correctly fetches weather data from
Tomorrow.io API and transforms it to Netro-compatible format.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add Server Plugin directory to path for imports
SERVER_PLUGIN_DIR = (
    Path(__file__).parent.parent
    / "Netro Sprinklers.indigoPlugin"
    / "Contents"
    / "Server Plugin"
)
sys.path.insert(0, str(SERVER_PLUGIN_DIR))

from tomorrow_client import TomorrowClient, _TOMORROW_TO_NETRO_CONDITION


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def client(mock_logger):
    """Create a TomorrowClient instance."""
    return TomorrowClient(
        api_key="test-api-key-123",
        location="42.3478,-71.0466",
        logger=mock_logger,
        timeout=10,
    )


@pytest.fixture
def sample_tomorrow_response():
    """Sample Tomorrow.io realtime API response."""
    return {
        "data": {
            "time": "2026-04-09T12:00:00Z",
            "values": {
                "temperature": 22.5,
                "temperatureApparent": 21.0,
                "humidity": 65,
                "precipitationIntensity": 0.0,
                "precipitationProbability": 10,
                "windSpeed": 5.2,
                "pressureSurfaceLevel": 1013.25,
                "cloudCover": 30,
                "weatherCode": 1100,
            }
        }
    }


@pytest.fixture
def rainy_tomorrow_response():
    """Sample Tomorrow.io response with rain."""
    return {
        "data": {
            "time": "2026-04-09T12:00:00Z",
            "values": {
                "temperature": 15.0,
                "humidity": 90,
                "precipitationIntensity": 2.5,
                "precipitationProbability": 85,
                "windSpeed": 8.0,
                "pressureSurfaceLevel": 1005.0,
                "weatherCode": 4001,
            }
        }
    }


@pytest.fixture
def snowy_tomorrow_response():
    """Sample Tomorrow.io response with snow."""
    return {
        "data": {
            "time": "2026-04-09T12:00:00Z",
            "values": {
                "temperature": -2.0,
                "humidity": 80,
                "precipitationIntensity": 1.0,
                "precipitationProbability": 70,
                "windSpeed": 3.0,
                "pressureSurfaceLevel": 1020.0,
                "weatherCode": 5000,
            }
        }
    }


@pytest.fixture
def windy_tomorrow_response():
    """Sample Tomorrow.io response with high wind and clear sky."""
    return {
        "data": {
            "time": "2026-04-09T12:00:00Z",
            "values": {
                "temperature": 18.0,
                "humidity": 40,
                "precipitationIntensity": 0.0,
                "precipitationProbability": 0,
                "windSpeed": 18.5,
                "pressureSurfaceLevel": 1010.0,
                "weatherCode": 1000,
            }
        }
    }


# =============================================================================
# TestWeatherCodeMapping
# =============================================================================

@pytest.mark.weather
class TestWeatherCodeMapping:
    """Tests for Tomorrow.io to Netro condition code mapping."""

    def test_clear_codes_map_to_0(self):
        """Clear and Mostly Clear should map to Netro condition 0."""
        assert _TOMORROW_TO_NETRO_CONDITION[1000] == 0
        assert _TOMORROW_TO_NETRO_CONDITION[1100] == 0

    def test_cloudy_codes_map_to_1(self):
        """Cloudy variants should map to Netro condition 1."""
        assert _TOMORROW_TO_NETRO_CONDITION[1101] == 1
        assert _TOMORROW_TO_NETRO_CONDITION[1102] == 1
        assert _TOMORROW_TO_NETRO_CONDITION[1001] == 1

    def test_fog_codes_map_to_1(self):
        """Fog should map to Netro condition 1 (cloudy)."""
        assert _TOMORROW_TO_NETRO_CONDITION[2000] == 1
        assert _TOMORROW_TO_NETRO_CONDITION[2100] == 1

    def test_rain_codes_map_to_2(self):
        """Rain variants should map to Netro condition 2."""
        assert _TOMORROW_TO_NETRO_CONDITION[4000] == 2
        assert _TOMORROW_TO_NETRO_CONDITION[4001] == 2
        assert _TOMORROW_TO_NETRO_CONDITION[4200] == 2
        assert _TOMORROW_TO_NETRO_CONDITION[4201] == 2

    def test_freezing_rain_maps_to_2(self):
        """Freezing rain should map to Netro condition 2 (rain)."""
        assert _TOMORROW_TO_NETRO_CONDITION[6000] == 2
        assert _TOMORROW_TO_NETRO_CONDITION[6001] == 2
        assert _TOMORROW_TO_NETRO_CONDITION[6200] == 2
        assert _TOMORROW_TO_NETRO_CONDITION[6201] == 2

    def test_thunderstorm_maps_to_2(self):
        """Thunderstorm should map to Netro condition 2 (rain)."""
        assert _TOMORROW_TO_NETRO_CONDITION[8000] == 2

    def test_snow_codes_map_to_3(self):
        """Snow variants should map to Netro condition 3."""
        assert _TOMORROW_TO_NETRO_CONDITION[5000] == 3
        assert _TOMORROW_TO_NETRO_CONDITION[5001] == 3
        assert _TOMORROW_TO_NETRO_CONDITION[5100] == 3
        assert _TOMORROW_TO_NETRO_CONDITION[5101] == 3

    def test_ice_pellets_map_to_3(self):
        """Ice pellets should map to Netro condition 3 (snow)."""
        assert _TOMORROW_TO_NETRO_CONDITION[7000] == 3
        assert _TOMORROW_TO_NETRO_CONDITION[7101] == 3
        assert _TOMORROW_TO_NETRO_CONDITION[7102] == 3


# =============================================================================
# TestTransformResponse
# =============================================================================

@pytest.mark.weather
class TestTransformResponse:
    """Tests for Tomorrow.io response transformation."""

    def test_clear_weather(self, client, sample_tomorrow_response):
        """Clear weather transforms correctly with all fields."""
        result = client._transform_response(sample_tomorrow_response)

        assert result is not None
        assert result["condition"] == 0  # Mostly Clear
        assert result["t"] == 22.5
        assert result["humidity"] == 65
        assert result["rain"] == 0.0
        assert result["rain_prob"] == 10
        assert result["wind_speed"] == 5.2
        assert result["pressure"] == 1013.2  # Rounded to 1 decimal
        assert "date" in result

    def test_rainy_weather(self, client, rainy_tomorrow_response):
        """Rain weather transforms with condition=2."""
        result = client._transform_response(rainy_tomorrow_response)

        assert result is not None
        assert result["condition"] == 2  # Rain
        assert result["t"] == 15.0
        assert result["humidity"] == 90
        assert result["rain"] == 2.5
        assert result["rain_prob"] == 85

    def test_snowy_weather(self, client, snowy_tomorrow_response):
        """Snow weather transforms with condition=3."""
        result = client._transform_response(snowy_tomorrow_response)

        assert result is not None
        assert result["condition"] == 3  # Snow
        assert result["t"] == -2.0

    def test_wind_override(self, client, windy_tomorrow_response):
        """High wind overrides clear/cloudy condition to Wind (4)."""
        result = client._transform_response(windy_tomorrow_response)

        assert result is not None
        assert result["condition"] == 4  # Wind
        assert result["wind_speed"] == 18.5

    def test_wind_override_boundary_at_15(self, client):
        """Exactly 15.0 m/s should NOT trigger wind override (threshold is >15)."""
        data = {
            "data": {
                "values": {
                    "temperature": 18.0,
                    "windSpeed": 15.0,
                    "weatherCode": 1000,  # Clear
                }
            }
        }
        result = client._transform_response(data)
        assert result is not None
        assert result["condition"] == 0  # Still Clear, not Wind

    def test_wind_override_just_above_15(self, client):
        """15.1 m/s should trigger wind override for clear/cloudy."""
        data = {
            "data": {
                "values": {
                    "temperature": 18.0,
                    "windSpeed": 15.1,
                    "weatherCode": 1000,  # Clear
                }
            }
        }
        result = client._transform_response(data)
        assert result is not None
        assert result["condition"] == 4  # Wind

    def test_wind_no_override_during_rain(self, client):
        """High wind should not override rain condition."""
        data = {
            "data": {
                "values": {
                    "temperature": 10.0,
                    "windSpeed": 20.0,
                    "weatherCode": 4001,  # Rain
                }
            }
        }
        result = client._transform_response(data)
        assert result is not None
        assert result["condition"] == 2  # Still Rain, not Wind

    def test_missing_temperature_returns_none(self, client, mock_logger):
        """Missing temperature should return None."""
        data = {
            "data": {
                "values": {
                    "humidity": 50,
                    "weatherCode": 1000,
                }
            }
        }
        result = client._transform_response(data)
        assert result is None
        mock_logger.error.assert_called()

    def test_missing_data_key_returns_none(self, client, mock_logger):
        """Response without data key returns None."""
        result = client._transform_response({"error": "bad"})
        assert result is None
        mock_logger.error.assert_called()

    def test_missing_values_key_returns_none(self, client, mock_logger):
        """Response without values key returns None."""
        result = client._transform_response({"data": {}})
        assert result is None
        mock_logger.error.assert_called()

    def test_unknown_weather_code_defaults_to_cloudy(self, client):
        """Unknown weather code maps to Cloudy (1)."""
        data = {
            "data": {
                "values": {
                    "temperature": 20.0,
                    "weatherCode": 9999,
                }
            }
        }
        result = client._transform_response(data)
        assert result is not None
        assert result["condition"] == 1  # Default: Cloudy

    def test_optional_fields_omitted_when_none(self, client):
        """Optional fields not present in response are omitted from result."""
        data = {
            "data": {
                "values": {
                    "temperature": 20.0,
                    "weatherCode": 1000,
                }
            }
        }
        result = client._transform_response(data)
        assert result is not None
        assert "humidity" not in result
        assert "rain" not in result
        assert "rain_prob" not in result
        assert "wind_speed" not in result
        assert "pressure" not in result

    def test_temperature_rounded_to_one_decimal(self, client):
        """Temperature should be rounded to 1 decimal place."""
        data = {
            "data": {
                "values": {
                    "temperature": 22.456,
                    "weatherCode": 1000,
                }
            }
        }
        result = client._transform_response(data)
        assert result["t"] == 22.5

    def test_humidity_rounded_to_integer(self, client):
        """Humidity should be rounded to integer."""
        data = {
            "data": {
                "values": {
                    "temperature": 20.0,
                    "humidity": 65.7,
                    "weatherCode": 1000,
                }
            }
        }
        result = client._transform_response(data)
        assert result["humidity"] == 66
        assert isinstance(result["humidity"], int)


# =============================================================================
# TestFetchCurrentWeather
# =============================================================================

@pytest.mark.weather
class TestFetchCurrentWeather:
    """Tests for the full fetch_current_weather method."""

    @patch("tomorrow_client.requests.get")
    def test_successful_fetch(self, mock_get, client, sample_tomorrow_response):
        """Successful API call returns weather data."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_tomorrow_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = client.fetch_current_weather()

        assert result is not None
        assert result["t"] == 22.5
        assert result["condition"] == 0
        mock_response.raise_for_status.assert_called_once()
        mock_get.assert_called_once()

    @patch("tomorrow_client.requests.get")
    def test_api_params_correct(self, mock_get, client, sample_tomorrow_response):
        """API call uses correct parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_tomorrow_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client.fetch_current_weather()

        mock_response.raise_for_status.assert_called_once()
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["location"] == "42.3478,-71.0466"
        assert call_kwargs[1]["params"]["apikey"] == "test-api-key-123"
        assert call_kwargs[1]["params"]["units"] == "metric"
        assert call_kwargs[1]["timeout"] == 10

    @patch("tomorrow_client.requests.get")
    def test_http_error_returns_none(self, mock_get, client, mock_logger):
        """HTTP error returns None and logs error."""
        import requests
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        result = client.fetch_current_weather()

        assert result is None
        mock_logger.error.assert_called()

    @patch("tomorrow_client.requests.get")
    def test_connection_error_returns_none(self, mock_get, client, mock_logger):
        """Connection error returns None and logs error."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = client.fetch_current_weather()

        assert result is None
        mock_logger.error.assert_called()

    @patch("tomorrow_client.requests.get")
    def test_timeout_returns_none(self, mock_get, client, mock_logger):
        """Timeout returns None and logs error."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = client.fetch_current_weather()

        assert result is None
        mock_logger.error.assert_called()

    @patch("tomorrow_client.requests.get")
    def test_unexpected_error_returns_none(self, mock_get, client, mock_logger):
        """Unexpected error returns None and logs error."""
        mock_get.side_effect = ValueError("unexpected")

        result = client.fetch_current_weather()

        assert result is None
        mock_logger.error.assert_called()


# =============================================================================
# Forecast Fixtures
# =============================================================================

def _make_daily_values(
    temp_avg=15.0, temp_max=20.0, temp_min=10.0, dew_point=8.0,
    humidity=60, rain_sum=2.5, rain_prob_max=40, wind_avg=3.0,
    wind_max=6.0, pressure_avg=1013.0, weather_code_max=1001,
):
    """Helper to build a daily forecast values dict."""
    return {
        "temperatureAvg": temp_avg,
        "temperatureMax": temp_max,
        "temperatureMin": temp_min,
        "dewPointAvg": dew_point,
        "humidityAvg": humidity,
        "rainAccumulationSum": rain_sum,
        "precipitationProbabilityMax": rain_prob_max,
        "windSpeedAvg": wind_avg,
        "windSpeedMax": wind_max,
        "pressureSurfaceLevelAvg": pressure_avg,
        "weatherCodeMax": weather_code_max,
    }


@pytest.fixture
def sample_forecast_response():
    """Sample Tomorrow.io forecast response with 6 days."""
    days = []
    for i in range(6):
        days.append({
            "time": f"2026-04-{10 + i:02d}T05:00:00Z",
            "values": _make_daily_values(
                temp_avg=12.0 + i,
                temp_max=18.0 + i,
                temp_min=6.0 + i,
            ),
        })
    return {"timelines": {"daily": days}}


@pytest.fixture
def rainy_forecast_day():
    """Single rainy forecast day."""
    return {
        "timelines": {
            "daily": [{
                "time": "2026-04-11T05:00:00Z",
                "values": _make_daily_values(
                    rain_sum=15.0,
                    rain_prob_max=85,
                    weather_code_max=4001,
                ),
            }]
        }
    }


# =============================================================================
# TestTransformForecastResponse
# =============================================================================

@pytest.mark.weather
class TestTransformForecastResponse:
    """Tests for Tomorrow.io forecast response transformation."""

    def test_transforms_all_six_days(self, client, sample_forecast_response):
        """Should return 6 dicts, one per day."""
        result = client._transform_forecast_response(sample_forecast_response)
        assert result is not None
        assert len(result) == 6

    def test_dates_extracted_correctly(self, client, sample_forecast_response):
        """Each dict should have the correct YYYY-MM-DD date."""
        result = client._transform_forecast_response(sample_forecast_response)
        assert result[0]["date"] == "2026-04-10"
        assert result[5]["date"] == "2026-04-15"

    def test_daily_fields_mapped_correctly(self, client, sample_forecast_response):
        """First day should have all fields mapped from aggregated values."""
        result = client._transform_forecast_response(sample_forecast_response)
        day = result[0]
        assert day["t"] == 12.0
        assert day["t_max"] == 18.0
        assert day["t_min"] == 6.0
        assert day["t_dew"] == 8.0
        assert day["humidity"] == 60
        assert day["rain"] == 2.5
        assert day["rain_prob"] == 40
        assert day["wind_speed"] == 3.0
        assert day["pressure"] == 1013.0

    def test_weather_code_max_maps_to_condition(self, client, rainy_forecast_day):
        """weatherCodeMax 4001 (Rain) should map to condition 2."""
        result = client._transform_forecast_response(rainy_forecast_day)
        assert result[0]["condition"] == 2

    def test_wind_override_uses_wind_speed_max(self, client):
        """windSpeedMax > 15 should override clear/cloudy to Wind (4)."""
        data = {
            "timelines": {
                "daily": [{
                    "time": "2026-04-10T05:00:00Z",
                    "values": _make_daily_values(
                        wind_max=16.0,
                        weather_code_max=1000,  # Clear
                    ),
                }]
            }
        }
        result = client._transform_forecast_response(data)
        assert result[0]["condition"] == 4

    def test_wind_override_boundary_at_15(self, client):
        """windSpeedMax exactly 15.0 should NOT trigger wind override."""
        data = {
            "timelines": {
                "daily": [{
                    "time": "2026-04-10T05:00:00Z",
                    "values": _make_daily_values(
                        wind_max=15.0,
                        weather_code_max=1000,  # Clear
                    ),
                }]
            }
        }
        result = client._transform_forecast_response(data)
        assert result[0]["condition"] == 0  # Still Clear

    def test_wind_no_override_during_rain(self, client):
        """windSpeedMax > 15 should NOT override rain condition."""
        data = {
            "timelines": {
                "daily": [{
                    "time": "2026-04-10T05:00:00Z",
                    "values": _make_daily_values(
                        wind_max=20.0,
                        weather_code_max=4001,  # Rain
                    ),
                }]
            }
        }
        result = client._transform_forecast_response(data)
        assert result[0]["condition"] == 2  # Still Rain

    def test_missing_temperature_skips_day(self, client, mock_logger):
        """Day with no temperatureAvg should be skipped."""
        data = {
            "timelines": {
                "daily": [
                    {
                        "time": "2026-04-10T05:00:00Z",
                        "values": {"humidityAvg": 50, "weatherCodeMax": 1000},
                    },
                    {
                        "time": "2026-04-11T05:00:00Z",
                        "values": _make_daily_values(),
                    },
                ]
            }
        }
        result = client._transform_forecast_response(data)
        assert len(result) == 1
        assert result[0]["date"] == "2026-04-11"
        mock_logger.warning.assert_called()

    def test_optional_fields_omitted_when_missing(self, client):
        """Only date, condition, and t should be present for minimal data."""
        data = {
            "timelines": {
                "daily": [{
                    "time": "2026-04-10T05:00:00Z",
                    "values": {"temperatureAvg": 15.0, "weatherCodeMax": 1000},
                }]
            }
        }
        result = client._transform_forecast_response(data)
        assert result[0]["t"] == 15.0
        assert "t_max" not in result[0]
        assert "humidity" not in result[0]
        assert "rain" not in result[0]

    def test_missing_timelines_returns_none(self, client, mock_logger):
        """Response without timelines key returns None."""
        result = client._transform_forecast_response({"error": "bad"})
        assert result is None
        mock_logger.error.assert_called()

    def test_empty_daily_returns_empty_list(self, client):
        """Empty daily array returns empty list (not None)."""
        result = client._transform_forecast_response({"timelines": {"daily": []}})
        assert result == []


# =============================================================================
# TestFetchForecast
# =============================================================================

@pytest.mark.weather
class TestFetchForecast:
    """Tests for the full fetch_forecast method."""

    @patch("tomorrow_client.requests.get")
    def test_successful_fetch(self, mock_get, client, sample_forecast_response):
        """Successful API call returns list of weather dicts."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_forecast_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = client.fetch_forecast()

        assert result is not None
        assert len(result) == 6
        mock_response.raise_for_status.assert_called_once()
        mock_get.assert_called_once()

    @patch("tomorrow_client.requests.get")
    def test_api_params_include_timesteps_1d(self, mock_get, client, sample_forecast_response):
        """Forecast API call should include timesteps=1d."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_forecast_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client.fetch_forecast()

        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["timesteps"] == "1d"
        assert call_kwargs[1]["params"]["units"] == "metric"

    @patch("tomorrow_client.requests.get")
    def test_http_error_returns_none(self, mock_get, client, mock_logger):
        """HTTP error returns None and logs error."""
        import requests
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        result = client.fetch_forecast()

        assert result is None
        mock_logger.error.assert_called()

    @patch("tomorrow_client.requests.get")
    def test_connection_error_returns_none(self, mock_get, client, mock_logger):
        """Connection error returns None and logs error."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("no connection")

        result = client.fetch_forecast()

        assert result is None
        mock_logger.error.assert_called()

    @patch("tomorrow_client.requests.get")
    def test_timeout_returns_none(self, mock_get, client, mock_logger):
        """Timeout returns None and logs error."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        result = client.fetch_forecast()

        assert result is None
        mock_logger.error.assert_called()

    @patch("tomorrow_client.requests.get")
    def test_unexpected_error_returns_none(self, mock_get, client, mock_logger):
        """Unexpected error returns None and logs error."""
        mock_get.side_effect = ValueError("unexpected")

        result = client.fetch_forecast()

        assert result is None
        mock_logger.error.assert_called()
