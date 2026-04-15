# CLAUDE.md — Netro Sprinklers

> **Part of the [Indigo workspace](../CLAUDE.md)** — see root for cross-project map, standards, and tooling.

## Project Identity

- **Name**: Netro Sprinklers
- **Type**: Indigo plugin
- **Shortcut**: `netro`
- **GitHub**: https://github.com/simons-plugins/netro-indigo
- **Language**: Python 3.10+

## Role in the workspace

Netro smart irrigation (Sprite/Pixie/Spark controllers + Whisperer soil sensors). Production-ready with comprehensive pytest suite and pylint + custom Indigo rules in `pyproject.toml` — this is the reference plugin for testing and linting standards in this workspace.

## Related projects

Standalone — no sibling dependencies in this workspace.

## Standards

Inherits workspace standards from [root CLAUDE.md](../CLAUDE.md#common-standards-apply-to-every-project-unless-its-claudemd-overrides). Key points for this project:

- **Version bump per PR**: `Info.plist` `PluginVersion`
- **Testing**: pytest + `pyproject.toml` (pylint with custom Indigo rules, 120-char lines)
- **Merge**: GitHub PR only, never `--admin`, never squash, wait for CI green, wait for user go-ahead.

---

**Detailed architecture, build, and development notes**: see [`docs/CLAUDE.md`](./docs/CLAUDE.md).
