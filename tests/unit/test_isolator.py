import uuid
from packages.isolation.src.isolator import CausalIsolator
from packages.contracts.src.models import ComponentType

def test_causal_isolator_quarantine():
    isolator = CausalIsolator(tenant_id=str(uuid.uuid4()))
    
    # Check default state
    assert isolator.check_invocation_allowed(ComponentType.RETRIEVER) is True
    
    # Apply quarantine
    rule = isolator.apply_quarantine(ComponentType.RETRIEVER, "Quarantined due to data drift")
    
    assert rule.target_component == ComponentType.RETRIEVER
    assert rule.enforce_network_isolation is True
    
    # Check state after quarantine
    assert isolator.check_invocation_allowed(ComponentType.RETRIEVER) is False
    assert isolator.check_invocation_allowed(ComponentType.GENERATOR) is True
    
    active_rules = isolator.list_active_quarantines()
    assert len(active_rules) == 1
    assert active_rules[0].target_component == ComponentType.RETRIEVER
