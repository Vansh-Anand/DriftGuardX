"""
DriftGuard-X v2 — Trace Completeness Scoring

Validates parent-child relationships, expected span presence, and monotonic timestamps.
"""

from packages.contracts.src.models import TraceArtifact


def calculate_trace_completeness(trace: TraceArtifact) -> float:
    """
    Analyzes a TraceArtifact and returns a completeness score between 0.0 and 1.0.
    1.0 means perfect completeness.
    """
    if not trace.spans:
        return 0.0

    score = 1.0
    penalties = 0.0

    # Check 1: Root span exists
    root_span = trace.get_root_span()
    if not root_span:
        penalties += 0.2

    # Check 2: All child spans have a valid parent
    span_ids = {s.span_id for s in trace.spans}
    orphans = 0
    for s in trace.spans:
        if s.parent_span_id and s.parent_span_id not in span_ids:
            orphans += 1

    if orphans > 0:
        penalties += min(0.3, orphans * 0.1)

    # Check 3: Monotonic timestamps
    time_inversions = 0
    for s in trace.spans:
        if s.end_time and s.start_time and s.end_time < s.start_time:
            time_inversions += 1

        if s.parent_span_id and s.parent_span_id in span_ids:
            # Note: A real implementation would lookup the parent and ensure child start >= parent start
            pass

    if time_inversions > 0:
        penalties += min(0.2, time_inversions * 0.1)

    # Check 4: Has generator or final_response (topology heuristic)
    has_terminal = any(s.component_type and s.component_type.value in ["generator", "final_response"] for s in trace.spans)
    if not has_terminal:
        penalties += 0.1

    final_score = max(0.0, score - penalties)
    return round(final_score, 2)
