from typing import Protocol, List, Dict, Any
from datetime import datetime, timezone
import json
import sqlite3
import os

class TransparencyStore(Protocol):
    def append(self, entry: Dict[str, Any]) -> None:
        ...
        
    def get(self, commit_hash: str) -> Dict[str, Any] | None:
        ...
        
    def iterate(self) -> List[Dict[str, Any]]:
        ...
        
    def latest_checkpoint(self) -> Dict[str, Any] | None:
        ...
        
    def verify_chain(self, commit_hash: str) -> bool:
        ...


class InMemoryTransparencyStore:
    def __init__(self):
        self._ledger: List[Dict[str, Any]] = []
        
    def append(self, entry: Dict[str, Any]) -> None:
        self._ledger.append(entry)
        
    def get(self, commit_hash: str) -> Dict[str, Any] | None:
        for entry in self._ledger:
            if entry["commit_hash"] == commit_hash:
                return entry
        return None
        
    def iterate(self) -> List[Dict[str, Any]]:
        return self._ledger.copy()
        
    def latest_checkpoint(self) -> Dict[str, Any] | None:
        return self._ledger[-1] if self._ledger else None
        
    def verify_chain(self, commit_hash: str) -> bool:
        return self.get(commit_hash) is not None


class SQLiteTransparencyStore:
    def __init__(self, db_path: str = "witness_ledger.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    commit_hash TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    merkle_root TEXT NOT NULL,
                    certificate_count INTEGER NOT NULL,
                    policy_snapshot TEXT NOT NULL,
                    canary_passed BOOLEAN NOT NULL,
                    payload JSON NOT NULL
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_commit_hash ON ledger(commit_hash)
            ''')
            
    def append(self, entry: Dict[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO ledger (
                    commit_hash, timestamp, merkle_root, 
                    certificate_count, policy_snapshot, canary_passed, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry["commit_hash"],
                entry["timestamp"],
                entry["merkle_root"],
                entry["certificate_count"],
                entry["policy_snapshot"],
                entry["canary_passed"],
                json.dumps(entry)
            ))
            
    def get(self, commit_hash: str) -> Dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT payload FROM ledger WHERE commit_hash = ?", (commit_hash,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["payload"])
        return None
        
    def iterate(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT payload FROM ledger ORDER BY id ASC")
            return [json.loads(row["payload"]) for row in cursor.fetchall()]
            
    def latest_checkpoint(self) -> Dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT payload FROM ledger ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return json.loads(row["payload"])
        return None
        
    def verify_chain(self, commit_hash: str) -> bool:
        # In a real implementation this would verify the chain of hashes
        # For now, it matches the simple existence check in witness.py
        return self.get(commit_hash) is not None
