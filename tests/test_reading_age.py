"""Tests for parse_reading_age_hours utility."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import utils


class TestParseReadingAgeHours:
    """Test utils.parse_reading_age_hours across supported input formats."""

    @pytest.fixture
    def fixed_now(self):
        """Anchor "now" to a known UTC datetime for deterministic age math."""
        return datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc)

    def test_v2_iso_string_fresh(self, fixed_now):
        """ISO-8601 string 3h old → ~3.0 hours."""
        three_hours_ago = (fixed_now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(three_hours_ago)
        assert age is not None
        assert 2.9 <= age <= 3.1

    def test_v2_iso_string_with_timezone(self, fixed_now):
        """ISO-8601 string with Z suffix should be treated as UTC."""
        three_hours_ago = (fixed_now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(three_hours_ago)
        assert age is not None
        assert 2.9 <= age <= 3.1

    def test_v1_epoch_millis_fresh(self, fixed_now):
        """V1 epoch millis 3h old → ~3.0 hours."""
        epoch_ms = int((fixed_now - timedelta(hours=3)).timestamp() * 1000)
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(epoch_ms)
        assert age is not None
        assert 2.9 <= age <= 3.1

    def test_v1_epoch_millis_as_string(self, fixed_now):
        """Epoch millis passed as a string should still parse."""
        epoch_ms_str = str(int((fixed_now - timedelta(hours=3)).timestamp() * 1000))
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(epoch_ms_str)
        assert age is not None
        assert 2.9 <= age <= 3.1

    def test_stale_reading(self, fixed_now):
        """24h-old reading → 24.0 hours (above threshold)."""
        one_day_ago = (fixed_now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(one_day_ago)
        assert age is not None
        assert 23.9 <= age <= 24.1

    def test_unparseable_string_returns_none(self):
        """Garbage input returns None, does not raise."""
        assert utils.parse_reading_age_hours("not-a-timestamp") is None
        assert utils.parse_reading_age_hours("unknown") is None

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        assert utils.parse_reading_age_hours("") is None

    def test_none_input_returns_none(self):
        """None input returns None."""
        assert utils.parse_reading_age_hours(None) is None

    def test_negative_age_clamped_to_zero(self, fixed_now):
        """Future timestamp (clock skew) returns 0.0, never negative."""
        future = (fixed_now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(future)
        assert age == 0.0

    def test_bool_input_returns_none(self):
        """Booleans (subclass of int) must NOT be treated as epoch millis."""
        assert utils.parse_reading_age_hours(True) is None
        assert utils.parse_reading_age_hours(False) is None

    def test_iso_with_triple_z_suffix_rejected(self):
        """Malformed ISO with multiple 'Z's is not silently stripped to valid."""
        # Only a single trailing 'Z' is accepted; "...ZZZ" is malformed input
        # and should return None rather than silently parsing as if it were "...Z".
        result = utils.parse_reading_age_hours("2026-04-23T10:00:00ZZZ")
        assert result is None
