# DriftGuard-X: Evidence-Bounded Technical Effect Evaluation

Verification date: 2026-08-30

All measurements in this document are `synthetic_simulation` evidence. They do not establish production effectiveness, real-world causal identification, or universal safety guarantees.

## Evaluated harness

The seeded causal benchmark uses SciFact test-query text with a deterministic in-process RAG simulation, seven injected fault classes, nineteen candidate components (seven faults plus twelve distractors), five strategies, three sampled queries per fault, and a fixed seed of 42. The corpus, component failures, interventions, costs, and oracle are controlled simulations. No live LLM provider, production trace, or real vector index is used.

The separate deterministic regression harness produced 25 golden executions and 35 injected-fault executions. It is a correctness regression artifact, not comparative-effectiveness evidence.

## Final aggregate results

| Strategy | Confirmed localization accuracy | Localization accuracy | Confirmation rate | Observed mitigation rate | False-confirmation rate | Mean replays | Mean simulated cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| Causal planner | 0.952 | 1.000 | 0.952 | 1.000 | 0.000 | 17.143 | $0.857 |
| Exhaustive | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 9.381 | $0.469 |
| Random | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 12.810 | $0.640 |
| Fixed order | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 9.381 | $0.469 |
| Current BCRB | 0.571 | 0.571 | 0.571 | 0.571 | 0.000 | 11.714 | $0.586 |

The benchmark now counts a baseline result as correct only when the intervention both mitigates the fault and targets the injected ground-truth component. It reports posterior confirmation separately from observed mitigation and retains per-trial observations. Wrong-component interventions are regression-tested not to clear a fault marker.

## Supported technical conclusions

- The process-bound simulation localized all injected root causes at the top of its posterior across these 21 causal-planner trials, but one trial stopped without evidentiary confirmation; confirmed accuracy was therefore 0.952 rather than 1.0.
- No strategy produced a false confirmation in this small deterministic run.
- The causal planner did not demonstrate a replay or cost advantage. Exhaustive and fixed-order search were materially cheaper under this harness's uniform prior and deterministic single-fault design.
- All strategies had the same aggregate modeled blast-radius value (1.9); this run does not support a blast-radius reduction claim.
- Process-bound replay tests demonstrate killability and incremental memory/output enforcement for the tested implementations. Docker isolation remains unexecuted locally because the Docker daemon was unavailable.

## Unsupported claims

These results do not support claims of real-world cost reduction, production isolation, zero false positives, optimality, flawless multi-cause recovery, superiority over exhaustive search, or performance on real RAG systems. Establishing such effects requires preregistered criteria, larger independent datasets, calibrated priors, real controlled replay evidence, uncertainty analysis, and external review.

The exact source state, frozen dependencies, commands, seeds, and result files are bound by the active content-addressed experiment manifest under `releases/2.0.0-rc.1/`.
