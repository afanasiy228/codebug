"""Sandbox behaviour tests that need a real container runtime.

These SKIP unless Docker is available and the codebug runner images are built
(scripts/build_runner_images.sh). They must be run on the judge host - or any
machine with Docker - before shipping changes to sandbox/ or judge.py, because
they are what actually proves the C++/Python verdicts are unchanged.

    ./.venv/bin/python -m pytest tests/test_sandbox_docker.py -v
"""
import shutil
import subprocess

import pytest

from sandbox import run_in_sandbox
from sandbox import docker_runner


def _docker_ready():
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=15, check=True)
    except Exception:
        return False
    return True


def _image_present(name):
    try:
        out = subprocess.run(
            ["docker", "image", "inspect", name],
            capture_output=True, timeout=15,
        )
        return out.returncode == 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _docker_ready(), reason="Docker is not available on this machine"
)


def _running_codebug_containers():
    out = subprocess.run(
        ["docker", "ps", "--filter", "name=codebug-", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=15,
    )
    return [n for n in out.stdout.split() if n.startswith("codebug-")]


@pytest.fixture
def cpp_workdir(tmp_path):
    if not _image_present("codebug-runner-cpp"):
        pytest.skip("codebug-runner-cpp image not built")
    return tmp_path


@pytest.fixture
def py_workdir(tmp_path):
    if not _image_present("codebug-runner-python"):
        pytest.skip("codebug-runner-python image not built")
    return tmp_path


def _compile_cpp(workdir, source):
    (workdir / "sol.cpp").write_text(source, encoding="utf-8")
    return run_in_sandbox(
        ["g++", "-std=c++17", "-O2", "sol.cpp", "-o", "sol"],
        workdir=str(workdir), language="cpp", timeout=30,
    )


# --- verdict parity: these must keep working exactly as before --------------

def test_correct_cpp_solution_runs_and_returns_zero(cpp_workdir):
    assert _compile_cpp(cpp_workdir, """
        #include <iostream>
        int main(){ int a,b; std::cin>>a>>b; std::cout<<a+b; }
    """).returncode == 0

    res = run_in_sandbox(["./sol"], workdir=str(cpp_workdir), language="cpp",
                         input_data="2 3\n", timeout=5)
    assert res.returncode == 0 and res.timeout is False
    assert res.stdout.strip() == "5"


def test_cpp_compile_error_is_reported(cpp_workdir):
    res = _compile_cpp(cpp_workdir, "int main(){ this is not c++ }")
    assert res.returncode != 0, "compile error must surface as a nonzero return (CE)"


def test_cpp_runtime_error_is_nonzero(cpp_workdir):
    assert _compile_cpp(cpp_workdir, "int main(){ return 3; }").returncode == 0
    res = run_in_sandbox(["./sol"], workdir=str(cpp_workdir), language="cpp", timeout=5)
    assert res.returncode == 3 and res.timeout is False  # -> RE


def test_correct_python_solution_runs(py_workdir):
    (py_workdir / "sol.py").write_text(
        "a,b=map(int,input().split())\nprint(a+b)\n", encoding="utf-8")
    res = run_in_sandbox(["python3", "sol.py"], workdir=str(py_workdir),
                         language="python", input_data="2 3\n", timeout=5)
    assert res.returncode == 0 and res.stdout.strip() == "5"


# --- C6: timeout must leave no container behind ----------------------------

def test_infinite_loop_times_out_and_leaves_no_container(cpp_workdir):
    assert _compile_cpp(cpp_workdir, "int main(){ while(1){} }").returncode == 0
    before = set(_running_codebug_containers())

    res = run_in_sandbox(["./sol"], workdir=str(cpp_workdir), language="cpp", timeout=2)
    assert res.timeout is True, "verdict must still be TL"

    # Give the daemon a moment to reap.
    import time
    time.sleep(2)
    leaked = set(_running_codebug_containers()) - before
    assert not leaked, f"timed-out run leaked containers: {leaked}"


# --- H3: runaway output must not fill the disk -----------------------------

def test_infinite_output_is_bounded(py_workdir, monkeypatch):
    monkeypatch.setattr(docker_runner, "_OUTPUT_HARD_LIMIT_BYTES", 8 * 1024 * 1024)
    (py_workdir / "sol.py").write_text(
        "import sys\nwhile True:\n    sys.stdout.write('A'*65536)\n", encoding="utf-8")
    res = run_in_sandbox(["python3", "sol.py"], workdir=str(py_workdir),
                         language="python", timeout=30)
    assert res.timeout is True
    assert len(res.stdout.encode()) <= docker_runner._OUTPUT_LIMIT_BYTES + 65536


# --- existing container limits still hold ----------------------------------

def test_fork_bomb_is_contained_by_pids_limit(py_workdir):
    (py_workdir / "sol.py").write_text(
        "import os\nwhile True:\n    os.fork()\n", encoding="utf-8")
    res = run_in_sandbox(["python3", "sol.py"], workdir=str(py_workdir),
                         language="python", timeout=10, pids_limit=32)
    # Either it dies on its own or it is killed; what matters is that it ends.
    assert res.returncode != 0 or res.timeout


def test_memory_hog_is_reported_as_memory_exceeded(py_workdir):
    (py_workdir / "sol.py").write_text(
        "x = bytearray(512 * 1024 * 1024)\nprint(len(x))\n", encoding="utf-8")
    res = run_in_sandbox(["python3", "sol.py"], workdir=str(py_workdir),
                         language="python", timeout=20, memory="64m")
    assert res.memory_exceeded or res.returncode != 0  # -> ML


def test_sandbox_has_no_network(py_workdir):
    (py_workdir / "sol.py").write_text(
        "import socket\n"
        "socket.setdefaulttimeout(3)\n"
        "socket.create_connection(('1.1.1.1', 53))\n"
        "print('REACHED NETWORK')\n",
        encoding="utf-8",
    )
    res = run_in_sandbox(["python3", "sol.py"], workdir=str(py_workdir),
                         language="python", timeout=15)
    assert "REACHED NETWORK" not in res.stdout
    assert res.returncode != 0


def test_sandbox_does_not_receive_server_secrets(py_workdir, monkeypatch):
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT", "SUPER-SECRET-VALUE")
    (py_workdir / "sol.py").write_text(
        "import os\nprint(os.environ.get('FIREBASE_SERVICE_ACCOUNT', 'ABSENT'))\n",
        encoding="utf-8")
    res = run_in_sandbox(["python3", "sol.py"], workdir=str(py_workdir),
                         language="python", timeout=10)
    assert "SUPER-SECRET-VALUE" not in res.stdout
