from packages.bcrb.src.calibration import BCRBCalibrator


def test_bcrb_calibrator_dynamic_prior_weighting():
    calibrator = BCRBCalibrator()

    # Default weights: 0.45 GAT, 0.35 Diffusion, 0.20 Symptom
    prior, prov = calibrator.estimate_prior(gat_score=0.8, diff_score=0.6, symptom_score=0.4)
    expected = (0.8 * 0.45) + (0.6 * 0.35) + (0.4 * 0.20)
    assert abs(prior - expected) < 1e-4
    assert prov["calibration_status"] == "data_driven"

    # Calibration with historical empirical accuracy
    accuracy_history = {
        "gat_accuracy": 0.9,
        "diffusion_accuracy": 0.4,
        "symptom_accuracy": 0.3,
    }
    prior_adj, prov_adj = calibrator.estimate_prior(
        gat_score=0.8, diff_score=0.6, symptom_score=0.4, historical_accuracy=accuracy_history
    )
    # GAT has higher accuracy, so prior_adj should weigh GAT higher
    assert prov_adj["weights_used"]["gat"] > 0.5
    assert prior_adj > prior


def test_bcrb_calibrator_cost_and_blast_radius():
    calibrator = BCRBCalibrator()

    # Historical spans data-driven cost estimation
    historical_spans = [
        {"component_type": "generator", "cost_usd": 0.042},
        {"component_type": "generator", "cost_usd": 0.038},
        {"component_type": "retriever", "cost_usd": 0.011},
    ]

    cost_gen = calibrator.estimate_candidate_cost("generator", historical_spans=historical_spans)
    assert abs(cost_gen - 0.040) < 1e-4

    cost_ret = calibrator.estimate_candidate_cost("retriever", historical_spans=historical_spans)
    assert abs(cost_ret - 0.011) < 1e-4

    # Blast radius calculated from causal DAG connectivity
    all_nodes = ["node_retriever", "node_reasoning", "node_tool", "node_response"]
    edges = [
        ("node_retriever", "node_reasoning"),
        ("node_reasoning", "node_tool"),
        ("node_tool", "node_response"),
    ]

    # Retriever reaches 3 downstream nodes out of 4 -> blast radius 3/4 = 0.75
    blast_retriever = calibrator.estimate_candidate_blast_radius(
        "retriever", causal_graph_edges=edges, all_nodes=all_nodes
    )
    assert blast_retriever == 0.75

    # Tool only reaches response (1/4 = 0.25)
    blast_tool = calibrator.estimate_candidate_blast_radius(
        "tool", causal_graph_edges=edges, all_nodes=all_nodes
    )
    assert blast_tool == 0.25


def test_bcrb_calibrated_likelihoods():
    calibrator = BCRBCalibrator()

    # High recovery delta -> high likelihood given cause
    p_cause_high, p_not_high = calibrator.calculate_calibrated_likelihoods(0.8)
    assert p_cause_high > 0.85
    assert p_not_high < 0.25

    # Low/negative recovery delta -> low likelihood given cause
    p_cause_low, p_not_low = calibrator.calculate_calibrated_likelihoods(-0.1)
    assert p_cause_low < 0.15
    assert p_not_low > 0.85
