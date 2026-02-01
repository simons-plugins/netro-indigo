# Phase 4: Validators - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract configuration validation logic from plugin.py into a standalone validators.py module. Create pure validation functions that handle all validateConfigUi callbacks. API response validation is out of scope for this phase (handled in Phase 3: API Client).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

The user has given Claude full discretion for all validation design decisions:

- **Return values**: Choose pattern that works best with Indigo's validateConfigUi callback signature and makes plugin.py cleaner
- **Error handling**: Decide whether to return tuples, raise exceptions, or use another pattern based on clarity and consistency with existing error handling
- **Value sanitization**: Determine whether validators should only check (pure read) or also sanitize/normalize values (strip whitespace, apply defaults) based on what makes the code cleaner
- **Cross-field validation**: Structure validators to handle field dependencies in whatever way makes most sense given the actual validation requirements in the code

### Constraints from Roadmap

- Validation logic must be pure functions with no side effects (success criteria #2)
- Plugin configuration validation must work identically to before extraction (success criteria #3)
- Focus on extracting validate*ConfigUi functions mentioned in the codebase

</decisions>

<specifics>
## Specific Ideas

No specific requirements from user - open to standard approaches that align with Indigo plugin patterns.

**Implementation guidance:**
- Review existing validateConfigUi callbacks in plugin.py to understand current patterns
- Maintain compatibility with Indigo's UI callback expectations
- Ensure error messages shown in Indigo's UI remain clear and helpful
- Keep validators testable and focused on validation logic only

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

Note: API response validation is handled separately in Phase 3 (API Client), not in this validators phase.

</deferred>

---

*Phase: 04-validators*
*Context gathered: 2026-02-01*
