import pytest

from packages.replay.src.merkle_dag import MerkleDAGStore


def test_dag_fork_diamond_shape():
    """
    Test a diamond DAG: A -> B, A -> C, B -> D, C -> D.
    Forking A should result in exactly one fork of D, with both new B and C parents.
    """
    store = MerkleDAGStore()
    store.add_node("A", {"val": "A"})
    store.add_node("B", {"val": "B"}, parent_ids=["A"])
    store.add_node("C", {"val": "C"}, parent_ids=["A"])
    store.add_node("D", {"val": "D"}, parent_ids=["B", "C"])

    # Fork A
    store.fork_lineage("A", {"val": "A2"})

    # D_fork should have B_fork and C_fork as parents
    d_fork = store.get_node("D_fork")
    assert d_fork is not None

    b_fork = store.get_node("B_fork")
    c_fork = store.get_node("C_fork")

    assert b_fork.node_hash in d_fork.parent_hashes
    assert c_fork.node_hash in d_fork.parent_hashes
    assert len(d_fork.parent_hashes) == 2

def test_dag_fork_linear_deep():
    """
    Test that we do not hit RecursionError for very deep chains (e.g. 5000 nodes).
    """
    store = MerkleDAGStore()

    store.add_node("node_0", {"val": 0})
    for i in range(1, 2000): # 2000 is enough to break default 1000 recursion limit
        store.add_node(f"node_{i}", {"val": i}, parent_ids=[f"node_{i-1}"])

    store.fork_lineage("node_0", {"val": "new_0"})

    # Check the last node was forked
    last_fork = store.get_node("node_1999_fork")
    assert last_fork is not None
    assert last_fork.payload == {"val": 1999}

def test_dag_cycle_protection():
    """
    Test that the system raises ValueError if a cycle is somehow introduced.
    We will hack a cycle in.
    """
    store = MerkleDAGStore()
    node_a = store.add_node("A", {"val": "A"})
    node_b = store.add_node("B", {"val": "B"}, parent_ids=["A"])
    node_c = store.add_node("C", {"val": "C"}, parent_ids=["B"])

    # Hack a cycle: C -> A
    node_a.parent_hashes.append(node_c.node_hash)
    node_a.children_ids.add("C")
    node_c.children_ids.add("A")

    with pytest.raises(ValueError, match="Cycle detected"):
        store.fork_lineage("A", {"val": "A2"})
