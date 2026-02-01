# Netro Plugin Refactoring

## What This Is

A comprehensive refactoring of the Netro Sprinklers Indigo plugin to eliminate technical debt and improve code quality. The plugin currently works in production (v2.0 with multi-controller support) but has accumulated quality issues including bare exception handlers, monolithic architecture (1635 lines), and gaps in test coverage.

## Core Value

Maintain a reliable, maintainable Indigo plugin for Netro smart irrigation control with clean, testable code that's easy to debug and extend.

## Requirements

### Validated

**Existing capabilities - must preserve:**
- ✓ Multi-controller support (device-level serial numbers) - existing (v2.0)
- ✓ Zone control (start, stop, duration) - existing
- ✓ Real-time status monitoring (online/offline) - existing
- ✓ Soil moisture tracking per zone - existing
- ✓ Schedule visibility (next watering time/zone) - existing
- ✓ Rain delay and standby mode - existing
- ✓ Whisperer soil sensor support - existing
- ✓ API rate limit detection and throttling - existing
- ✓ Comprehensive test suite (64 tests, 70% coverage) - existing
- ✓ Detailed documentation (CLAUDE.md, API_NOTES.md, TROUBLESHOOTING.md) - existing

### Active

**Code Quality & Architecture:**
- [ ] Eliminate all bare exception handlers (replace with specific exceptions + logging)
- [ ] Split plugin.py into focused modules (api_client, validators, utils, actions)
- [ ] Achieve Pylint 8.0+ score (currently 6.5/10)
- [ ] Extract timestamp parsing to single utility function
- [ ] Improve logging consistency (correct levels: debug/info/warning/error)
- [ ] Use f-strings exclusively for string formatting

**Error Handling & Reliability:**
- [ ] Add specific exception handling throughout (requests.Timeout, KeyError, ValueError)
- [ ] Log all exceptions with full traceback
- [ ] Wrap individual API calls with targeted error handling
- [ ] Fix concurrent thread exception handling (no silent failures)
- [ ] Implement proactive rate limit prevention (pause polling when tokens <100)
- [ ] Persist throttle state across plugin restarts

**Testing:**
- [ ] Add comprehensive Whisperer sensor tests
- [ ] Add error path tests (network timeouts, API 500s, malformed JSON)
- [ ] Add edge case tests (unicode names, empty moisture lists, schedule parsing)
- [ ] Improve overall coverage to 75%+

**Features:**
- [ ] API response schema validation (detect format changes early)

**Development Workflow:**
- [ ] Create GitHub issues for all major work items
- [ ] Tie commits and PRs to GitHub issues
- [ ] Update CHANGELOG.md with issue references

### Out of Scope

- Multi-controller support — Already implemented in v2.0 (device-level serial numbers)
- Serial number redaction in logs — Local Mac logs, not a security concern
- Per-device polling configuration — Not needed, adds complexity
- Historical moisture graphing — Feature request for future version
- Zone usage statistics — Feature request for future version
- Webhook support — Netro API doesn't provide webhooks

## Context

**Existing Architecture:**
- Production-ready Indigo plugin (v2.0, Jan 2025 overhaul)
- Python 3.10+ for Indigo 2023.2+
- Single 1635-line plugin.py file
- Netro Public API v1 integration (REST with 2000 calls/day limit)
- Supports Sprite, Pixie, Spark controllers + Whisperer sensors
- 64 automated tests (pytest), >70% coverage
- Tested with real hardware ("Clark Castle Spark" controller, 16 zones)
- GitHub repository: https://github.com/simons-plugins/netro-indigo

**Known Issues Identified:**
- 10 documented API quirks (timestamp formats, response structures)
- Bare exception handlers at 5+ locations (masks bugs)
- Large single file (hard to navigate, test, maintain)
- Timestamp parsing duplicated in 4+ places
- Whisperer sensor code undertested
- Throttle state lost on plugin restart
- Thread dies silently on errors (line 827: `except (Exception,): pass`)

**Tech Stack:**
- Python 3.10+
- requests 2.32.5 (HTTP client)
- pytest + pytest-cov + pytest-mock (testing)
- Indigo Plugin API 3.0+

## Constraints

- **Python version**: 3.10+ — Can use modern Python features (type hints, match/case, etc.)
- **Indigo compatibility**: Must work with Indigo 2023.2+
- **API limits**: Netro API has 2000 calls/day limit — Must respect rate limits
- **Breaking changes**: Acceptable — Users can reconfigure if needed for better architecture
- **Hardware testing**: Real Netro controller available for validation
- **Issue tracking**: Use GitHub issues, tie PRs to issues

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Comprehensive refactoring (not conservative fixes) | Technical debt has accumulated; better to fix properly than patch | — Pending |
| Breaking changes allowed | Clean architecture more important than backward compatibility | — Pending |
| Skip serial number redaction | Local logs on user's Mac, not a security concern | ✓ Good |
| Skip multi-controller work | Already implemented in v2.0 with device-level serial numbers | ✓ Good |
| Python 3.10+ features OK | Indigo 2023.2+ requirement already in place | — Pending |
| Use GitHub issues for tracking | Maintains history, ties code to issues, good for open source | — Pending |

---
*Last updated: 2026-02-01 after initialization*
