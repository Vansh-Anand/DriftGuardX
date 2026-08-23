
from pydantic import BaseModel


class ExperimentConfig(BaseModel):
    experiment_name: str
    regime: str  # e.g., 'retrieval-only', 'rag', 'tool-use', 'mixed'
    model_version: str = "mock-v1"
    prompt_version: str = "v1"
    deterministic_seed: int = 42
    budget_cap_usd: float = 10.0
    concurrency_limit: int = 4

class DetectorConfig(ExperimentConfig):
    mode: str = "detector-only"

class ReplayConfig(ExperimentConfig):
    mode: str = "exhaustive-replay"
    trials: int = 3

class BCRBConfig(ExperimentConfig):
    mode: str = "bcrb"
    heuristic_scheduler: str = "ucb"

class DiffusionConfig(ExperimentConfig):
    mode: str = "diffusion"
    diffusion_type: str = "fixed" # or "learned"

class PolicyVariantConfig(ExperimentConfig):
    mode: str = "policy"
    policy_strictness: str = "high"

class CertificateModeConfig(ExperimentConfig):
    mode: str = "certificate"
    certificate_type: str = "strict"
