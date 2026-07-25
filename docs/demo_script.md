# DriftGuard-X Controlled Demo Script
*Estimated Duration: 5-7 Minutes*

## 1. Setup & Ingestion (Minute 0-1)
**Action**: Run the golden demo ingestion script.
`python tests/e2e/test_golden_demo.py`
**Talking Point**: "We simulate a pipeline where the retrieval index has gone stale, causing the generation step to hallucinate based on old data. The system automatically ingests these traces and forms a Causal Reliability Graph."

## 2. Diffusion & Diagnosis (Minute 1-2)
**Action**: Navigate to `http://localhost:3000/diffusion`.
**Talking Point**: "Notice the terminal failure (hallucination). Our diffusion engine propagates this symptom backward across the DAG. It highlights the *Retriever Node* as the high-probability causal root, ignoring the generation node which was just acting on bad data."

## 3. Budget-Constrained Replay (Minute 2-4)
**Action**: Navigate to `http://localhost:3000/scheduler/[id]`.
**Talking Point**: "Exhaustively testing fixes is too expensive. We trigger the BCRB scheduler. Watch the Knapsack-UCB algorithm efficiently prune the search space, focusing only on the highest value interventions (e.g., rolling back the index) within our compute budget."

## 4. Policy-Gated Rollback (Minute 4-5)
**Action**: Navigate to `http://localhost:3000/policy`.
**Talking Point**: "The optimal intervention is found, but high-risk actions default to deny. The system queues a Rollback Request. As an Administrator, I approve this via the tightened hierarchy rules."

## 5. Certification & Independent Verification (Minute 5-7)
**Action**: Execute verification in CLI: `python apps/cli/verifier.py --bundle [bundle_path]`.
**Talking Point**: "The recovery is executed and state is restored. DriftGuard-X emits an Ed25519 signed Certificate of Recovery. This CLI tool verifies the cryptographic hash-chain independently of the database, providing non-repudiable audit evidence."
