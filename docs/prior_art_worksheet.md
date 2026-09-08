# Preliminary Prior-Art Review

Review date: 2026-09-08. Target jurisdiction: India (user supplied).
This is a bounded technical search, not an exhaustive patent search or a legal novelty opinion.
No filing or priority date for DriftGuard-X has been supplied. Dates below must be
compared with that date by the patent agent; publication is not evidence of grant.

## Search record

Public web search and primary-source reads used these query families:
- counterfactual replay root cause analysis microservices budget bandit patent
- site.patents.google.com counterfactual root cause replay
- Bandits with Knapsacks
- Graph Attention Networks
- conformal prediction calibration finite sample
- in-toto cryptographic provenance

No unpublished applications, comprehensive Indian patent-family search, claim
construction, prosecution history, or freedom-to-operate search was completed.

## References and technical overlap

| ID | Primary reference and date | Observed overlap | Implication for the draft |
|---|---|---|---|
| P1 | [CN121681201A](https://patents.google.com/patent/CN121681201A/en), published 2026-03-17; listed filing 2025-12-10 | Dependency topology, counterfactual interventions, root-node selection, environment reconstruction, isolated replay repair; description also covers read-only storage snapshots. | Broad diagnosis-plus-sandbox-repair scope has substantial overlap. Read the original-language claims and investigate its family before asserting a distinction. |
| R1 | [Bandits with Knapsacks](https://arxiv.org/abs/1305.2545), submitted 2013-05-11 | Exploration with resource budgets and reward feedback. | Budgeted bandit selection itself is established; renaming it BCRB supplies no technical distinction. |
| R2 | [Graph Attention Networks](https://arxiv.org/abs/1710.10903), submitted 2017-10-30, ICLR 2018 | Attention over graph neighborhoods and stacked graph layers. | The GAT architecture and head counts are implementation choices, not established novelty. |
| R3 | [Counterfactual-based Root Cause Analysis for Dynamical Systems](https://arxiv.org/abs/2406.08106), 2024 preprint | Counterfactual reasoning for root-cause diagnosis. | Counterfactual attribution alone needs a narrower distinction. Only the abstract-level scope was assessed here. |
| R4 | [A Gentle Introduction to Conformal Prediction](https://arxiv.org/abs/2107.07511), submitted 2021-07-15 | Calibration residuals, finite-sample quantiles, conditional coverage assumptions. | Conformal bounds are established. The corrected implementation is a correctness fix, not a claimed new statistical method. |
| R5 | [in-toto](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias), USENIX Security 2019 | Cryptographic verification of software provenance through deployment. | Signed provenance and deployment verification are established; any recovery-specific distinction needs an element-by-element analysis. |

## Candidate distinction for investigation

The candidate system combination is the enforcement of state-bound replay eligibility,
resource admission with a rollback reserve, provenance-preserving measured outcomes,
and recovery authorization tied to evidence and deployment conditions.

This is an engineering hypothesis about possible claim scope. The search does not
establish that the combination is novel or non-obvious, and separate implemented
modules do not prove a completely integrated embodiment. The patent agent should
compare P1 plus R1 and R5, including motivation to combine them. Resource containment,
hashing, signatures, GATs, and confidence intervals individually are not presented as
new inventions.

## Disclosure chronology

- Existing GitHub pushes are recorded in the project history.
- Repository visibility when each push occurred: unverified.
- Earliest public disclosure, demonstration, paper, sale, or submission: user input required.
- Existing application, priority date, applicants and human inventors: user input required.
- A Git commit timestamp does not establish a patent priority date.
