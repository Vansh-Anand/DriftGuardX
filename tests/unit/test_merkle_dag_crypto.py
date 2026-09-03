import pytest

from packages.replay.src.merkle_dag import MerkleDAGStore, MerkleNode


def test_same_content_same_hash():
    store = MerkleDAGStore()
    node1 = store.add_node("node1", {"key": "value"})
    node2 = store.add_node("node2", {"key": "value"})

    assert node1.node_hash == node2.node_hash
    # Also verify they mapped to the same underlying blob/node in the store if deduplication applies
    assert store.blob_count == 1


def test_leaf_and_internal_domain_separation():
    # An internal node with no payload but parents vs a leaf node with same parents data as payload
    # Let's craft them manually to see if their hashes can collide

    # Leaf with string payload
    leaf = MerkleNode(node_id="leaf", payload="dummy_parent_hash", parent_hashes=[], version="v1")

    # Internal with empty payload but one parent hash equal to "dummy_parent_hash"
    internal = MerkleNode(
        node_id="internal", payload="", parent_hashes=["dummy_parent_hash"], version="v1"
    )

    assert leaf.node_hash != internal.node_hash


def test_child_ordering():
    # parent order should not affect the hash because they are sorted internally
    node1 = MerkleNode(
        node_id="n1", payload="payload", parent_hashes=["hashB", "hashA"], version="v1"
    )
    node2 = MerkleNode(
        node_id="n2", payload="payload", parent_hashes=["hashA", "hashB"], version="v1"
    )

    assert node1.node_hash == node2.node_hash


def test_legacy_version_rejected_or_supported():
    # v0 should generate a different hash than v1 for the same content
    legacy = MerkleNode(node_id="leg", payload="payload", parent_hashes=[], version="v0")
    hardened = MerkleNode(node_id="hard", payload="payload", parent_hashes=[], version="v1")

    assert legacy.node_hash != hardened.node_hash

    # Verify chain works for legacy
    store = MerkleDAGStore()
    store._nodes["leg"] = legacy
    assert store.verify_chain("leg") is True

    # Unknown version should raise ValueError
    with pytest.raises(ValueError, match="Unsupported node version"):
        MerkleNode(node_id="err", payload="payload", parent_hashes=[], version="v999")
