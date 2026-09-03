import os
import signal
import socket
import sys
import time
from pathlib import Path

import pytest

from packages.replay.src.sandbox import SandboxedWorker


@pytest.fixture
def sandbox_dir(tmp_path):
    d = tmp_path / "sandbox_work"
    d.mkdir()
    return str(d)


def exploit_read_outside(outside_file):
    with open(outside_file) as f:
        return f.read()


def test_read_outside_root(sandbox_dir):
    outside_file = str(Path(sandbox_dir).parent / "secret.txt")
    with open(outside_file, "w") as f:
        f.write("secret")

    with pytest.raises(RuntimeError, match="Sandbox error.*blocked"):
        SandboxedWorker.run(
            exploit_read_outside,
            {"outside_file": outside_file},
            enable_arc=False,
            sandbox_work_dir=sandbox_dir,
        )


def exploit_read_sibling(target):
    with open(target) as f:
        return f.read()


def test_sibling_path_prefix_traversal(sandbox_dir):
    sibling_dir = str(sandbox_dir) + "2"
    os.makedirs(sibling_dir, exist_ok=True)
    target = os.path.join(sibling_dir, "secret.txt")
    with open(target, "w") as f:
        f.write("secret")

    with pytest.raises(RuntimeError, match="Sandbox error.*blocked"):
        SandboxedWorker.run(
            exploit_read_sibling, {"target": target}, enable_arc=False, sandbox_work_dir=sandbox_dir
        )


def exploit_read_symlink(symlink_path):
    with open(symlink_path) as f:
        return f.read()


def test_symlink_redirection_escape(sandbox_dir):
    if os.name == "nt":
        pytest.skip("Symlink tests skip on Windows")

    outside_file = str(Path(sandbox_dir).parent / "secret.txt")
    with open(outside_file, "w") as f:
        f.write("secret")

    symlink_path = os.path.join(sandbox_dir, "link.txt")
    os.symlink(outside_file, symlink_path)

    with pytest.raises(RuntimeError, match="Sandbox error.*blocked"):
        SandboxedWorker.run(
            exploit_read_symlink,
            {"symlink_path": symlink_path},
            enable_arc=False,
            sandbox_work_dir=sandbox_dir,
        )


def exploit_write_naive(outside_target):
    with open(outside_target, "w") as f:
        f.write("hacked")


def test_naive_fixture_naming_bypass(sandbox_dir):
    outside_target = str(Path(sandbox_dir).parent / "my_fixture_file.txt")

    with pytest.raises(RuntimeError, match="Sandbox error.*blocked"):
        SandboxedWorker.run(
            exploit_write_naive,
            {"outside_target": outside_target},
            enable_arc=False,
            sandbox_work_dir=sandbox_dir,
        )


def exploit_fork():
    if hasattr(os, "fork"):
        os.fork()
    else:
        import subprocess

        subprocess.Popen([sys.executable, "-V"])


def test_fork_subprocess(sandbox_dir):
    with pytest.raises(RuntimeError, match="Sandbox error"):
        SandboxedWorker.run(exploit_fork, {}, enable_arc=False, sandbox_work_dir=sandbox_dir)


def exploit_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))


def test_socket_connection(sandbox_dir):
    with pytest.raises(RuntimeError, match="Sandbox error"):
        SandboxedWorker.run(exploit_socket, {}, enable_arc=False, sandbox_work_dir=sandbox_dir)


def exploit_write_outside(sandbox_dir):
    with open(os.path.join(sandbox_dir, "../../out.txt"), "w") as f:
        f.write("hacked")


def test_write_outside_temp_root(sandbox_dir):
    with pytest.raises(RuntimeError, match="Sandbox error.*blocked"):
        SandboxedWorker.run(
            exploit_write_outside,
            {"sandbox_dir": sandbox_dir},
            enable_arc=False,
            sandbox_work_dir=sandbox_dir,
        )


def exploit_timeout():
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(10)


def test_timeout_resistant_child(sandbox_dir):
    with pytest.raises(TimeoutError, match="Sandboxed execution timed out"):
        SandboxedWorker.run(
            exploit_timeout, {}, timeout_seconds=1, enable_arc=False, sandbox_work_dir=sandbox_dir
        )


def exploit_large_output():
    return "A" * (6 * 1024 * 1024)


def test_large_output_bound(sandbox_dir):
    with pytest.raises(RuntimeError, match="Sandbox error.*exceeds sandbox bound"):
        SandboxedWorker.run(
            exploit_large_output, {}, enable_arc=False, sandbox_work_dir=sandbox_dir
        )


def exploit_kill():
    os.kill(os.getpid(), signal.SIGTERM)


def test_kill_attempt(sandbox_dir):
    with pytest.raises(RuntimeError, match="Sandbox error.*blocked"):
        SandboxedWorker.run(exploit_kill, {}, enable_arc=False, sandbox_work_dir=sandbox_dir)
