from typing import Never

from packages.contracts.src.models import ReplayEpisode


class EvaluationRegime:
    name: str

    def evaluate(self, episodes: list[ReplayEpisode]) -> Never:
        raise NotImplementedError


class RetrievalOnlyRegime(EvaluationRegime):
    name = "retrieval-only"

    def evaluate(self, episodes: list[ReplayEpisode]) -> None:
        # Mock evaluation logic for retrieval-only
        pass


class RAGAnswerQualityRegime(EvaluationRegime):
    name = "rag"

    def evaluate(self, episodes: list[ReplayEpisode]) -> None:
        pass


class ToolUseRegime(EvaluationRegime):
    name = "tool-use"

    def evaluate(self, episodes: list[ReplayEpisode]) -> None:
        pass


class MemoryPolicySyntheticRegime(EvaluationRegime):
    name = "memory-synthetic"

    def evaluate(self, episodes: list[ReplayEpisode]) -> None:
        pass


class MixedAgenticRegime(EvaluationRegime):
    name = "mixed"

    def evaluate(self, episodes: list[ReplayEpisode]) -> None:
        pass
