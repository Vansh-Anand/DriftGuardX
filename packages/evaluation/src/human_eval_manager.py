import csv
import json
from pathlib import Path
from typing import Any

from packages.evaluation.src.human_eval_schema import EvaluationItem


class HumanEvalManager:
    def __init__(self, data_dir: str = "/tmp/human_eval_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.items_file = self.data_dir / "evaluation_items.json"
        self.items: dict[str, EvaluationItem] = {}
        self._load()

    def _load(self):
        if self.items_file.exists():
            with open(self.items_file, encoding='utf-8') as f:
                data = json.load(f)
                self.items = {k: EvaluationItem(**v) for k, v in data.items()}

    def _save(self):
        with open(self.items_file, 'w', encoding='utf-8') as f:
            json.dump({k: v.dict() for k, v in self.items.items()}, f, default=str, indent=2)

    def add_raw_trace(self, trace_id: str, trace_data: dict[str, Any]):
        """
        Takes a raw trace, blinds it, and adds it to the evaluation pool.
        """
        # Blinding: strip out baseline identifiers, scheduler info, etc.
        blinded_context = {
            "query": trace_data.get("query", ""),
            "generated_answer": trace_data.get("generated_answer", ""),
            "retrieved_evidence": trace_data.get("retrieved_evidence", []),
            "predicted_root_cause": trace_data.get("predicted_root_cause", ""),
            "proposed_recovery_action": trace_data.get("proposed_recovery_action", ""),
            "fault_type": trace_data.get("fault_type", "UNKNOWN") # kept for stratification, hidden from reviewer in CLI
        }

        self.items[trace_id] = EvaluationItem(
            item_id=trace_id,
            blinded_trace_context=blinded_context
        )
        self._save()

    def get_pending_items(self) -> list[EvaluationItem]:
        """Returns items that have less than 2 reviews."""
        return [item for item in self.items.values() if len(item.annotations) < 2]

    def submit_annotation(self, item_id: str, annotation):
        """Records an annotation and checks for adjudication."""
        if item_id in self.items:
            self.items[item_id].annotations.append(annotation)
            self._save()

    def export_anonymized_results(self, output_format: str = "csv", out_path: str = None):
        """
        Exports the results. The schema natively uses random UUIDs for reviewers,
        so no PII is included in the export.
        """
        out_path = out_path or str(self.data_dir / f"anonymized_export.{output_format}")

        flat_records = []
        for item in self.items.values():
            base_rec = {
                "item_id": item.item_id,
                "needs_adjudication": item.needs_adjudication,
                "review_count": len(item.annotations)
            }

            for i, ann in enumerate(item.annotations):
                rec = base_rec.copy()
                rec.update({
                    "annotation_idx": i,
                    "reviewer_pseudonym": str(ann.reviewer_id),
                    "answer_correct": ann.answer_correct,
                    "evidence_sufficient": ann.evidence_sufficient,
                    "hallucinated": ann.hallucinated,
                    "predicted_root_cause_correct": ann.predicted_root_cause_correct,
                    "proposed_recovery_safe": ann.proposed_recovery_safe,
                    "comments": ann.comments
                })
                flat_records.append(rec)

        if output_format == "csv":
            if not flat_records:
                return
            keys = flat_records[0].keys()
            with open(out_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(flat_records)
        else:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(flat_records, f, indent=2)

        return out_path
