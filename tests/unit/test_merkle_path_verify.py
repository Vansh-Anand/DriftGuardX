"""
Unit tests: Merkle-DAG verify_path().
Tests path integrity verification from leaf to root, tamper detection at
interior nodes, cycle detection, and missing ancestor handling.
"""
from packages.replay.src.merkle_dag import MerkleDAGStore


class TestMerklePathVerify:
    def setup_method(self):
        self.store = MerkleDAGStore()

    def test_single_node_path_to_self(self):
        self.store.add_node("root", {"data": "root_payload"})
        assert self.store.verify_path("root", "root")

    def test_linear_chain_valid(self):
        self.store.add_node("n1", {"data": "n1"})
        self.store.add_node("n2", {"data": "n2"}, parent_ids=["n1"])
        self.store.add_node("n3", {"data": "n3"}, parent_ids=["n2"])
        assert self.store.verify_path("n3", "n1")

    def test_path_missing_intermediate_returns_false(self):
        """A node that doesn't exist in the store makes the path invalid."""
        self.store.add_node("root", {"data": "root"})
        self.store.add_node("child", {"data": "child"}, parent_ids=["root"])
        # Manually corrupt the hash index to simulate a missing ancestor
        corrupt_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        child_node = self.store.get_node("child")
        # Override the parent hash to point to a non-existent node
        child_node.parent_hashes = [corrupt_hash]
        assert not self.store.verify_path("child", "root")

    def test_tampered_leaf_fails_verify_chain(self):
        self.store.add_node("root", {"data": "root"})
        self.store.add_node("leaf", {"data": "original"}, parent_ids=["root"])
        leaf = self.store.get_node("leaf")
        # Tamper with the payload directly
        leaf.payload = {"data": "TAMPERED"}
        assert not self.store.verify_chain("leaf")
        assert not self.store.verify_path("leaf", "root")

    def test_tampered_interior_node_detected_by_path(self):
        self.store.add_node("root", {"data": "root"})
        self.store.add_node("middle", {"data": "middle"}, parent_ids=["root"])
        self.store.add_node("leaf", {"data": "leaf"}, parent_ids=["middle"])
        # Tamper the middle node
        middle = self.store.get_node("middle")
        middle.payload = {"data": "TAMPERED_MIDDLE"}
        # verify_chain on leaf might still pass (it only checks its own hash),
        # but verify_path must catch the tampered middle node
        assert not self.store.verify_path("leaf", "root")

    def test_wrong_root_returns_false(self):
        self.store.add_node("actual_root", {"data": "r"})
        self.store.add_node("child", {"data": "c"}, parent_ids=["actual_root"])
        # verify_path to a wrong root should fail (path never reaches "wrong_root")
        self.store.add_node("wrong_root", {"data": "wr"})
        assert not self.store.verify_path("child", "wrong_root")

    def test_full_dag_verification_passes_clean(self):
        self.store.add_node("n1", {"val": 1})
        self.store.add_node("n2", {"val": 2}, parent_ids=["n1"])
        self.store.add_node("n3", {"val": 3}, parent_ids=["n2"])
        assert self.store.verify_full_dag()

    def test_full_dag_verification_fails_after_tamper(self):
        self.store.add_node("n1", {"val": 1})
        self.store.add_node("n2", {"val": 2}, parent_ids=["n1"])
        # Tamper n1
        self.store.get_node("n1").payload = {"val": 999}
        assert not self.store.verify_full_dag()
