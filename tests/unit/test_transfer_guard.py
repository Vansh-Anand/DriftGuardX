from packages.policy.src.transfer_guard import (
    CalibrationEvidence,
    ProvenanceEnvelope,
    TransferGuard,
)


from packages.contracts.src.evidence import RecoveryEvidenceKind

def make_env(components: list[str], risk: float = 0.1, kind: RecoveryEvidenceKind = RecoveryEvidenceKind.PRODUCTION_CANARY, env_hash: str = "abc") -> ProvenanceEnvelope:
    return ProvenanceEnvelope(
        tenant_id="test",
        components=components,
        environment_hash=env_hash,
        calibration_evidence=CalibrationEvidence(
            confidence_interval=0.05, support_size=100, empirical_risk=risk
        ),
        evidence_kind=kind,
    )


def test_jaccard_spoofing_attack_prevented():
    source_prov = make_env(["model:gpt-4"])
    target_prov_spoofed = make_env(
        [
            "model:gpt-4",
            "dummy_node_1",
            "dummy_node_2",
            "dummy_node_3",
            "dummy_node_4",
            "dummy_node_5",
        ]
    )

    guard = TransferGuard("secret_key")
    result = guard._compute_provenance_similarity(source_prov, target_prov_spoofed)

    assert result.score == 0.0
    assert result.unrecognized_penalties == 5


def test_weighted_anchors():
    source_prov = make_env(["model:gpt-4", "tool:search"])
    target_prov1 = make_env(["model:gpt-4", "tool:calc"])
    target_prov2 = make_env(["model:gpt-3.5", "tool:search"])

    guard = TransferGuard("secret_key")
    res1 = guard._compute_provenance_similarity(source_prov, target_prov1)
    res2 = guard._compute_provenance_similarity(source_prov, target_prov2)

    assert res1.score == 0.6
    assert abs(res2.score - (1.0 / 7.0)) < 1e-5
    assert res1.score > res2.score


def test_can_transfer_diagnosis():
    guard = TransferGuard("secret_key")
    source_prov = make_env(["model:gpt-4"], risk=0.1)
    source_prov.signature = source_prov.recompute_signature("secret_key")

    target_prov = make_env(["model:gpt-4"], risk=0.1)
    target_prov.signature = target_prov.recompute_signature("secret_key")

    # Exactly same, low shift
    assert (
        guard.can_transfer_diagnosis(source_prov, target_prov, max_calibration_shift=0.05) is True
    )

def test_synthetic_simulation_rejected():
    guard = TransferGuard("secret_key")
    source_prov = make_env(["model:gpt-4"], risk=0.1, kind=RecoveryEvidenceKind.SYNTHETIC_SIMULATION)
    source_prov.signature = source_prov.recompute_signature("secret_key")
    
    target_prov = make_env(["model:gpt-4"], risk=0.1, kind=RecoveryEvidenceKind.SYNTHETIC_SIMULATION)
    target_prov.signature = target_prov.recompute_signature("secret_key")
    
    assert guard.can_transfer_diagnosis(source_prov, target_prov) is False

    # Calibration shifted too much
    target_prov_shift = make_env(["model:gpt-4"], risk=0.5, env_hash="def")
    target_prov_shift.signature = target_prov_shift.recompute_signature("secret_key")
    assert (
        guard.can_transfer_diagnosis(source_prov, target_prov_shift, max_calibration_shift=0.05)
        is False
    )

    # Provenance similarity is too low (spoofed)
    target_prov_spoofed = make_env(["model:gpt-4", "dummy_1", "dummy_2"], risk=0.1, env_hash="def")
    target_prov_spoofed.signature = target_prov_spoofed.recompute_signature("secret_key")
    assert (
        guard.can_transfer_diagnosis(
            source_prov, target_prov_spoofed, max_calibration_shift=0.05, similarity_threshold=0.8
        )
        is False
    )
