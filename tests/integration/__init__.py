"""TestingBase live-integration tests for netro.

Run from the dedicated venv (not netro's main env):

    source tests/venv/bin/activate
    pytest tests/integration/

Requires `tests/.env` to exist with a valid Indigo API key. See
`tests/.env.example` for the template, and the `docs/plans/`
design doc for the full pilot context.

If you see `ModuleNotFoundError: No module named 'shared'`, the
TestingBase submodule isn't initialised. Run:

    git submodule update --init
"""
