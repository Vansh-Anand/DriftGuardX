"""
DriftGuard-X v2 — Dataset Generators for Replay
PRIVATE — All Rights Reserved.
"""
import json
import os

from packages.replay.src.faults import get_all_fault_recipes


def generate_fault_episodes(output_dir: str):
    """
    Generates synthetic traces exhibiting the 18 fault taxonomies.
    These are saved to local immutable JSON lines for benchmarking.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, "synthetic_fault_episodes.jsonl")

    recipes = get_all_fault_recipes()

    with open(out_file, "w") as f:
        for recipe in recipes:
            episode = {
                "episode_id": f"ep_{recipe.id}",
                "fault_injected": recipe.id,
                "metadata": {
                    "affected_component": recipe.affected_component_type,
                    "risk_tier": recipe.risk_tier,
                },
                "trace_digest": f"fake_digest_for_{recipe.id}",
                "capsule": {
                    "query": f"Test query for {recipe.name}",
                    "random_seeds": {"global": 42}
                }
            }
            f.write(json.dumps(episode) + "\n")

    return out_file
