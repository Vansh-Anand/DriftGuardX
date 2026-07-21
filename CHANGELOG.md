# CHANGELOG

## [Unreleased]
### Added
- **Fault Taxonomy**: Created 18 specific fault scenarios (Stale Index, Bad Chunking, Policy Overblocking, etc.).
- **Deterministic Replay Harness**: Built local deterministic providers for embedding, retrieval, generation.
- **Do-Operator Sandbox**: Implemented a `multiprocessing` tool sandbox with sys.addaudithook to trap unexpected network and filesystem writes.
- **Reliability Metrics**: Added `ReliabilityVector` to capture multi-dimensional trace scores.
- **UI**: Added `apps/web/app/replay/[id]/page.tsx` to compare side-by-side replays and display freeze-invariant validations.

- **Causal Reliability Graph Builder & State Store (Prompt 03)**:
  - Added `NodeType` and `EdgeType` schemas in `packages/contracts/src/graph.py` with baseline features.
  - Expanded `ComponentVersion` to support rollbacks, constraints, and lifecycle states in the `VersionRegistry`.
  - Built `GraphBuilder` mapping traces to deterministic DAG graphs.
  - Implemented `GraphValidator` supporting orphan checks and permitted memory/tool cycles.
  - Persisted Causal Graphs via SQLAlchemy JSON models in `apps/api/src/models_graph.py`.
  - Implemented SQL graph traversal in `/v1/graph/query` to find descendants and candidate intervention points.
  - Scaffolding of React Flow interactive Graph Explorer UI in `apps/web/app/graph/[run_id]/page.tsx`.

- **Trace Fabric & Middleware**:
  - Implemented `packages/trace_sdk/src/adapters/langgraph.py` for LangGraph node/edge tracing.
  - Implemented `packages/trace_sdk/src/adapters/agent.py` for standard Python loop tracing.
  - Expanded `SpanRecord` and `TraceArtifact` schemas with privacy modes (metadata-only, redacted-content, etc.) and semantic attribute namespaces.
  - Enhanced RedactionMetadata with PII regex detection, data residency labels, and field-level allowlists.

- **Ingestion & Storage**:
  - Implemented content-addressed ArtifactStorage for prompts/payloads in `apps/api/src/services/artifacts.py`.
  - Implemented idempotent `IngestionService` supporting late arriving and out-of-order spans.
  - Implemented trace completeness scoring in `packages/evaluation/src/completeness.py` validating monotonic time and parent relationships.

- **Dashboards & OTEL**:
  - Added `/v1/telemetry/quality` and `/search` endpoints for telemetry health tracking.
  - Scaffolding of DriftGuard-X Telemetry Console UI in `apps/web/src/app/page.tsx`.
  - Added `deploy/otel-collector-config.yaml` for OTLP HTTP/gRPC routing.
  - Created `examples/agent_demo.py` demonstrating Trace SDK capabilities with data residency and PII redaction.
