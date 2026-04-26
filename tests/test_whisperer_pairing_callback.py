"""Tests for Plugin.getWhispererDevices ConfigUI callback."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_indigo(mock_indigo_base):
    """Extend conftest mock_indigo_base with iter() for callback tests."""
    mock_indigo_base.devices.iter = MagicMock(return_value=iter([]))
    return mock_indigo_base


def _fake_device(dev_id, name, type_id="Whisperer"):
    return SimpleNamespace(id=dev_id, name=name, deviceTypeId=type_id)


def test_returns_unpaired_sentinel_when_no_whisperers(mock_indigo):
    """With zero Whisperers installed, returns only the unpaired option."""
    mock_indigo.devices.iter.return_value = iter([])
    # Import after mock is installed.
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)  # skip __init__
    result = plugin.getWhispererDevices()
    assert result[0] == ("", "(Unpaired — use Netro forecast)")
    assert len(result) == 1


def test_returns_whisperers_sorted_by_name(mock_indigo):
    """Whisperers are appended, sorted case-insensitively by name."""
    devs = [
        _fake_device(101, "Zebra"),
        _fake_device(102, "apple"),
        _fake_device(103, "Mango"),
        _fake_device(104, "Sprite 8-zone", type_id="Sprite"),  # not Whisperer
    ]
    mock_indigo.devices.iter.return_value = iter(devs)
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)
    result = plugin.getWhispererDevices()
    assert result[0] == ("", "(Unpaired — use Netro forecast)")
    assert result[1:] == [("102", "apple"), ("103", "Mango"), ("101", "Zebra")]


def test_ignores_non_whisperer_devices(mock_indigo):
    """Sprite/Pixie/Spark controllers and zones are excluded."""
    devs = [
        _fake_device(1, "Sprite 8", type_id="Sprite"),
        _fake_device(2, "Pixie 12", type_id="Pixie"),
        _fake_device(3, "Zone A", type_id="zone"),
        _fake_device(4, "Garden Whisperer", type_id="Whisperer"),
    ]
    mock_indigo.devices.iter.return_value = iter(devs)
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)
    result = plugin.getWhispererDevices()
    whisperer_ids = [r[0] for r in result[1:]]
    assert whisperer_ids == ["4"]
