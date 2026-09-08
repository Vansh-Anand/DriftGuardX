# Controlled Retrieval Replications

Generated locally on 2026-09-08 using real BEIR SciFact records. These are controlled
BM25 executions, not sandbox-worker, production-canary or patentability evidence.

| Seed | Eligible queries | Regressing query/fault pairs | Neutral BCRB | Oracle BCRB | Wrong-prior BCRB | Fixed order | Random |
|---|---:|---:|---:|---:|---:|---:|---:|
| 42 | 30 | 75 | 2.6800 | 1.0000 | 2.8533 | 2.6800 | 2.4533 |
| 7 | 30 | 72 | 2.6806 | 1.0000 | 2.8472 | 2.6806 | 2.5833 |

Strategy columns are mean executed replays per query/fault pair. Every included
case was recovered by the candidate set. Inclusion requires clean-baseline success
and a regressing fault, so this is not a general recovery-rate estimate.

Neutral priors produce the same order as fixed ordering in this configuration.
The oracle receives the answer, making its advantage unsuitable as evidence of
learned diagnosis. Wrong priors are adverse controls. Statistics in summary.json
use equal-weight query means across faults, which differ from the pair-weighted
means in this table. Repeated seeds can share queries; do not pool them as independent.

## Artifacts

- scifact_seed42.json and scifact_seed7.json retain complete trials, dataset and
  implementation hashes, seed, Git state, limitations and paired statistics.
- summary.json includes original-file SHA-256, manifest hashes, per-fault counts,
  aggregates and comparisons. Both records declare dirty source state honestly.

Verify with:

```text
uv run python scripts/verify_controlled_evidence.py results/patent_review/scifact_seed42.json results/patent_review/scifact_seed7.json
```

Verification establishes internal consistency only. A party can modify data and
recompute unkeyed hashes; this is not independent experimental attestation.
