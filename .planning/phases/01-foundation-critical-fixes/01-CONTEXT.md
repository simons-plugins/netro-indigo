# Phase 1: Foundation & Critical Fixes - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish robust error handling infrastructure, development workflow tooling, and code quality standards. This phase fixes silent failures in the plugin (particularly in runConcurrentThread), sets up GitHub workflow for tracking work, and improves Pylint score from 8.75 to 9.0+. The foundation enables all subsequent refactoring phases to proceed with confidence.

</domain>

<decisions>
## Implementation Decisions

### GitHub Workflow

- **Commit linking**: Use auto-close keywords ("Closes #123", "Fixes #124") in commit messages to automatically close issues
- **Issue content**: Minimal approach - issues contain just enough to track work (title + brief description). Details live in code and commit messages, not duplicated in issues.

### Claude's Discretion

- Issue granularity (per-criterion, per-phase, or logical groupings)
- Branch strategy (feature branches, per-issue branches, or direct to main)
- Exception handling strategy (granularity, custom vs built-in exceptions)
- Logging approach (verbosity levels, context inclusion, debug mode behavior)
- Pylint configuration (strict vs permissive start, rule selections, violation handling)

</decisions>

<specifics>
## Specific Ideas

No specific requirements - open to standard approaches for error handling, logging, and code quality tooling.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation-critical-fixes*
*Context gathered: 2026-02-01*
