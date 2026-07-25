import json
import os
import uuid
from typing import List, Dict, Any
from packages.contracts.src.models import ReplayEpisode, ComponentType

class BenchmarkAdapter:
    def fetch(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def transform(self, raw_data: List[Dict[str, Any]]) -> List[ReplayEpisode]:
        raise NotImplementedError

    def get_dataset(self) -> List[ReplayEpisode]:
        raw = self.fetch()
        return self.transform(raw)

def _mock_episode(dataset_name: str, i: int, metric_name: str, metric_val: float) -> ReplayEpisode:
    return ReplayEpisode(
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=uuid.uuid4(),
        replay_version_id=uuid.uuid4(),
        original_version_tag="v1",
        replay_version_tag="v2",
        original_reliability_vector={metric_name: metric_val},
        replay_reliability_vector={metric_name: metric_val}
    )

class BEIRAdapter(BenchmarkAdapter):
    def __init__(self, dataset_name: str = "scifact"):
        self.dataset_name = dataset_name

    def fetch(self) -> List[Dict[str, Any]]:
        return [
            {"query_id": "1", "text": "Is this a fact?", "relevant_docs": ["doc1", "doc2"]},
            {"query_id": "2", "text": "Another fact?", "relevant_docs": ["doc3"]}
        ]
        
    def transform(self, raw_data: List[Dict[str, Any]]) -> List[ReplayEpisode]:
        episodes = []
        for i, raw in enumerate(raw_data):
            episodes.append(_mock_episode(self.dataset_name, i, "relevance", 1.0))
        return episodes

class ToolBenchAdapter(BenchmarkAdapter):
    def fetch(self) -> List[Dict[str, Any]]:
        return [
            {"task_id": "tb_1", "tool_calls": ["search_web"]},
            {"task_id": "tb_2", "tool_calls": ["calculator"]}
        ]
        
    def transform(self, raw_data: List[Dict[str, Any]]) -> List[ReplayEpisode]:
        episodes = []
        for i, raw in enumerate(raw_data):
            episodes.append(_mock_episode("toolbench", i, "tool_accuracy", 0.9))
        return episodes

class QAAdapter(BenchmarkAdapter):
    def __init__(self, name: str = "nq"):
        self.name = name

    def fetch(self) -> List[Dict[str, Any]]:
        return [{"question": "Who won the game?", "answer": "Team A"}]
        
    def transform(self, raw_data: List[Dict[str, Any]]) -> List[ReplayEpisode]:
        return [_mock_episode(self.name, 1, "exact_match", 1.0)]
