"""
DriftGuard-X v2 — Asynchronous Optimizer Recomputing (AOR) Scheduler
Hardware-Gated Compute Scheduler.
"""

import concurrent.futures
import threading
from collections.abc import Callable
from typing import Any

from packages.replay.src.executor import LocalDevExecutor


class TaskStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    DIAGNOSING = "DIAGNOSING"


class AORTask:
    def __init__(
        self, task_id: str, func: Callable, inputs: dict[str, Any], dependencies: list[str] | None = None
    ):
        self.task_id = task_id
        self.func = func
        self.inputs = inputs
        self.dependencies = dependencies or []
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.diagnostic_result = None


class AORScheduler:
    def __init__(self, max_workers: int = 4):
        self.tasks: dict[str, AORTask] = {}
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._diagnostic_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def add_task(self, task: AORTask) -> None:
        with self._lock:
            self.tasks[task.task_id] = task

    def _get_ready_tasks(self) -> list[AORTask]:
        ready = []
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING:
                can_run = True
                for dep_id in task.dependencies:
                    dep_task = self.tasks.get(dep_id)
                    if dep_task:
                        if dep_task.status in (
                            TaskStatus.FAILED,
                            TaskStatus.BLOCKED,
                            TaskStatus.DIAGNOSING,
                        ):
                            task.status = TaskStatus.BLOCKED
                            can_run = False
                            break
                        elif dep_task.status != TaskStatus.COMPLETED:
                            can_run = False
                            break
                if can_run:
                    ready.append(task)
        return ready

    def _execute_task(self, task: AORTask) -> None:
        try:
            result = task.func(**task.inputs)
            with self._lock:
                task.result = result
                task.status = TaskStatus.COMPLETED
                self._condition.notify_all()
        except Exception as e:
            with self._lock:
                task.error = e
                task.status = TaskStatus.FAILED

                # Instantly divert to VTI sandbox for counterfactual testing
                task.status = TaskStatus.DIAGNOSING
                self._diagnostic_executor.submit(self._run_diagnostic, task)

                self._condition.notify_all()

    def _run_diagnostic(self, task: AORTask) -> None:
        """
        Background sandboxed execution (VTI) for counterfactual testing.
        """
        import asyncio

        executor = LocalDevExecutor()
        try:
            # We wrap the function in the LocalDevExecutor to physically isolate the test
            diag_result = asyncio.run(executor.execute(task.func, budget_seconds=5, **task.inputs))
            with self._lock:
                task.diagnostic_result = {
                    "payload": diag_result.payload,
                    "error": diag_result.error,
                }
                task.status = TaskStatus.FAILED
                self._condition.notify_all()
        except Exception as e:
            with self._lock:
                task.diagnostic_result = {"error": str(e)}
                task.status = TaskStatus.FAILED
                self._condition.notify_all()

    def run(self) -> None:
        """
        Main scheduler loop.
        """
        futures = []
        with self._condition:
            while True:
                # Check for completion
                all_done = True
                for t in self.tasks.values():
                    if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.DIAGNOSING):
                        all_done = False
                        break
                if all_done:
                    break

                ready_tasks = self._get_ready_tasks()
                for task in ready_tasks:
                    task.status = TaskStatus.RUNNING
                    f = self._executor.submit(self._execute_task, task)
                    futures.append(f)

                self._condition.wait(timeout=0.1)

    def get_task(self, task_id: str) -> AORTask:
        with self._lock:
            return self.tasks.get(task_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)
        self._diagnostic_executor.shutdown(wait=True)
