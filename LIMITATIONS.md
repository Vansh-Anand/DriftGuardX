# DriftGuard-X: Claims-Safe Limitations

This document serves to transparently bound the epistemic and causal claims that DriftGuard-X can reliably make. 

## 1. Causal Diagnosis Limitations
- **Correlational Bounds:** While our directed acyclic graph (DAG) can isolate which versions of a component executed prior to an error, we can only infer *potential* causation until a `ReplayEpisode` is run.
- **Intervention Confounders:** In `ReplayEpisode`s, we pin versions of all components except the target. However, if external provider settings (e.g. OpenAI's internal non-deterministic changes) drift concurrently, the reliability delta might be incorrectly attributed to our component version change.

## 2. False Positives & Calibration
- **Statistical Baselines:** Our metrics (e.g. KS-Test, PSI) assume stable underlying data distributions. Real-world conceptual drift (where the true positive class definition changes over time) will naturally increase our False Positive Rate (FPR).
- **Hard Thresholds:** Even with the dynamic thresholding in `calibration.py`, edge-cases in the distribution tail will trigger `LOW` or `MEDIUM` severity symptoms. 
- **Visibility:** We intentionally DO NOT filter out False Positives from the Drift Timeline UI or Symptom Registry; they are retained for auditing.

## 3. Privacy & Redaction
- **Pydantic Model Limits:** When `privacy_mode` is set to `METADATA_ONLY`, it is physically impossible for the detectors to run content-aware rules (like contradiction or faithfulness), because the raw outputs are replaced by `output_hash`. 
- **Leakage Risks:** Although we redact standard PII, we do not guarantee semantic privacy (e.g. the model leaking a company secret that isn't formatted like standard PII).

## 4. Reproducibility
- While `TraceArtifact` preserves seeds and provider configs, black-box APIs do not guarantee exact bit-for-bit reproducibility over long time horizons. Therefore, older traces may exhibit different downstream effects if replayed months later.

## 5. Security and Adversarial Hardening
- **Adversarial Resilience:** The prototype framework has undergone a 20-point adversarial hardening sweep addressing cryptographic integrity (Merkle DAG canonicalization), policy bypass via Unicode encoding, cross-tenant memory isolation, and Replay Engine resource exhaustion.
- **Production Scale Security:** While these defenses hold at the prototype phase, the system remains a research vehicle. Deep canonicalization, complex AST-level execution limits, and multi-node tenant separation must be subjected to ongoing review if scaled to a distributed production setting.
- **Algorithmic Confidence:** Heuristics and semantic boundary detectors have been augmented, but sophisticated prompt injections and semantic adversarial attacks on the evaluation models themselves remain an active research limitation.
