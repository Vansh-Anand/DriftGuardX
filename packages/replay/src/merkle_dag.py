"""
DriftGuard-X v2 — Merkle-DAG State Deduplication
Storage Optimization: Structures causal trace logs as a Merkle Directed Acyclic Graph.
Shared payloads (prompts, retrieved documents) are content-addressed and stored
exactly once, dramatically reducing database storage bloat.

Patent Claim: Provides cryptographic tamper-evidence for audit compliance while
enabling content-addressable deduplication of repeated trace payloads, improving
storage efficiency and query latency.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def _length_prefix_encode(data: bytes) -> bytes:
    """Encode bytes with an 8-byte big-endian length prefix to prevent concatenation ambiguity."""
    return len(data).to_bytes(8, "big") + data

def _content_hash(payload: Any) -> str:
    """
    Deterministic SHA-256 content hash of any JSON-serialisable payload.
    Identical payloads always produce identical hashes — the foundation of
    content-addressable storage and tamper-evidence.
    """
    serialised = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


@dataclass
class MerkleNode:
    """
    A single node in the Merkle-DAG.  Its `node_hash` is derived from its own
    payload *and* the hashes of all its parent nodes, making the entire chain
    tamper-evident.
    """
    node_id: str
    payload: Any
    parent_hashes: list[str] = field(default_factory=list)
    version: str = "v1"
    node_hash: str = field(init=False)
    children_ids: set[str] = field(default_factory=set, repr=False, compare=False)

    def __post_init__(self):
        self.node_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Computes the deterministic hash based on node version."""
        if self.version == "v0":
            # Legacy non-separated hash
            is_leaf = len(self.parent_hashes) == 0
            prefix = b"\x00" if is_leaf else b"\x01"
            raw = _content_hash(self.payload) + "".join(sorted(self.parent_hashes))
            return hashlib.sha256(prefix + raw.encode()).hexdigest()

        elif self.version == "v1":
            # Hardened domain separation
            # Removed default=str to prevent hash collisions from unstable string representations
            payload_bytes = json.dumps(self.payload, sort_keys=True).encode("utf-8")
            version_bytes = b"V1"

            if not self.parent_hashes:
                # Leaf Domain
                encoded = b"\x00" + version_bytes + _length_prefix_encode(payload_bytes)
                return hashlib.sha256(encoded).hexdigest()
            else:
                # Internal Domain
                encoded = b"\x01" + version_bytes + _length_prefix_encode(payload_bytes)
                for ph in sorted(self.parent_hashes):
                    encoded += _length_prefix_encode(ph.encode("ascii"))
                return hashlib.sha256(encoded).hexdigest()
        else:
            raise ValueError(f"Unsupported node version: {self.version}")


class MerkleDAGStore:
    """
    Content-addressable store for causal trace states.

    Key properties:
    - Deduplication: identical payloads share a single storage slot keyed by
      their content hash.  Two failure traces that share the same prompt are
      stored once.
    - Tamper-evidence: each node's hash incorporates its ancestry, so any
      post-hoc mutation breaks the chain deterministically.
    - Retrieval: nodes are looked up by their `node_id` (logical name) or
      directly by `node_hash` (content address).
    """

    def __init__(self):
        # Content-addressed blob store: hash -> payload
        self._blobs: dict[str, Any] = {}
        # Node registry: node_id -> MerkleNode
        self._nodes: dict[str, MerkleNode] = {}
        # Reverse index: node_hash -> node_id (for dedup checks)
        self._hash_index: dict[str, str] = {}

    # ── Insertion ─────────────────────────────────────────────────────────────

    def add_node(
        self,
        node_id: str,
        payload: Any,
        parent_ids: list[str] | None = None,
    ) -> MerkleNode:
        """
        Add a new node to the DAG.

        If an identical payload with the same parents already exists the
        existing MerkleNode is returned without creating a duplicate blob.

        Args:
            node_id:    Logical identifier (e.g. trace_id + span_id).
            payload:    Any JSON-serialisable data (prompt, docs, state).
            parent_ids: List of logical node IDs this node depends on.

        Returns:
            The newly created (or de-duplicated existing) MerkleNode.
        """
        parent_hashes = []
        for pid in (parent_ids or []):
            parent_node = self._nodes.get(pid)
            if parent_node:
                parent_hashes.append(parent_node.node_hash)
            else:
                raise ValueError(f"Parent node '{pid}' not found in DAG. Orphaned parents are rejected.")

        node = MerkleNode(
            node_id=node_id,
            payload=payload,
            parent_hashes=parent_hashes,
            version="v1"  # Always create new nodes as v1
        )

        # Reject duplicate ID mutations
        if node_id in self._nodes:
            existing_node = self._nodes[node_id]
            if existing_node.node_hash != node.node_hash:
                raise ValueError(f"Duplicate ID mutation rejected: node_id '{node_id}' already exists with different payload/ancestry.")
            return existing_node

        # Dedup: if exact hash already in store, reuse
        if node.node_hash in self._hash_index:
            existing_id = self._hash_index[node.node_hash]
            return self._nodes[existing_id]

        # Store blob once
        blob_key = _content_hash(payload)
        if blob_key not in self._blobs:
            self._blobs[blob_key] = payload

        self._nodes[node_id] = node
        self._hash_index[node.node_hash] = node_id

        # Track children for lineage forking
        for pid in (parent_ids or []):
            if pid in self._nodes:
                self._nodes[pid].children_ids.add(node_id)

        return node

    def fork_lineage(self, target_node_id: str, new_payload: Any) -> MerkleNode:
        """
        Creates a semantic rollback fork (Update 9). 
        Replaces the payload of the target_node_id and propagates the change 
        down all descendant nodes, creating a parallel validated state branch.
        """
        original_node = self._nodes.get(target_node_id)
        if not original_node:
            raise ValueError(f"Target node {target_node_id} not found.")

        # 1. Find all descendants using BFS, including the target node
        from collections import deque
        descendants = set()
        queue = deque([target_node_id])
        visited_search = {target_node_id}

        while queue:
            curr = queue.popleft()
            descendants.add(curr)

            node = self._nodes.get(curr)
            if node:
                for child in node.children_ids:
                    if child not in visited_search:
                        visited_search.add(child)
                        queue.append(child)

        # 2. Compute in-degrees within the descendant subgraph
        in_degrees = {d: 0 for d in descendants}
        for d in descendants:
            node = self._nodes.get(d)
            if node:
                for child in node.children_ids:
                    if child in descendants:
                        in_degrees[child] += 1

        # 3. Process in topological order
        topo_queue = deque([d for d, deg in in_degrees.items() if deg == 0])
        old_to_new = {}
        processed_count = 0
        forked_node = None

        # Buffer new nodes to prevent graph pollution on cycle failure
        buffered_nodes = []

        while topo_queue:
            curr = topo_queue.popleft()
            processed_count += 1

            curr_node = self._nodes[curr]

            payload = new_payload if curr == target_node_id else curr_node.payload

            new_parent_ids = []
            for p_hash in curr_node.parent_hashes:
                pid = self._hash_index.get(p_hash)
                if pid in old_to_new:
                    new_parent_ids.append(old_to_new[pid])
                elif pid:
                    new_parent_ids.append(pid)

            new_curr_id = f"{curr}_fork"
            buffered_nodes.append((new_curr_id, payload, new_parent_ids))
            old_to_new[curr] = new_curr_id

            for child in curr_node.children_ids:
                if child in in_degrees:
                    in_degrees[child] -= 1
                    if in_degrees[child] == 0:
                        topo_queue.append(child)

        if processed_count != len(descendants):
            raise ValueError("Cycle detected in Merkle-DAG during lineage forking.")

        # 4. Commit buffer if no cycle detected
        for new_id, payload, parent_ids in buffered_nodes:
            new_node = self.add_node(new_id, payload, parent_ids)
            if new_id == f"{target_node_id}_fork":
                forked_node = new_node

        return forked_node

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> MerkleNode | None:
        return self._nodes.get(node_id)

    def get_by_hash(self, node_hash: str) -> MerkleNode | None:
        node_id = self._hash_index.get(node_hash)
        return self._nodes.get(node_id) if node_id else None

    def verify_chain(self, node_id: str) -> bool:
        """
        Verify the cryptographic integrity of a node by recomputing its hash
        from its payload and parent hashes.  Returns False if tampered.
        """
        node = self._nodes.get(node_id)
        if not node:
            return False
        recomputed = MerkleNode(
            node_id=node.node_id,
            payload=node.payload,
            parent_hashes=node.parent_hashes,
            version=node.version
        )
        return recomputed.node_hash == node.node_hash

    def verify_full_dag(self) -> bool:
        """Verify cryptographic integrity of the entire DAG."""
        for node_id in self._nodes:
            if not self.verify_chain(node_id):
                return False
        return True

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def blob_count(self) -> int:
        """Number of unique payloads stored (after deduplication)."""
        return len(self._blobs)

    @property
    def node_count(self) -> int:
        return len(self._nodes)
