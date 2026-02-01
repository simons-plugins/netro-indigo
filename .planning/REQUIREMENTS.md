# Requirements: Netro Plugin Refactoring

**Defined:** 2026-02-01
**Core Value:** Maintain reliable, maintainable Indigo plugin with clean, testable code

## v1 Requirements

### Critical Fixes

- [ ] **CRIT-01**: Fix line 827 silent exception handler in runConcurrentThread (polling thread can die silently)
- [ ] **CRIT-02**: Fix incorrect logging levels (using info() for errors, error() for warnings)
- [ ] **CRIT-03**: Add exception logging with full traceback to all bare exception handlers
- [ ] **CRIT-04**: Replace silent `pass` in exception handlers with proper error logging

### Code Quality

- [ ] **QUAL-01**: Replace bare `except (Exception,):` at line 131 with specific exception types
- [ ] **QUAL-02**: Replace bare `except (Exception,):` at line 827 with specific exception types + logging
- [ ] **QUAL-03**: Replace bare `except (Exception,):` at line 1230 with specific exception types
- [ ] **QUAL-04**: Replace bare `except (Exception,):` at line 1285 with specific exception types
- [ ] **QUAL-05**: Replace bare `except (Exception,):` at line 1306 with specific exception types
- [ ] **QUAL-06**: Convert remaining .format() calls to f-strings (3 locations)
- [ ] **QUAL-07**: Remove unused variables (lines 1402, 1473, 1534)
- [ ] **QUAL-08**: Fix bare tuple syntax `except (Exception,):` to `except Exception:`
- [ ] **QUAL-09**: Achieve Pylint score 9.0+ (currently 8.75/10)
- [ ] **QUAL-10**: Add pyproject.toml with Pylint configuration

### Module Organization

- [ ] **MOD-01**: Extract constants.py (API URLs, defaults, enums) ~80 lines
- [ ] **MOD-02**: Extract exceptions.py (custom exception classes) ~30 lines
- [ ] **MOD-03**: Extract utils.py (timestamp parsing, helper functions) ~100 lines
- [x] **MOD-04**: Extract api_client.py (Netro API HTTP client + throttle management) ~250 lines
- [x] **MOD-05**: Extract validators.py (all validation functions) ~200 lines
- [ ] **MOD-06**: Extract device_handlers.py (SprinklerHandler, WhispererHandler) ~260 lines
- [ ] **MOD-07**: Refactor plugin.py to slim coordinator ~400 lines (down from 1635)
- [ ] **MOD-08**: Update all imports throughout codebase
- [ ] **MOD-09**: Verify no circular import dependencies
- [ ] **MOD-10**: Update test imports for new module structure

### Testing Expansion

- [ ] **TEST-01**: Add 15 Whisperer sensor tests (cover lines 663-690, 735-789)
- [ ] **TEST-02**: Add 8 network timeout error tests (requests.Timeout scenarios)
- [ ] **TEST-03**: Add 6 API 500 error tests (server error handling)
- [ ] **TEST-04**: Add 6 malformed JSON response tests
- [ ] **TEST-05**: Add 6 unicode edge case tests (device names, zone names)
- [ ] **TEST-06**: Add 6 empty data edge case tests (empty moisture lists, no schedules)
- [ ] **TEST-07**: Add 6 schedule parsing edge case tests (multiple formats, missing fields)
- [ ] **TEST-08**: Add 6 concurrent thread tests (StopThread handling, loop termination)
- [ ] **TEST-09**: Update test coverage configuration to track new modules
- [ ] **TEST-10**: Achieve 87% overall test coverage (up from 70%)

### API Reliability

- [x] **API-01**: Implement proactive throttle prevention (pause polling when tokens <100)
- [x] **API-02**: Add token budget tracking and warnings at <200 remaining
- [x] **API-03**: Persist throttle state to pluginPrefs (survives plugin restart)
- [x] **API-04**: Restore throttle state from pluginPrefs on startup
- [x] **API-05**: Add API response schema validation (detect format changes)
- [x] **API-06**: Create schema definitions for all API endpoints
- [x] **API-07**: Add version detection for API responses
- [x] **API-08**: Log warnings when API response format doesn't match schema

### Development Workflow

- [ ] **DEV-01**: Create GitHub issues for all major work items
- [ ] **DEV-02**: Structure work into atomic commits tied to issue numbers
- [ ] **DEV-03**: Update CHANGELOG.md with issue references
- [ ] **DEV-04**: Create feature branches for each module extraction
- [ ] **DEV-05**: Submit PRs for review before merging to main

## v2 Requirements

Deferred to future release:

### Performance Optimizations

- **PERF-01**: Per-device polling interval configuration
- **PERF-02**: Parallel device polling with thread pool
- **PERF-03**: Connection pooling for API requests

### Features

- **FEAT-01**: Historical moisture data graphing
- **FEAT-02**: Zone usage statistics and reporting
- **FEAT-03**: Custom schedule templates

## Out of Scope

| Feature | Reason |
|---------|--------|
| Serial number redaction in logs | Local Mac logs, not a security concern for this use case |
| Multi-controller support | Already implemented in v2.0 with device-level serial numbers |
| Webhook support | Netro API doesn't provide webhooks |
| Real-time push notifications | API is polling-only |
| Mobile app integration | Plugin is Indigo-only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CRIT-01 | Phase 1 | Complete |
| CRIT-02 | Phase 1 | Complete |
| CRIT-03 | Phase 1 | Complete |
| CRIT-04 | Phase 1 | Complete |
| QUAL-01 | Phase 1 | Complete |
| QUAL-02 | Phase 1 | Complete |
| QUAL-03 | Phase 1 | Complete |
| QUAL-04 | Phase 1 | Complete |
| QUAL-05 | Phase 1 | Complete |
| QUAL-06 | Phase 1 | Complete |
| QUAL-07 | Phase 1 | Complete |
| QUAL-08 | Phase 1 | Complete |
| QUAL-09 | Phase 1 | Complete |
| QUAL-10 | Phase 1 | Complete |
| MOD-01 | Phase 2 | Complete |
| MOD-02 | Phase 2 | Complete |
| MOD-03 | Phase 2 | Complete |
| MOD-04 | Phase 3 | Complete |
| MOD-05 | Phase 4 | Complete |
| MOD-06 | Phase 5 | Pending |
| MOD-07 | Phase 5 | Pending |
| MOD-08 | Phase 5 | Pending |
| MOD-09 | Phase 5 | Pending |
| MOD-10 | Phase 5 | Pending |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 6 | Pending |
| TEST-05 | Phase 6 | Pending |
| TEST-06 | Phase 6 | Pending |
| TEST-07 | Phase 6 | Pending |
| TEST-08 | Phase 6 | Pending |
| TEST-09 | Phase 6 | Pending |
| TEST-10 | Phase 6 | Pending |
| API-01 | Phase 3 | Complete |
| API-02 | Phase 3 | Complete |
| API-03 | Phase 3 | Complete |
| API-04 | Phase 3 | Complete |
| API-05 | Phase 3 | Complete |
| API-06 | Phase 3 | Complete |
| API-07 | Phase 3 | Complete |
| API-08 | Phase 3 | Complete |
| DEV-01 | Phase 1 | Complete |
| DEV-02 | Phase 1 | Complete |
| DEV-03 | Phase 1 | Complete |
| DEV-04 | Phase 2 | Complete |
| DEV-05 | Phase 2 | Complete |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 47
- Unmapped: 0

---
*Requirements defined: 2026-02-01*
*Last updated: 2026-02-01 after roadmap creation*
