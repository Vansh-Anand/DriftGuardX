"""
DriftGuard-X v2 — Bandit State Persistence
PRIVATE — All Rights Reserved.
"""
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, JSON, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class BanditStateModel(Base):
    """
    Persists the state of the Budget-Constrained Root-Cause Bandit
    to allow resumption if the worker restarts.
    """
    __tablename__ = "bandit_states"
    
    run_id = Column(String, primary_key=True)
    total_budget = Column(Float, nullable=False)
    remaining_budget = Column(Float, nullable=False)
    exploration_constant = Column(Float, nullable=False)
    
    # Stored as JSON: {"arm_1": 5, "arm_2": 2}
    pulls_json = Column(JSON, default=dict)
    
    # Stored as JSON: {"arm_1": 0.85, "arm_2": 0.10}
    rewards_json = Column(JSON, default=dict)
    
    total_pulls = Column(Integer, default=0)
    stop_reason = Column(String, nullable=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
