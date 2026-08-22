# DriftGuard-X: Reviewer Instructions

Thank you for participating in the DriftGuard-X human evaluation. 

## Workflow

1. **Read the Rubric:** Before you begin, thoroughly review `human_evaluation_rubric.md`. Keep it open as a reference.
2. **Read the Privacy Policy:** Review `privacy_and_consent.md` to understand how your data is anonymized.
3. **Start the CLI:**
   From the root of the repository, run the evaluation script:
   ```bash
   python apps/cli/human_eval.py
   ```
4. **Provide Consent:**
   The terminal will prompt you to consent to the privacy policy. Type `y` and press Enter.
5. **Evaluate Items:**
   The script will present you with an evaluation item. Read the provided Context carefully.
   Answer the 5 Yes/No questions by typing `y` or `n`.
6. **Comments (Optional):**
   If you feel your judgment requires explanation (especially if an item is ambiguous), provide a brief comment on step 6. Press Enter to skip.
7. **Complete:**
   The script will loop until all pending items assigned to you are completed. You can exit at any time using `Ctrl+C`; your progress is saved automatically after every item.
8. **Export:**
   Once finished, the manager will export an anonymized CSV file. This file contains no PII and is safe to share with the research team.
