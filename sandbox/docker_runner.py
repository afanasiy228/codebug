import os
import shutil
import subprocess
import time
from dataclasses import dataclass


class SandboxError(RuntimeError):
    pass


@dataclass
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str
    timeout: bool = False
    memory_exceeded: bool = False
    duration_ms: int = 0
    memory_mb: float | None = None


def _allow_unsafe_runner():
    return os.getenv("ALLOW_UNSAFE_RUNNER") == "1"


def _docker_available():
    return shutil.which("docker") is not None


def _image_for(language):
    lang = str(language or "").strip().lower()
    if lang in ("py", "python", "python3"):
        return "codebug-runner-python"
    return "codebug-runner-cpp"


def run_in_sandbox(
    command,
    *,
    workdir,
    language="cpp",
    input_data=None,
    timeout=5,
    memory="256m",
    cpus="1",
    pids_limit=64,
):
    if _docker_available():
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network=none",
            f"--memory={memory}",
            f"--cpus={cpus}",
            f"--pids-limit={pids_limit}",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--cap-drop=ALL",
            "-v",
            f"{os.path.abspath(workdir)}:/work:rw",
            "-w",
            "/work",
            _image_for(language),
            *command,
        ]
        try:
            started = time.monotonic()
            proc = subprocess.run(
                docker_cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return SandboxResult(
                proc.returncode,
                proc.stdout,
                proc.stderr,
                memory_exceeded=proc.returncode in (137, 139),
                duration_ms=elapsed_ms,
            )
        except subprocess.TimeoutExpired as e:
            return SandboxResult(-1, e.stdout or "", e.stderr or "", timeout=True)

    if not _allow_unsafe_runner():
        raise SandboxError(
            "Docker is required for CodeBug sandbox. "
            "Set ALLOW_UNSAFE_RUNNER=1 only for local development."
        )

    try:
        started = time.monotonic()
        proc = subprocess.run(
            command,
            cwd=workdir,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return SandboxResult(proc.returncode, proc.stdout, proc.stderr, duration_ms=elapsed_ms)
    except subprocess.TimeoutExpired as e:
        return SandboxResult(-1, e.stdout or "", e.stderr or "", timeout=True)
