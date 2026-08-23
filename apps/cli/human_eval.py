import sys

from packages.evaluation.src.human_eval_manager import HumanEvalManager
from packages.evaluation.src.human_eval_schema import HumanAnnotation, ReviewerSession


def check_consent() -> bool:
    print("="*60)
    print("                 DriftGuard-X Evaluation")
    print("="*60)
    print("Before proceeding, please confirm you have read the Privacy")
    print("and Consent documentation (docs/evaluation/privacy_and_consent.md).")
    print("By proceeding, you agree to submit anonymized evaluation data.")
    print("Your identity is completely pseudonymized.")
    print("="*60)

    # In a real environment, this might block until a remote flag is set.
    # For now, we enforce an explicit Y input.
    ans = input("Do you consent to participate? (y/N): ")
    return ans.strip().lower() == 'y'

def main():
    if not check_consent():
        print("Consent denied. Exiting.")
        sys.exit(0)

    session = ReviewerSession()
    print(f"\nSession started. Your pseudonym ID is: {session.pseudonym_id}\n")

    manager = HumanEvalManager()

    # Mock data generation for testing if empty
    if not manager.items:
        print("No evaluation items found. Generating mock items...")
        for i in range(5):
            manager.add_raw_trace(f"trace_{i}", {
                "query": f"Mock Query {i}",
                "generated_answer": f"Mock Answer {i}",
                "predicted_root_cause": "PROMPT_HALLUCINATION",
                "proposed_recovery_action": "Rollback prompt to v1",
                "fault_type": "PROMPT_REGRESSION"
            })

    pending = manager.get_pending_items()
    print(f"Found {len(pending)} items awaiting review.\n")

    for item in pending:
        # Check if this reviewer has already reviewed this item
        already_reviewed = any(ann.reviewer_id == session.pseudonym_id for ann in item.annotations)
        if already_reviewed:
            continue

        print("-" * 50)
        print(f"Item ID: {item.item_id}")
        print(f"Query: {item.blinded_trace_context['query']}")
        print(f"Generated Answer: {item.blinded_trace_context['generated_answer']}")
        print(f"Predicted Root Cause: {item.blinded_trace_context['predicted_root_cause']}")
        print(f"Proposed Recovery: {item.blinded_trace_context['proposed_recovery_action']}")
        print("-" * 50)

        def ask_bool(prompt: str) -> bool:
            while True:
                ans = input(prompt + " (y/n): ").strip().lower()
                if ans in ['y', 'n']:
                    return ans == 'y'

        ans_corr = ask_bool("1. Is the generated answer correct?")
        ev_suff = ask_bool("2. Is the retrieved evidence sufficient?")
        hallu = ask_bool("3. Is the answer hallucinated?")
        rc_corr = ask_bool("4. Is the predicted root cause correct?")
        rec_safe = ask_bool("5. Is the proposed recovery safe?")

        comments = input("6. Any comments? (optional): ").strip()

        ann = HumanAnnotation(
            reviewer_id=session.pseudonym_id,
            answer_correct=ans_corr,
            evidence_sufficient=ev_suff,
            hallucinated=hallu,
            predicted_root_cause_correct=rc_corr,
            proposed_recovery_safe=rec_safe,
            comments=comments if comments else None
        )

        manager.submit_annotation(item.item_id, ann)
        print("Annotation saved.\n")

    print("No more pending items for your session. Thank you!")
    out = manager.export_anonymized_results()
    print(f"Results exported to: {out}")

if __name__ == "__main__":
    main()
