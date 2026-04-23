"""Tests for Whisperer-specific constants."""
import constants


def test_whisperer_staleness_hours_defined():
    """WHISPERER_STALENESS_HOURS should be defined as a positive integer."""
    assert hasattr(constants, "WHISPERER_STALENESS_HOURS")
    assert isinstance(constants.WHISPERER_STALENESS_HOURS, int)
    assert constants.WHISPERER_STALENESS_HOURS > 0


def test_whisperer_staleness_hours_value():
    """WHISPERER_STALENESS_HOURS should be 12 hours (2-12 missed readings at 1-6h cadence)."""
    assert constants.WHISPERER_STALENESS_HOURS == 12
