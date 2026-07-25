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
from typing import Any, Dict, List, Optional, Set


def _content_hash(payload: Any) -> str:
    """
    Deterministic SHA-256 content hash of any JSON-serialisable payload.
    Identical payloads always produce identical hashes — the foundation of
    content-addressable storage and tamper-evidence.
    """
    serialised = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
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
    parent_hashes: List[str] = field(default_factory=list)
    node_hash: str = field(init=False)

    def __post_init__(self):
        # Hash = SHA-256(content_hash(payload) + sorted parent_hashes)
        raw = _content_hash(self.payload) + "".join(sorted(self.parent_hashes))
        self.node_hash = hashlib.sha256(raw.encode()).hexdigest()


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
        self._blobs: Dict[str, Any] = {}
        # Node registry: node_id -> MerkleNode
        self._nodes: Dict[str, MerkleNode] = {}
        # Reverse index: node_hash -> node_id (for dedup checks)
        self._hash_index: Dict[str, str] = {}

    # ── Insertion ─────────────────────────────────────────────────────────────

    def add_node(
        self,
        node_id: str,
        payload: Any,
        parent_ids: Optional[List[str]] = None,
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

        node = MerkleNode(
            node_id=node_id,
            payload=payload,
            parent_hashes=parent_hashes,
        )

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
        return node

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[MerkleNode]:
        return self._nodes.get(node_id)

    def get_by_hash(self, node_hash: str) -> Optional[MerkleNode]:
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
        )
        return recomputed.node_hash == node.node_hash

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def blob_count(self) -> int:
        """Number of unique payloads stored (after deduplication)."""
        return len(self._blobs)

    @property
    def node_count(self) -> int:
        return len(self._nodes)
