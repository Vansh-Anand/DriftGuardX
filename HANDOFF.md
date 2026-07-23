# Mandatory Antigravity Handoff Format

**1. Stage completed:** Prompt 14 — Grounded Natural-Language Recovery Rationale
**2. Estimated cumulative completion after verified gates:** 89%

**3. Repository audit and design decisions:**
The `packages/rationale` module was introduced to generate natural language explanations for recovery actions. To ensure strict adherence to safety rules, `RationaleInputContract` requires strongly-typed structured evidence. Four deterministic fallback templates (`OPERATOR_SUMMARY`, `EXECUTIVE_SUMMARY`, `INCIDENT_TICKET`, `PATENT_NOTE`) are provided as the baseline logic. An optional LLM adapter (`llm.py`) takes redacted data (scrubbed of raw UUIDs) and translates it to fluent text using strict zero-hallucination prompts. Before the LLM output is accepted, it passes through `validator.py`, which ensures every version tag and metric float exists exactly within the input contract bounds; if it fails, the deterministic template silently takes over.

**4. Files created, modified, migrated, or deprecated:**
- `packages/rationale/src/models.py` (New: `RationaleInputContract`, `RationaleStyle`, `RationaleOutput`)
- `packages/rationale/src/templates.py` (New: Deterministic generators for 4 unique styles)
- `packages/rationale/src/llm.py` (New: Optional LLM adapter with redaction and execution controls)
- `packages/rationale/src/validator.py` (New: Strict factual validator catching hallucinated metrics and version tags)
- `apps/web/app/rationale/page.tsx` (New: React UI parsing inline evidence citations)
- `tests/e2e/test_rationale_eval.py` (New: Validation and evaluation test suite)
- `CHANGELOG.md` (Modified: Added v0.14.0)

**5. Commands executed and exact test/results summary:**
```
$env:PYTHONPATH="."; python -m pytest tests/e2e/test_rationale_eval.py -v -s
10 passed in 0.18s

Tests:
  test_template_operator_summary                  PASSED
  test_template_patent_note                       PASSED
  test_validator_detects_hallucinated_metric      PASSED
  test_validator_detects_hallucinated_version     PASSED
  test_validator_detects_missing_component        PASSED
  test_validator_passes_valid_text                PASSED
  test_llm_fallback_on_hallucination              PASSED
  test_llm_success_path                           PASSED
  test_disabled_llm                               PASSED
  test_undercertified_logic                       PASSED
```

**6. Demonstration or experiment artifacts with paths:**
- `apps/web/app/rationale/page.tsx` — Dynamic React viewer distinguishing between LLM-generated vs. template outputs and highlighting cited artifacts.

**7. Security, privacy, safety, and IP-disclosure checks:**
- Hallucination Control: Any numeric claim or unapproved version tag triggered by the LLM is forcibly rejected by `validator.py`, switching instantly to safe deterministic templates.
- Patent Note: The `PATENT_NOTE` template explicitly prevents the generation of legal clearance or global safety claims.
- Redaction: The input payload scrubs all potential system-specific UUID traces (`run_id`, `tenant_id`) before they enter the LLM layer via `llm.py/redact_input`.

**8. Known limitations and failed/negative results:**
- By design, the module intentionally rejects "creative" or overly verbose explanations if they use numbers outside the known metric bounds. Consequently, users will see the deterministic fallback triggered often if a deployed LLM is uncalibrated or overly verbose.

**9. Data migrations and rollback notes:**
- No database migrations were required, as this module calculates outputs statelessly upon request, or it could be attached to existing JSON columns inside the `RepairDecision`.

**10. HANDOFF.md updated; next prompt:** 15
