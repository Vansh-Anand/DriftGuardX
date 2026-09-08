# India Patent Review Package

Prepared 2026-09-08. User-selected jurisdiction: India.
Status: technical review materials, not a submitted application.

## Start here

- patent_technical_disclosure.md: mechanism, example, limitations, technical diagrams.
- patent_claims_draft.md: revised candidate outline; unsupported earlier claims withdrawn.
- patent_claims_audit.md: source/test support with explicit prototype limits.
- prior_art_worksheet.md: dated primary references, overlap and search limitations.
- patent_india_handoff.md: Indian official sources, filing inputs and unresolved decisions.
- ../results/patent_review/: new benchmark records and their summary.

Older patent_evidence_bcrb.md, patent_evidence_bounds.md, patent_evidence_policy.md,
patent_evidence_matrix.md and patent_figures.md are historical development material.
Their statistics, implementation references and figures must not be used as current
claim support without independent revalidation. This package supersedes their
readiness and novelty assertions.

## Reproduce

From repository root with the existing Python environment:

```text
uv sync --frozen --extra dev --extra infra
uv run pytest -q
uv run python -m apps.cli.run_controlled_replay_benchmark --dataset scifact --max-queries 30 --seed 42 --output results/patent_review/scifact_seed42.json
uv run python -m apps.cli.run_controlled_replay_benchmark --dataset scifact --max-queries 30 --seed 7 --output results/patent_review/scifact_seed7.json
```

The benchmark requires a materialized data/raw/scifact snapshot and fails if it is
missing. It hashes dataset files, relevant implementation files and dirty Git state.
Elapsed time and source metadata may change on rerun; compare retrieval outcomes,
replay counts and statistical protocol, not byte-for-byte artifact equality.
Do not overwrite the historical evidence when generating a new run.

## Experimental interpretation

Schema 2.0 labels oracle, neutral and wrong-prior BCRB ablations separately and
includes fixed-order and random controls. The oracle receives the injected correct
repair, so its advantage cannot establish autonomous fault diagnosis. The neutral
prior receives no fault label. Ordering uses zero exploration with zero reward
updates during ordering; this measures static prioritization, not online learning.

Fault injection and evaluation use real public retrieval data with in-memory
controlled perturbations. The experiment does not invoke the production replay
worker or certify a recovery. Only clean-retrievable queries whose injected fault
reduces recall enter the results. Report the four attempted fault families and
actual per-family counts; faults with no regression are excluded.

Confidence comparisons resample query-level averages across faults because faults
on the same query are dependent. Repeated seeds on the same corpus are replication
checks, not independent populations. Intervals are exploratory, not adjusted for
multiple comparisons; do not pool the seeds as independent evidence.

## Correctness evidence

Numeric-bound regressions reject malformed evidence, check the finite conformal
order statistic, and enumerate all exchangeable holdouts of a fixed residual set.
Capsule tests mutate target state, expiry and compatibility to demonstrate refusal.
These demonstrate implementation behavior under test, not new mathematical results,
an exhaustive security assessment or patentability.
