import pytest
from packages.policy.src.transfer_guard import TransferGuard, SimilarityResult

def test_jaccard_spoofing_attack_prevented():
    # Source graph has only one model
    source_prov = {"components": ["model:gpt-4"]}
    
    # Target graph has the same model but an attacker injected a bunch of dummy unrecognized nodes
    # In a naive intersection/union approach without penalties, the union is large if we don't filter them.
    # If we DO filter them, intersection is {"model:gpt-4"} and union is {"model:gpt-4"}, score is 1.0!
    # The new TransferGuard penalizes unrecognized nodes to prevent this.
    target_prov_spoofed = {
        "components": [
            "model:gpt-4",
            "dummy_node_1",
            "dummy_node_2",
            "dummy_node_3",
            "dummy_node_4",
            "dummy_node_5"
        ]
    }
    
    result = TransferGuard._compute_provenance_similarity(source_prov, target_prov_spoofed)
    
    # 5 dummy nodes * 0.2 penalty = 1.0 penalty. Raw score 1.0 - 1.0 = 0.0.
    assert result.score == 0.0
    assert result.unrecognized_penalties == 5

def test_weighted_anchors():
    # Model match should be worth more than a tool match
    source_prov = {"components": ["model:gpt-4", "tool:search"]}
    target_prov1 = {"components": ["model:gpt-4", "tool:calc"]} # model matches, tool differs
    target_prov2 = {"components": ["model:gpt-3.5", "tool:search"]} # model differs, tool matches
    
    # model weight = 3.0, tool weight = 1.0. Total union weight = 3.0 + 1.0 + 1.0 = 5.0
    # For target 1, intersection = model (3.0). Score = 3.0 / 5.0 = 0.6
    res1 = TransferGuard._compute_provenance_similarity(source_prov, target_prov1)
    
    # For target 2, intersection = tool (1.0). Union = model1 (3) + model2 (3) + tool (1) = 7.0. Score = 1.0 / 7.0
    res2 = TransferGuard._compute_provenance_similarity(source_prov, target_prov2)
    
    assert res1.score == 0.6
    assert abs(res2.score - (1.0 / 7.0)) < 1e-5
    assert res1.score > res2.score # Matching the model is more critical than matching a tool

def test_can_transfer_diagnosis():
    source_prov = {"components": ["model:gpt-4"]}
    target_prov = {"components": ["model:gpt-4"]}
    
    # Exactly same, low shift
    assert TransferGuard.can_transfer_diagnosis(
        "tenant_A", "tenant_B", source_prov, target_prov, calibration_shift=0.05
    ) is True
    
    # Calibration shifted too much
    assert TransferGuard.can_transfer_diagnosis(
        "tenant_A", "tenant_B", source_prov, target_prov, calibration_shift=0.5
    ) is False
    
    # Provenance similarity is too low (spoofed)
    target_prov_spoofed = {"components": ["model:gpt-4", "dummy_1", "dummy_2"]}
    assert TransferGuard.can_transfer_diagnosis(
        "tenant_A", "tenant_B", source_prov, target_prov_spoofed, calibration_shift=0.05, similarity_threshold=0.8
    ) is False
