"""Plugin-loaded smoke test using TestingBase's APIBase.

Asserts the netro plugin is loaded and enabled in the running
Indigo server. Validates auth, connectivity, and plugin
discovery in one call. No netro hardware required.
"""
from shared import APIBase


class TestNetroPluginLoaded(APIBase):
    def test_netro_is_loaded_and_enabled(self):
        plugins = self.get_indigo_object("plugins")
        self.assertIsInstance(plugins, list, "plugins endpoint must return a list")
        netro = next(
            (p for p in plugins if p.get("pluginId") == self.plugin_id),
            None,
        )
        self.assertIsNotNone(
            netro,
            f"netro plugin {self.plugin_id} not found in Indigo's plugin list. "
            f"Loaded plugin IDs: {sorted(p.get('pluginId', '?') for p in plugins)}",
        )
        # Indigo's plugin object exposes 'enabled' and 'isRunning' (or similar).
        # If the exact key differs in Indigo 2025.2, the assertion message
        # will tell us what keys are actually there.
        self.assertTrue(
            netro.get("enabled", False),
            f"netro plugin found but not enabled. Plugin object: {netro}",
        )
