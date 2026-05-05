"""Plugin-loaded smoke test using TestingBase's APIBase + run_host_script.

Asserts the netro plugin is loaded and enabled in the running Indigo
server. Indigo's HTTP API does not expose plugin state — only devices,
variables, actionGroups, controlPages, logs, triggers, schedules — so
plugin queries go through the IOM via `indigo-host -e <script>`
(wrapped by TestingBase's `run_host_script`).

Note on script convention: `indigo-host -e` wraps the script as a
function body. `print()` in that context goes to Indigo's event log,
not the subprocess stdout — use `return` to send a value back. See
upstream `tests/shared/utils.py:get_install_folder` for the same
pattern.

Plugin object API used here is documented in
`/indigo:dev` → `docs/plugin-dev/api/iom/command-namespaces.md`:
`indigo.server.getPlugin(pluginId)` returns a plugin object exposing
`isInstalled()`, `isEnabled()`, `isRunning()`.
"""
from shared import APIBase
from shared.utils import run_host_script


class TestNetroPluginLoaded(APIBase):
    def test_netro_is_loaded_and_enabled(self):
        script = (
            f"plugin = indigo.server.getPlugin('{self.plugin_id}')\n"
            f"if plugin is None:\n"
            f"    return 'state=missing'\n"
            f"return (\n"
            f"    f'state=found'\n"
            f"    f'|installed={{plugin.isInstalled()}}'\n"
            f"    f'|enabled={{plugin.isEnabled()}}'\n"
            f"    f'|running={{plugin.isRunning()}}'\n"
            f")\n"
        )
        result = run_host_script(script)
        self.assertIn(
            "state=found",
            result,
            f"netro plugin {self.plugin_id} not registered with Indigo. "
            f"indigo-host returned: {result!r}",
        )
        self.assertIn(
            "enabled=True",
            result,
            f"netro plugin found but not enabled. "
            f"indigo-host returned: {result!r}",
        )
        self.assertIn(
            "running=True",
            result,
            f"netro plugin enabled but not running. "
            f"indigo-host returned: {result!r}",
        )
