"""
DriftGuard-X v2 — Isolated Replay Executor
Abstracts execution between local multiprocess sandboxes and production container boundaries.
"""
import asyncio
import os
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import cloudpickle
from pydantic import BaseModel

from packages.replay.src.sandbox import SandboxedWorker


class ReplayStateManifest(BaseModel):
    executor_type: str
    image_digest: str | None = None
    execution_time_seconds: float
    memory_used_bytes: int | None = None

class ReplayResult(BaseModel):
    payload: Any
    error: str | None = None
    manifest: ReplayStateManifest


class ReplayExecutor(ABC):
    @abstractmethod
    async def execute(self, func: Callable, budget_seconds: float, **kwargs) -> ReplayResult:
        pass


class LocalDevExecutor(ReplayExecutor):
    """
    Executes replays using the existing local multiprocessing SandboxedWorker.
    Suitable for unit tests and local demo mode.
    """
    async def execute(self, func: Callable, budget_seconds: float, **kwargs) -> ReplayResult:
        start_time = time.monotonic()

        try:
            # Wrap the blocking SandboxedWorker call in a thread
            result = await asyncio.to_thread(
                SandboxedWorker.run,
                func,
                kwargs,
                timeout_seconds=int(budget_seconds),
                trace_id="local_replay",
                enable_arc=False
            )
            error = None
        except (ValueError, RuntimeError, KeyError, TypeError, OSError) as e:
            result = None
            error = str(e)

        execution_time = time.monotonic() - start_time

        return ReplayResult(
            payload=result,
            error=error,
            manifest=ReplayStateManifest(
                executor_type="LocalDevExecutor",
                execution_time_seconds=execution_time,
                memory_used_bytes=None
            )
        )

class ContainerReplayExecutor(ReplayExecutor):
    """
    Production-oriented replay executor enforcing hard sandboxing using Docker.
    """
    def __init__(self, image: str = "python:3.11-slim"):
        self.base_image = image
        self.image = "driftguard-sandbox:latest"
        try:
            import io

            import docker
            self.client = docker.from_env()

            try:
                self.client.images.get(self.image)
            except docker.errors.ImageNotFound:
                dockerfile = f"FROM {self.base_image}\nRUN pip install cloudpickle\n"
                self.client.images.build(fileobj=io.BytesIO(dockerfile.encode('utf-8')), tag=self.image)

            self.image_info = self.client.images.get(self.image)
            self.image_digest = self.image_info.id
            repo_digests = self.image_info.attrs.get("RepoDigests", [])
            if repo_digests:
                self.image_digest = repo_digests[0]

        except ImportError:
            self.client = None

    async def execute(self, func: Callable, budget_seconds: float, **kwargs) -> ReplayResult:
        if not self.client:
            raise RuntimeError("Docker SDK not installed or daemon unavailable.")

        MAX_REQUEST_SIZE_BYTES = 5 * 1024 * 1024

        # Serialize the function and arguments
        payload_data = cloudpickle.dumps((func, kwargs))
        if len(payload_data) > MAX_REQUEST_SIZE_BYTES:
            return ReplayResult(
                payload=None,
                error="Payload exceeds 5MB limit",
                manifest=ReplayStateManifest(
                    executor_type="ContainerReplayExecutor",
                    image_digest=self.image_digest,
                    execution_time_seconds=0
                )
            )

        # Create a temporary directory to share with the container
        temp_dir = tempfile.mkdtemp(prefix="driftguard_sandbox_")
        payload_path = os.path.join(temp_dir, "payload.pkl")
        result_path = os.path.join(temp_dir, "result.pkl")

        with open(payload_path, "wb") as f:
            f.write(payload_data)

        # Runner script that unpickles, runs, and pickles the result
        runner_script = """
import sys
import pickle
import os

import cloudpickle

def main():
    try:
        with open('/sandbox/payload.pkl', 'rb') as f:
            func, kwargs = cloudpickle.load(f)
        
        # Add DriftGuard-X to python path
        sys.path.insert(0, '/app')
        
        result = func(**kwargs)
        
        out_data = cloudpickle.dumps({"status": "success", "payload": result})
        if len(out_data) > 10 * 1024 * 1024:
            raise RuntimeError("Response payload exceeds 10MB limit.")
            
        with open('/sandbox/result.pkl', 'wb') as f:
            f.write(out_data)
            
    except (ValueError, RuntimeError, KeyError, TypeError, OSError) as e:
        with open('/sandbox/result.pkl', 'wb') as f:
            cloudpickle.dump({"status": "error", "error": str(e)}, f)

if __name__ == '__main__':
    main()
"""
        script_path = os.path.join(temp_dir, "runner.py")
        with open(script_path, "w") as f:
            f.write(runner_script)

        container = None
        start_time = time.monotonic()
        error_msg = None

        try:
            # We must map the host temp_dir into the container.
            # Docker Desktop on Mac/Windows or native Linux supports mapping /tmp.
            # Convert Windows path if needed, but docker-py usually handles it.
            volumes = {
                temp_dir: {'bind': '/sandbox', 'mode': 'rw'},
                os.getcwd(): {'bind': '/app', 'mode': 'ro'}
            }

            # Spin up the container with hard boundaries
            container = self.client.containers.run(
                self.image,
                command=["python", "/sandbox/runner.py"],
                volumes=volumes,
                working_dir="/app",
                network_mode="none",  # Default deny network
                mem_limit="128m",     # Memory cap
                nano_cpus=1000000000, # 1 CPU core
                pids_limit=10,        # Prevent fork bombs
                tmpfs={'/tmp': 'size=64m'}, # Storage limit
                detach=True,
                remove=False
            )

            # Wait for it to finish asynchronously
            # We poll the container state since docker-py .wait() is blocking
            poll_interval = 0.1
            while True:
                container.reload()
                if container.status == "exited":
                    break

                if time.monotonic() - start_time > budget_seconds:
                    container.kill()
                    error_msg = f"TimeoutError: Exceeded {budget_seconds} seconds"
                    break

                await asyncio.sleep(poll_interval)

            # If not timed out, check results
            if not error_msg:
                # Get max memory used if possible
                try:
                    stats = container.stats(stream=False)
                    max_mem = stats.get('memory_stats', {}).get('max_usage')
                except (ValueError, RuntimeError, KeyError, TypeError, OSError):
                    max_mem = None
            else:
                max_mem = None

        except (ValueError, RuntimeError, KeyError, TypeError, OSError) as e:
            error_msg = f"ContainerError: {e!s}"
            max_mem = None
        finally:
            if container:
                try:
                    container.stop(timeout=1)
                    container.remove(force=True)
                except (ValueError, RuntimeError, KeyError, TypeError, OSError):
                    pass

        execution_time = time.monotonic() - start_time

        # Load the result from the mount
        result_payload = None
        if not error_msg:
            if os.path.exists(result_path):
                try:
                    with open(result_path, "rb") as f:
                        res = cloudpickle.load(f)
                    if res["status"] == "success":
                        result_payload = res["payload"]
                    else:
                        error_msg = res["error"]
                except (ValueError, RuntimeError, KeyError, TypeError, OSError) as e:
                    error_msg = f"Failed to unpickle result: {e!s}"
            else:
                error_msg = "No result file found. Container may have crashed."

        # Cleanup temp dir (ignoring errors if files are locked)
        import shutil
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except (ValueError, RuntimeError, KeyError, TypeError, OSError):
            pass

        return ReplayResult(
            payload=result_payload,
            error=error_msg,
            manifest=ReplayStateManifest(
                executor_type="ContainerReplayExecutor",
                image_digest=self.image_digest,
                execution_time_seconds=execution_time,
                memory_used_bytes=max_mem
            )
        )
