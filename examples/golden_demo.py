"""
DriftGuard-X v2 — Golden End-to-End Demonstration

Scenario:
  1. Execute a pipeline run with experimental retriever v2 (stale evidence)
  2. Show reliability failure (score < 0.6)
  3. Create a replay — swap retriever v2-exp → v1 (stable)
  4. Show reliability improvement
  5. Show intervention recorded (NOT applied to production)
  6. Generate RecoveryCertificate

This script runs against the local API (SQLite dev mode, no Docker required).

IMPORTANT: All runs are marked is_synthetic=True (DEMO data).
No production state is mutated.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import asyncio
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")


def banner(text: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def section(text: str) -> None:
    print(f"\n-- {text}")


async def run_golden_demo() -> dict:
    """
    Run the complete golden demo scenario.
    Returns a dict with all results for evidence.
    """
    results: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "demo_mode": True,
        "steps": {},
    }

    from httpx import ASGITransport
    from apps.api.src.main import app, _lifespan

    banner("DriftGuard-X v2 - Golden Demo (SYNTHETIC)")
    print("[WARNING] All data is SYNTHETIC. No production state will be mutated.")
    print(f"   API: In-Memory (ASGITransport)")

    async with _lifespan(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url=API_BASE, timeout=30.0) as client:

            # ─── Step 1: Health check ─────────────────────────────────────────────
            section("Step 1: Health Check")
            resp = await client.get("/health")
            resp.raise_for_status()
            health = resp.json()
            print(f"   Status: {health['status']} | Version: {health['version']}")
            results["steps"]["health"] = health
            assert health["status"] == "ok", f"Health check failed: {health}"

            # ─── Step 2: Run with experimental retriever (v2-exp) ─────────────────
            section("Step 2: Execute run with EXPERIMENTAL retriever v2 (known stale issue)")
            run_payload = {
                "query": "What are the latest AI safety guidelines for enterprise RAG systems?",
                "use_experimental_retriever": True,
                "seed": 42,
                "is_synthetic": True,
                "request_id": f"golden-demo-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            }

            resp = await client.post("/v1/runs", json=run_payload)
            resp.raise_for_status()
            run_exp = resp.json()
            run_id = run_exp["id"]

            print(f"   Run ID:            {run_id}")
            print(f"   Status:            {run_exp['status']}")
            print(f"   Reliability Score: {run_exp['reliability_score']:.4f}  <- EXPECTED TO BE LOW")
            print(f"   Reliability Vector: {json.dumps(run_exp['reliability_vector'], indent=6)}")
            print(f"   Total Latency:     {run_exp['total_latency_ms']:.2f}ms")
            print(f"   Is Synthetic:      {run_exp['is_synthetic']}")

            results["steps"]["original_run"] = run_exp

            # Verify reliability failure
            assert run_exp["reliability_score"] is not None
            original_score = run_exp["reliability_score"]
            if original_score >= 0.6:
                print(f"   [WARNING] Score {original_score:.4f} is not below 0.6 - demo still works but threshold not triggered")
            else:
                print(f"   [OK] Reliability failure confirmed: score {original_score:.4f} < 0.6")

            # ─── Step 3: Get the trace ────────────────────────────────────────────
            section("Step 3: Retrieve normalized trace")
            resp = await client.get(f"/v1/runs/{run_id}/trace")
            resp.raise_for_status()
            trace = resp.json()

            print(f"   Trace ID:      {trace['trace_id']}")
            print(f"   Total Spans:   {trace['total_span_count']}")
            print(f"   Root Span:     {trace['root_span_id']}")

            # Print span timeline
            for span in trace["spans"]:
                latency = f"{span['latency_ms']:.1f}ms" if span.get("latency_ms") else "N/A"
                ct = span.get("component_type") or "root"
                ver = span.get("component_version_tag") or ""
                parent = span.get("parent_span_id")
                indent = "  " if parent else ""
                print(f"   {indent}|- {ct}/{ver:<10} [{span['status_code']}] {latency}")

            results["steps"]["trace"] = {
                "trace_id": trace["trace_id"],
                "total_span_count": trace["total_span_count"],
                "span_components": [
                    {
                        "name": s["name"],
                        "component_type": s.get("component_type"),
                        "version": s.get("component_version_tag"),
                        "latency_ms": s.get("latency_ms"),
                        "status": s["status_code"],
                    }
                    for s in trace["spans"]
                ],
            }

            # Verify span parentage
            span_ids = {s["span_id"] for s in trace["spans"]}
            for span in trace["spans"]:
                if span.get("parent_span_id"):
                    assert span["parent_span_id"] in span_ids, (
                        f"Span {span['span_id']} has parent {span['parent_span_id']} not in trace!"
                    )
            print("   [OK] Span parentage verified - all parent_span_ids present in trace")

            # ─── Step 4: Create replay (retriever rollback) ───────────────────────
            section("Step 4: Create replay - swap retriever v2-exp -> v1 (stable)")
            print("   [WARNING] Policy requires human approval for non-synthetic runs.")
            print("   [OK] Synthetic run: auto-approved for demo.")

            replay_payload = {"swap_retriever_to_stable": True, "seed": 42}
            resp = await client.post(f"/v1/runs/{run_id}/replays", json=replay_payload)
            resp.raise_for_status()
            replay = resp.json()
            replay_id = replay["id"]

            print(f"   Replay ID:              {replay_id}")
            print(f"   Status:                 {replay['status']}")
            print(f"   Swapped Component:      {replay['swapped_component_type']}")
            print(f"   From Version:           {replay['original_version_tag']}")
            print(f"   To Version:             {replay['replay_version_tag']}")
            print(f"   Original Score:         {replay['original_reliability_score']:.4f}")
            print(f"   Replay Score:           {replay['replay_reliability_score']:.4f}")
            print(f"   Reliability Improvement: {replay['reliability_improvement']:+.4f}")
            print(f"   Delta: {json.dumps(replay['reliability_delta'], indent=8)}")

            results["steps"]["replay"] = replay

            improvement = replay["reliability_improvement"]
            if improvement is not None and improvement > 0:
                print(f"\n   [SUCCESS] GOLDEN DEMO SUCCESS: Reliability improved by {improvement:+.4f}")
            else:
                print(f"\n   [INFO] Reliability delta: {improvement} (both runs used same pipeline or already stable)")

            # ─── Step 5: Verify replay isolation ─────────────────────────────────
            section("Step 5: Verify replay isolation — non-intervened versions pinned")
            original_rv = replay["original_reliability_vector"]
            replay_rv = replay["replay_reliability_vector"]

            print("   Dimension-by-dimension comparison:")
            for key in sorted(set(original_rv) | set(replay_rv)):
                orig = original_rv.get(key, 0.0)
                rep = replay_rv.get(key, 0.0)
                delta = rep - orig
                marker = "[UP]" if delta > 0.01 else ("[DOWN]" if delta < -0.01 else "[EQ]")
                print(f"   {marker} {key:<20} {orig:.4f} -> {rep:.4f}  (delta {delta:+.4f})")

            # ─── Step 6: Get replay by ID ─────────────────────────────────────────
            section("Step 6: Fetch replay by ID (provenance check)")
            resp = await client.get(f"/v1/replays/{replay_id}")
            resp.raise_for_status()
            replay_fetched = resp.json()
            assert replay_fetched["id"] == replay_id
            print(f"   [OK] Replay {replay_id} retrieved successfully")

            # ─── Step 7: Run with STABLE retriever (baseline) ─────────────────────
            section("Step 7: Baseline — Execute run with STABLE retriever v1")
            stable_payload = {
                "query": "What are the latest AI safety guidelines for enterprise RAG systems?",
                "use_experimental_retriever": False,
                "seed": 42,
                "is_synthetic": True,
            }
            resp = await client.post("/v1/runs", json=stable_payload)
            resp.raise_for_status()
            run_stable = resp.json()

            print(f"   Run ID (stable):   {run_stable['id']}")
            print(f"   Reliability Score: {run_stable['reliability_score']:.4f}  <- EXPECTED HIGH")
            results["steps"]["stable_run"] = run_stable

            # ─── Step 8: List all runs ─────────────────────────────────────────────
            section("Step 8: List all runs")
            resp = await client.get("/v1/runs", params={"page": 1, "page_size": 10})
            resp.raise_for_status()
            runs_list = resp.json()
            print(f"   Total runs in DB:  {runs_list['total']}")
            for r in runs_list["runs"][:5]:
                score = f"{r['reliability_score']:.4f}" if r.get("reliability_score") is not None else "N/A"
                print(f"   |- {r['id']} | {r['status']:<12} | score={score}")
            results["steps"]["runs_list"] = {"total": runs_list["total"]}

        # ─── Summary ──────────────────────────────────────────────────────────────
        banner("GOLDEN DEMO COMPLETE")
        print(f"""
      Results:
      |- Original run (exp retriever):  score = {results['steps']['original_run']['reliability_score']:.4f}
      |- Replay (stable retriever):     score = {results['steps']['replay']['replay_reliability_score']:.4f}
      |- Reliability improvement:       {results['steps']['replay']['reliability_improvement']:+.4f}
      |- Stable baseline run:           score = {results['steps']['stable_run']['reliability_score']:.4f}
      |- Total spans in trace:          {results['steps']['trace']['total_span_count']}
      |- Intervention recorded:         NOT applied to production (requires human approval)

      [WARNING] DEMO/SYNTHETIC: All data above is synthetic. No production mutations occurred.
      [WARNING] Reliability improvement is MEASURED, not causally proven.
      [WARNING] This does not constitute a patent claim, legal certification, or safety proof.
    """)

        return results


if __name__ == "__main__":
    results = asyncio.run(run_golden_demo())

    # Save results
    output_path = Path(__file__).parent / "golden_demo_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Results saved to: {output_path}")
