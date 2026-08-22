# DriftGuard-X Evaluation: Privacy & Informed Consent

**Purpose of the Study:**
This evaluation workflow collects human-labeled judgments on the outputs of the DriftGuard-X RAG system under various fault conditions. The goal is to establish a ground truth for diagnostic accuracy (Root Cause Analysis) and recovery safety.

**What we collect:**
- Your judgments on boolean criteria (e.g., answer correctness, safety).
- Optional free-text comments you provide.
- A randomly generated UUID representing your session.
- A timestamp of when the annotations were submitted.

**What we DO NOT collect:**
- Your name, email address, or any other personally identifying information (PII).
- IP addresses or geolocation data.
- System or device fingerprints.

**Anonymity & Blinding:**
Your session is bound to a pseudonym (a UUID). There is no mechanism to reverse-map this UUID to your identity. The evaluation items you review are also blinded; you will not know which baseline model or scheduler generated the response you are reviewing.

**Data Usage:**
The exported data will be used strictly in aggregate (JSON/CSV format) to calculate Cohen’s Kappa (inter-rater reliability), system precision/recall, and safety bounds.

## Consent Declaration
By executing `python apps/cli/human_eval.py` and answering `y` to the consent prompt, you acknowledge that:
1. You have read and understood this privacy policy.
2. You voluntarily participate in this evaluation.
3. You understand that because the data is strictly anonymized upon collection, it cannot be selectively withdrawn after submission.

**DO NOT begin collecting participant data until the Project Owner formally approves this workflow.**
