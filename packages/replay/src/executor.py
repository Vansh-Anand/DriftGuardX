"""
DriftGuard-X v2 — Execution Sandbox
Provides hard runtime enforcement to prevent budget exhaustion by adversarial arms.
"""
import asyncio
from typing import Callable, Any

class TimeoutExecutor:
    """
    Executes an arm's payload with a hard wall-clock timeout.
    Prevents adversarial arms from reporting low costs but hanging the worker.
    """
    
    @staticmethod
    async def execute_with_timeout(func: Callable, budget_seconds: float, *args, **kwargs) -> Any:
        """
        Executes the function, raising asyncio.TimeoutError if it exceeds budget_seconds.
        """
        return await asyncio.wait_for(func(*args, **kwargs), timeout=budget_seconds)
