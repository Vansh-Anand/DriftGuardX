import pytest
from packages.replay.src.merkle_dag import MerkleNode

def test_set_instability():
    # Because json.dumps uses default=str, sets are converted to string.
    # Python set string representation is unordered and depends on hash seed.
    # A set {1, 2, "a"} might stringify differently.
    import json
    
    class UnstableObj:
        def __str__(self): return "Unstable"
        
    class UnstableObj2:
        def __str__(self): return "Unstable"
        
    # Different objects with same str() representation cause a hash collision!
    # UPDATE: We now strictly require JSON-serializable payloads to prevent this.
    with pytest.raises(TypeError):
        MerkleNode(node_id="n1", payload={"key": UnstableObj()}, version="v1")
        
    # What about tuples vs lists?
    n3 = MerkleNode(node_id="n3", payload={"key": [1, 2]}, version="v1")
    n4 = MerkleNode(node_id="n4", payload={"key": (1, 2)}, version="v1")
    # JSON serializes tuples as lists, which is a known limitation but safe for deterministic trees
    # because lists and tuples convey the same ordered data. We accept this collision.
    assert n3.node_hash == n4.node_hash

def test_dag_cycle_pollution():
    from packages.replay.src.merkle_dag import MerkleDAGStore
    
    store = MerkleDAGStore()
    store.add_node("root", {"data": 0})
    store.add_node("n1", {"data": 1}, ["root"])
    store.add_node("n2", {"data": 2}, ["n1"])
    store.add_node("n3", {"data": 3}, ["n2"])
    
    # Force a cycle maliciously to test fuzzing vulnerability
    # root -> n1 -> n2 -> n3
    #          ^          |
    #          |__________|
    store._nodes["n1"].children_ids.add("n3") 
    store._nodes["n3"].children_ids.add("n1")
    store._nodes["n1"].parent_hashes.append(store._nodes["n3"].node_hash)
    
    # Now try to fork root
    with pytest.raises(ValueError, match="Cycle detected"):
        store.fork_lineage("root", {"data": 10})
        
    # The vulnerability: does it leave orphaned nodes in the graph?
    # Because 'root' has in-degree 0, it gets processed and forked to 'root_fork'
    # before the cycle stops Kahn's algorithm and raises the error!
    assert "root_fork" not in store._nodes, "VULNERABILITY: Graph polluted before cycle detection!"

