from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from packages.contracts.src.incident_models import IncidentState
from packages.recovery.src.mocks import MockBeliefModel


@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=50)
@given(st.dictionaries(st.text(min_size=1), st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=10))
def test_belief_summation_property(raw_probs):
    """
    Belief: probabilities sum to approximately 1.
    We normalize a raw dictionary of probabilities and verify they sum to 1.
    """
    # Normalize
    total = sum(raw_probs.values())
    if total > 0:
        normalized = {k: v / total for k, v in raw_probs.items()}
    else:
        normalized = {k: 1.0 / len(raw_probs) for k in raw_probs}

    model = MockBeliefModel(normalized)
    state = IncidentState()
    # Execute an update
    updated = model.update_belief(state, [])

    assert abs(sum(updated.values()) - 1.0) < 1e-6
