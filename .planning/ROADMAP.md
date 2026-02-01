# Roadmap: Netro Plugin Refactoring

## Overview

This roadmap transforms a 1635-line monolithic Indigo plugin into a maintainable, modular architecture while improving code quality from 8.75/10 to 9.0+ Pylint. The refactoring proceeds through six phases: first fixing critical silent failures and establishing workflow, then extracting foundation modules (constants, exceptions, utils), followed by the API client with reliability features, validators, device handlers, and finally expanding test coverage to 87%. Each phase delivers a working plugin that can be deployed if needed.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation & Critical Fixes** - Fix silent failures, establish development workflow, quick quality wins
- [ ] **Phase 2: Base Modules** - Extract no-dependency modules (constants, exceptions, utils)
- [ ] **Phase 3: API Client** - Extract API layer with throttle management and reliability features
- [ ] **Phase 4: Validators** - Extract configuration validation functions
- [ ] **Phase 5: Device Handlers** - Extract device update logic, slim plugin.py to coordinator
- [ ] **Phase 6: Testing Expansion** - Expand test coverage to 87%, cover all critical paths

## Phase Details

### Phase 1: Foundation & Critical Fixes
**Goal**: Plugin has no silent failures, development workflow is established, quick quality wins achieved
**Depends on**: Nothing (first phase)
**Requirements**: CRIT-01, CRIT-02, CRIT-03, CRIT-04, DEV-01, DEV-02, DEV-03, DEV-04, DEV-05, QUAL-06, QUAL-07, QUAL-08, QUAL-09, QUAL-10
**Success Criteria** (what must be TRUE):
  1. runConcurrentThread logs all exceptions with full traceback (no silent deaths)
  2. All bare exception handlers replaced with specific exceptions + logging
  3. GitHub issues exist for all major work items
  4. Pylint score is 9.0+ (up from 8.75)
  5. pyproject.toml exists with Pylint configuration
**Plans**: 3 plans in 2 waves

Plans:
- [ ] 01-01-PLAN.md — Fix silent exception handlers with proper logging
- [ ] 01-02-PLAN.md — Create pyproject.toml and fix code style issues
- [ ] 01-03-PLAN.md — Create GitHub issues and commit with issue references

### Phase 2: Base Modules
**Goal**: Foundation modules extracted and tested, proving multi-file pattern works with Indigo
**Depends on**: Phase 1
**Requirements**: MOD-01, MOD-02, MOD-03
**Success Criteria** (what must be TRUE):
  1. constants.py exists with all API URLs, defaults, and enums
  2. exceptions.py exists with custom exception classes for API errors
  3. utils.py exists with timestamp parsing and helper functions
  4. Plugin loads successfully in Indigo with new module structure
  5. All 64 existing tests pass with new imports
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: API Client
**Goal**: API communication isolated in dedicated module with proactive throttle management
**Depends on**: Phase 2
**Requirements**: MOD-04, API-01, API-02, API-03, API-04, API-05, API-06, API-07, API-08
**Success Criteria** (what must be TRUE):
  1. api_client.py exists with NetroAPIClient class handling all HTTP requests
  2. Plugin pauses polling automatically when API tokens drop below 100
  3. Throttle state persists across plugin restarts (saved to pluginPrefs)
  4. API responses are validated against schema, warnings logged on format changes
  5. Token budget warnings logged when remaining tokens drop below 200
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: Validators
**Goal**: Configuration validation extracted to standalone module
**Depends on**: Phase 2 (uses constants)
**Requirements**: MOD-05
**Success Criteria** (what must be TRUE):
  1. validators.py exists with all validate*ConfigUi functions
  2. Validation logic is pure functions with no side effects
  3. Plugin configuration validation works identically to before extraction
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: Device Handlers
**Goal**: Device update logic extracted, plugin.py reduced to slim coordinator (~400 lines)
**Depends on**: Phase 3 (device handlers use API client)
**Requirements**: MOD-06, MOD-07, MOD-08, MOD-09, MOD-10, QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05
**Success Criteria** (what must be TRUE):
  1. device_handlers.py exists with SprinklerHandler and WhispererHandler classes
  2. plugin.py is under 450 lines (down from 1635)
  3. No circular import dependencies exist between modules
  4. All bare `except (Exception,):` handlers replaced with specific exception types
  5. All existing tests pass with updated imports
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

### Phase 6: Testing Expansion
**Goal**: Test coverage expanded to 87%, all critical paths tested
**Depends on**: Phase 5 (tests target final module structure)
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06, TEST-07, TEST-08, TEST-09, TEST-10
**Success Criteria** (what must be TRUE):
  1. Whisperer sensor code has 85%+ test coverage (up from 40%)
  2. Error paths (network timeout, API 500, malformed JSON) have dedicated tests
  3. Edge cases (unicode names, empty lists, schedule parsing) are tested
  4. Overall test coverage is 87%+ (up from 70%)
  5. Test configuration tracks coverage for all new modules
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Critical Fixes | 0/3 | Ready to execute | - |
| 2. Base Modules | 0/TBD | Not started | - |
| 3. API Client | 0/TBD | Not started | - |
| 4. Validators | 0/TBD | Not started | - |
| 5. Device Handlers | 0/TBD | Not started | - |
| 6. Testing Expansion | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-01*
*Phase 1 planned: 2026-02-01*
*Requirements coverage: 47/47 (100%)*
