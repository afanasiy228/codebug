import os
import re
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


_RSS_MARKER = "__CB_MAXRSS_KB__:"


def _extract_rss(stderr_text):
    text = stderr_text or ""
    memory_mb = None
    cleaned_lines = []
    for line in text.splitlines():
        m = re.search(rf"{re.escape(_RSS_MARKER)}(\d+)", line.strip())
        if m:
            try:
                kb = int(m.group(1))
                memory_mb = kb / 1024.0
            except (TypeError, ValueError):
                pass
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    if text.endswith("\n"):
        cleaned += "\n"
    return cleaned, memory_mb


def _with_time(command):
    if shutil.which("time"):
        return ["time", "-f", f"{_RSS_MARKER}%M", *command]
    if os.path.exists("/usr/bin/time"):
        return ["/usr/bin/time", "-f", f"{_RSS_MARKER}%M", *command]
    return list(command)


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
        wrapped_command = _with_time(command)
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
            *wrapped_command,
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
            stderr_clean, memory_mb_value = _extract_rss(proc.stderr)
            return SandboxResult(
                proc.returncode,
                proc.stdout,
                stderr_clean,
                memory_exceeded=proc.returncode in (137, 139),
                duration_ms=elapsed_ms,
                memory_mb=memory_mb_value,
            )
        except subprocess.TimeoutExpired as e:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            stderr_clean, memory_mb_value = _extract_rss(e.stderr or "")
            return SandboxResult(
                -1,
                e.stdout or "",
                stderr_clean,
                timeout=True,
                duration_ms=elapsed_ms,
                memory_mb=memory_mb_value,
            )

    if not _allow_unsafe_runner():
        raise SandboxError(
            "Docker is required for CodeBug sandbox. "
            "Set ALLOW_UNSAFE_RUNNER=1 only for local development."
        )

    try:
        started = time.monotonic()
        proc = subprocess.run(
            _with_time(command),
            cwd=workdir,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        stderr_clean, memory_mb_value = _extract_rss(proc.stderr)
        return SandboxResult(
            proc.returncode,
            proc.stdout,
            stderr_clean,
            duration_ms=elapsed_ms,
            memory_mb=memory_mb_value,
        )
    except subprocess.TimeoutExpired as e:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        stderr_clean, memory_mb_value = _extract_rss(e.stderr or "")
        return SandboxResult(
            -1,
            e.stdout or "",
            stderr_clean,
            timeout=True,
            duration_ms=elapsed_ms,
            memory_mb=memory_mb_value,
        )
