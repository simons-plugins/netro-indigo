# Phase 1: Foundation & Critical Fixes - Research

**Researched:** 2026-02-01
**Domain:** Python exception handling, logging, Pylint configuration, GitHub workflow
**Confidence:** HIGH

## Summary

This phase focuses on three interconnected areas: fixing critical silent failure bugs in exception handling, establishing code quality tooling with Pylint, and setting up GitHub workflow for issue tracking. Research confirms that Python's standard library provides all needed functionality - no external dependencies required beyond what's already in use.

The critical bug at line 827 (`except (Exception,): pass`) in `runConcurrentThread()` is a textbook anti-pattern that can cause the polling thread to die silently. The fix is straightforward: use `logger.exception()` which automatically captures the full traceback at ERROR level.

Pylint 4.0.4 is already installed and supports pyproject.toml configuration natively. GitHub's auto-close keywords (Closes #, Fixes #, Resolves #) work exactly as expected when commits merge to the default branch.

**Primary recommendation:** Replace all `except (Exception,): pass` patterns with specific exception types plus `logger.exception()` for automatic traceback capture, configure Pylint via pyproject.toml with minimal overrides from defaults.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| logging (stdlib) | Python 3.10+ | Exception logging with traceback | Built-in, `logger.exception()` auto-captures traceback |
| pylint | 4.0.4 | Static code analysis | Already installed, industry standard |
| pyproject.toml | PEP 518 | Project configuration | Modern Python standard, replaces setup.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| traceback (stdlib) | Python 3.10+ | Manual traceback formatting | Only when `logger.exception()` insufficient |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| logger.exception() | logger.error(exc_info=True) | Equivalent, but exception() is clearer intent |
| pyproject.toml | .pylintrc | pyproject.toml is modern standard, consolidates config |
| pylint | ruff | ruff is faster but pylint has better message explanations |

**Installation:**
No installation needed - all tools already available.

## Architecture Patterns

### Recommended Exception Handling Pattern

**Pattern 1: Specific Exceptions with Traceback Logging**
**What:** Catch specific exceptions, log with full traceback, then handle appropriately
**When to use:** All exception handlers in production code
**Example:**
```python
# Source: Python logging documentation
try:
    self._update_from_netro()
except requests.exceptions.ConnectionError:
    self.logger.exception("Connection error during Netro update")
    # Continue loop - recoverable
except requests.exceptions.Timeout:
    self.logger.exception("Timeout during Netro update")
    # Continue loop - recoverable
except Exception:
    self.logger.exception("Unexpected error during Netro update")
    # Continue loop but log for debugging
```

**Pattern 2: Thread Loop Exception Handling**
**What:** Never let exceptions kill a background thread silently
**When to use:** `runConcurrentThread()` and similar polling loops
**Example:**
```python
# Source: Indigo plugin best practices + Python logging docs
def runConcurrentThread(self):
    self.logger.debug("Starting concurrent thread")
    while True:
        try:
            self._update_from_netro()
        except self.StopThread:
            # Clean exit requested by Indigo
            raise
        except Exception:
            # Log but continue - thread must not die silently
            self.logger.exception("Error in polling loop, will retry")
        self.sleep(self.pollingInterval * 60)
```

**Pattern 3: Validation Exception Handling**
**What:** Catch specific parsing/validation errors, return sensible defaults
**When to use:** User input validation, API response parsing
**Example:**
```python
# For get_key_from_dict() at line 127
try:
    return a_dict[a_key]
except KeyError:
    return "unavailable from API"
except (TypeError, AttributeError) as exc:
    self.logger.debug(f"Error accessing key {a_key}: {exc}")
    return "unknown error"
```

### Anti-Patterns to Avoid
- **`except (Exception,): pass`** - Silent failure, impossible to debug. Always log.
- **`except Exception: pass`** - Same problem without the tuple syntax.
- **`except:` (bare)** - Catches SystemExit/KeyboardInterrupt, never use.
- **`logger.error()` without `exc_info=True`** - Loses traceback. Use `logger.exception()` instead.
- **Using info() for errors** - Wrong severity level confuses log analysis.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Traceback capture | Manual traceback.format_exc() everywhere | logger.exception() | Automatic, includes full context |
| Exception chaining | Re-raising without context | `raise NewError() from exc` | Preserves original traceback |
| Log formatting | Custom exception formatters | Python logging defaults | Consistent, well-tested |

**Key insight:** Python's logging module already solves exception logging perfectly. `logger.exception()` is specifically designed for use in except blocks and automatically captures the full traceback.

## Common Pitfalls

### Pitfall 1: Silent Thread Death
**What goes wrong:** Background thread dies, plugin appears to work but stops updating
**Why it happens:** `except (Exception,): pass` swallows all errors silently
**How to avoid:** Always use `logger.exception()` in thread loops, re-raise `StopThread`
**Warning signs:** Device states stop updating, no errors in log

### Pitfall 2: Wrong Log Level
**What goes wrong:** Errors logged as info(), warnings logged as error()
**Why it happens:** Copy-paste errors, inconsistent conventions
**How to avoid:** Follow severity guidelines strictly:
- DEBUG: Diagnostic details for developers
- INFO: Normal operation confirmations
- WARNING: Unexpected but recoverable situations
- ERROR: Failed operations that need attention
- CRITICAL: System cannot continue
**Warning signs:** Important errors buried in info-level noise

### Pitfall 3: Lost Traceback
**What goes wrong:** Exception logged but no stack trace to debug
**Why it happens:** Using `logger.error(str(exc))` instead of `logger.exception()`
**How to avoid:** Always use `logger.exception()` in except blocks
**Warning signs:** Log shows error message but not where it occurred

### Pitfall 4: Exception Tuple Syntax
**What goes wrong:** `except (Exception,):` is valid but unusual, confuses readers
**Why it happens:** Leftover from Python 2 or copy-paste
**How to avoid:** Use `except Exception:` (no tuple for single type)
**Warning signs:** Pylint warning about bare-except-tuple

### Pitfall 5: Pylint Score Gaming
**What goes wrong:** Disabling too many checks to hit score target
**Why it happens:** Focus on score instead of actual code quality
**How to avoid:** Start with minimal config, only disable rules with good reason
**Warning signs:** Long disable lists, pylint: disable comments everywhere

## Code Examples

### Critical Fix: runConcurrentThread (Line 827)
```python
# BEFORE (broken - thread can die silently)
def runConcurrentThread(self):
    self.logger.debug("Starting concurrent thread")
    while True:
        try:
            self._update_from_netro()
        except (Exception,):
            pass
        self.sleep(self.pollingInterval * 60)

# AFTER (correct - exceptions logged, thread continues)
def runConcurrentThread(self):
    """Background thread that polls Netro API periodically."""
    self.logger.debug("Starting concurrent thread")
    while True:
        try:
            self._update_from_netro()
        except self.StopThread:
            # Clean shutdown requested by Indigo
            self.logger.debug("Concurrent thread stopping")
            raise
        except Exception:
            # Log error but continue polling - thread must not die
            self.logger.exception("Error in polling loop, will retry next interval")
        self.sleep(self.pollingInterval * 60)
```

### Fix: get_key_from_dict (Line 127-132)
```python
# BEFORE
def get_key_from_dict(a_key, a_dict):
    try:
        return a_dict[a_key]
    except KeyError:
        return "unavailable from API"
    except (Exception,):
        return "unknown error"

# AFTER
def get_key_from_dict(a_key, a_dict):
    """Safely get value from dictionary with graceful error handling."""
    try:
        return a_dict[a_key]
    except KeyError:
        return "unavailable from API"
    except (TypeError, AttributeError):
        # dict is None or not a dict
        return "unknown error"
```

### Fix: triggerStopProcessing (Line 1228-1232)
```python
# BEFORE
def triggerStopProcessing(self, trigger):
    super().triggerStopProcessing(trigger)
    self.logger.debug("Stop processing trigger " + str(trigger.id))
    try:
        del self.triggerDict[trigger.id]
    except (Exception,):
        # the trigger isn't in the list for some reason so just skip it
        pass

# AFTER
def triggerStopProcessing(self, trigger):
    """Called when a trigger is disabled."""
    super().triggerStopProcessing(trigger)
    self.logger.debug(f"Stop processing trigger {trigger.id}")
    try:
        del self.triggerDict[trigger.id]
    except KeyError:
        # Trigger wasn't in dict - already removed or never added
        self.logger.debug(f"Trigger {trigger.id} not found in triggerDict")
```

### Fix: Zone Start Error (Line 1285)
```python
# BEFORE
try:
    self._make_api_call(ZONE_START_URL, request_method="put", data=data)
    self.logger.info(f'sent "{dev.name} - {zoneName}" on')
    dev.updateStateOnServer("activeZone", action.zoneIndex)
except (Exception,):
    # Else log failure but do NOT update state on Indigo Server.
    self.logger.error(f'send "{dev.name} - {zoneName}" on failed')

# AFTER
try:
    self._make_api_call(ZONE_START_URL, request_method="put", data=data)
    self.logger.info(f'sent "{dev.name} - {zoneName}" on')
    dev.updateStateOnServer("activeZone", action.zoneIndex)
except requests.exceptions.RequestException:
    # Network/HTTP error - log and fire trigger
    self.logger.exception(f'send "{dev.name} - {zoneName}" on failed')
    self._fireTrigger("startZoneFailed", dev.id)
except ThrottleDelayError:
    self.logger.warning(f'send "{dev.name} - {zoneName}" throttled')
    self._fireTrigger("startZoneFailed", dev.id)
```

### Convert .format() to f-strings
```python
# Line 587 BEFORE
self.logger.debug("API error: \n{}".format(traceback.format_exc(10)))
# AFTER
self.logger.debug(f"API error: \n{traceback.format_exc(10)}")

# Line 600 BEFORE
zoneNames += (", {}".format(zone["name"]) if len(zoneNames) else zone["name"])
# AFTER
zoneNames += f", {zone['name']}" if zoneNames else zone["name"]

# Line 1379 BEFORE
self.logger.debug("API error: \n{}".format(traceback.format_exc(10)))
# AFTER
self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
```

### pyproject.toml Pylint Configuration
```toml
# Minimal configuration - only override defaults where needed
[tool.pylint.main]
# Target Python version (Indigo 2023.2+ requires 3.10+)
py-version = "3.10"

# Exit with error if score below this
fail-under = 9.0

# Use all available cores
jobs = 0

[tool.pylint.format]
# Match existing codebase style
max-line-length = 120

[tool.pylint.design]
# Plugin has large main class by necessity
max-attributes = 20
max-args = 8

[tool.pylint."messages control"]
# Disable rules that conflict with Indigo plugin patterns
disable = [
    "too-many-lines",           # Single-file plugin by design
    "too-many-public-methods",  # Plugin class requires many callbacks
    "invalid-name",             # Indigo uses camelCase callbacks
]

[tool.pylint.basic]
# Allow Indigo's camelCase callback names
method-rgx = "[a-z_][a-zA-Z0-9_]{2,}$"
```

## GitHub Workflow

### Auto-Close Keywords (Locked Decision)
The following keywords automatically close issues when commit merges to default branch:
- `close`, `closes`, `closed`
- `fix`, `fixes`, `fixed`
- `resolve`, `resolves`, `resolved`

**Syntax:**
```
feat: Add exception logging to runConcurrentThread

Closes #123
```

Or inline: `Fixes #123: Add exception logging to runConcurrentThread`

**Multiple issues:**
```
fix: Replace all bare exception handlers

Fixes #1, fixes #2, closes #3
```

### Recommended Issue Granularity (Claude's Discretion)
Given the minimal approach decision, recommend **logical groupings**:
1. One issue for critical exception handling fixes (CRIT-01 through CRIT-04)
2. One issue for Pylint configuration and score improvement (QUAL-09, QUAL-10)
3. One issue for code cleanup (.format to f-strings, unused variables)

This keeps issues meaningful while avoiding micro-management overhead.

### Branch Strategy (Claude's Discretion)
Recommend **direct to main** for this foundation phase:
- Changes are small, atomic, and low-risk
- Foundation work needed before feature branches make sense
- Each commit is self-contained with tests

For later phases with module extraction, use feature branches.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| .pylintrc file | pyproject.toml [tool.pylint] | Pylint 2.14+ (2022) | Single config file for all tools |
| `logger.error(traceback.format_exc())` | `logger.exception()` | Always available | Cleaner, automatic context |
| `except Exception, e:` | `except Exception as e:` | Python 3.0 (2008) | Required for Python 3 |
| `except (Exception,):` | `except Exception:` | Python 3.0 | Tuple syntax unnecessary for single type |

**Deprecated/outdated:**
- `.pylintrc` files: Still work but pyproject.toml is preferred
- `traceback.format_exc()` in logging: `logger.exception()` is better
- `%` formatting in log messages: f-strings allowed since Python 3.6, but `%` still valid

## Open Questions

None for this phase - all technical questions resolved through research.

## Sources

### Primary (HIGH confidence)
- [Python logging documentation](https://docs.python.org/3/library/logging.html) - logger.exception(), exc_info parameter
- [Pylint documentation](https://pylint.readthedocs.io/en/stable/user_guide/configuration/index.html) - pyproject.toml configuration
- [GitHub documentation](https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue) - auto-close keywords

### Secondary (MEDIUM confidence)
- [Real Python exception handling](https://realpython.com/ref/best-practices/exception-handling/) - best practices patterns
- [Pylint examples/pyproject.toml](https://github.com/pylint-dev/pylint/blob/main/examples/pyproject.toml) - configuration format

### Tertiary (LOW confidence)
- Web search results for "Python logging best practices 2026" - general community consensus

## Metadata

**Confidence breakdown:**
- Exception handling patterns: HIGH - verified with Python official docs
- Pylint configuration: HIGH - verified with Pylint official docs and installed version
- GitHub workflow: HIGH - verified with GitHub official docs
- Code examples: HIGH - based on actual codebase analysis

**Research date:** 2026-02-01
**Valid until:** 2026-03-01 (30 days - stable domain, unlikely to change)
