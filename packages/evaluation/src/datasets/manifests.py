from pydantic import BaseModel
from typing import List, Optional

class FaultManifest(BaseModel):
    fault_type: str
    seed: int
    severity: float

class DatasetManifest(BaseModel):
    dataset_name: str
    version: str
    num_samples: int
    fault_overlays: List[FaultManifest] = []
