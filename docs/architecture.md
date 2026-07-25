# DriftGuard-X Architecture

## Overview
DriftGuard-X v2 is a specialized pipeline framework that intercepts GenAI agent traces, maps them into a Causal Reliability Graph (DAG), and uses Budget-Constrained Root-Cause Bandits (BCRB) to isolate semantic drift and perform verified recoveries.

## Core Modules
1. **Trace SDK**: Python decorators generating `SpanRecord` objects with PII redaction and deterministic metadata constraints.
2. **Diffusion Engine**: PyTorch-based GAT and PageRank logic computing the upstream probability of terminal drift symptoms.
3. **Replay Engine & BCRB Scheduler**: Executes sandboxed counterfactual interventions against a SQLite trace store to verify causality bounds via Knapsack-UCB.
4. **Policy Engine**: A strictly tightening, hierarchical authorization matrix overriding autonomous rollback triggers.
5. **Ledger**: Emits Ed25519 hash-chained certificates verifying that state rollback actions were authorized and completed successfully without tampering.

## Data Flow (Closed Loop)
Trace Ingestion -> Causal Graph Map -> Diffusion -> BCRB Isolation -> Hoeffding Bounding -> Policy Authorization -> Cryptographic Ledger -> Rollback execution.

## Deployment Profile
Designed for Kubernetes via Next.js Web Console, FastAPI control plane, Redis Queue, and Postgres persistence (with deterministic SQLite fallbacks for testing).
