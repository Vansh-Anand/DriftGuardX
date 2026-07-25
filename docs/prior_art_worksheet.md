# Prior-Art Search Worksheet
*PRIVATE - NOT LEGAL ADVICE - DRAFTING TEMPLATE*

Use this worksheet to conduct preliminary clearance and novelty searches before drafting claims. **This does not constitute a clearance opinion.**

## 1. CPC / IPC Classification Candidates
*To be confirmed by patent counsel.*
- **G06F 11/36** (Software testing and debugging)
- **G06N 5/00** (Machine learning / AI reliability)
- **G06N 20/00** (Machine learning)
- **H04L 9/00** (Cryptographic mechanisms, hash chains)

## 2. Keywords and Search Strings
- (AI OR "machine learning" OR LLM OR "language model") AND (drift OR hallucination OR anomaly) AND (causal OR counterfactual OR "root cause") AND ("multi-armed bandit" OR "MAB" OR knapsack OR "budget constrained")
- (pipeline OR DAG OR "directed acyclic graph") AND (rollback OR recovery OR "optimistic lock") AND ("hash chain" OR ledger OR cryptographic)

## 3. Assignee Watchlist
- Google LLC
- Microsoft Corporation
- IBM
- Amazon Technologies
- Anthropic / OpenAI (via published papers, if filed)

## 4. Claim Element Comparison

| Novel DriftGuard-X Element | Closest Prior Art Found | Differences / Technical Advantages |
| :--- | :--- | :--- |
| **Budget-Constrained Counterfactual Replay via Bandit** | [Insert Reference] | Prior art uses exhaustive replay or random perturbation. DG-X uses Knapsack-UCB optimization. |
| **Cross-Layer Drift Diffusion over DAG** | [Insert Reference] | Prior art stops at terminal output scores. DG-X attributes upstream symptoms using fixed PageRank / GAT on traces. |
| **Cryptographic Rollback Certificates** | [Insert Reference] | Prior art issues alerts. DG-X issues verifiable, immutable state-change certificates with domain separators. |
| **Policy-Gated Optimistic Recovery** | [Insert Reference] | Prior art performs manual rollbacks. DG-X applies hierarchical tightening-only deterministic policies before executing pre-verified alternate modules. |
