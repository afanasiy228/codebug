import os
import re
import shutil
import signal
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
_OUTPUT_LIMIT_BYTES = int(os.getenv("CODEBUG_OUTPUT_LIMIT_BYTES", str(4 * 1024 * 1024)))


def _parse_memory_bytes(value):
    text = str(value or "").strip().lower()
    match = re.fullmatch(r"(\d+)([kmgt]?)b?", text)
    if not match:
        return 256 * 1024 * 1024
    amount = int(match.group(1))
    unit = match.group(2)
    scale = {
        "": 1,
        "k": 1024,
        "m": 1024 * 1024,
        "g": 1024 * 1024 * 1024,
        "t": 1024 * 1024 * 1024 * 1024,
    }[unit]
    return amount * scale


def _memory_limit_mb(value):
    return _parse_memory_bytes(value) / (1024 * 1024)


def _looks_memory_exceeded(returncode, stderr_text):
    if returncode in (137, -signal.SIGKILL):
        return True
    text = (stderr_text or "").lower()
    indicators = (
        "memoryerror",
        "std::bad_alloc",
        "bad_alloc",
        "cannot allocate memory",
        "out of memory",
    )
    return any(marker in text for marker in indicators)


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


def _limit_child_resources(memory, timeout):
    memory_bytes = _parse_memory_bytes(memory)

    def apply_limits():
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            resource.setrlimit(resource.RLIMIT_DATA, (memory_bytes, memory_bytes))
            cpu_seconds = max(1, int(timeout) + 1)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
            file_limit = _OUTPUT_LIMIT_BYTES + 1024 * 1024
            resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit, file_limit))
        except Exception:
            pass

    return apply_limits


def _read_limited(path):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            data = f.read(_OUTPUT_LIMIT_BYTES + 1)
    except FileNotFoundError:
        return "", False
    truncated = len(data) > _OUTPUT_LIMIT_BYTES or size > _OUTPUT_LIMIT_BYTES
    data = data[:_OUTPUT_LIMIT_BYTES]
    return data.decode("utf-8", errors="replace"), truncated


def _run_process(command, *, cwd=None, input_data=None, timeout=5, preexec_fn=None):
    import tempfile

    input_bytes = None
    if input_data is not None:
        input_bytes = str(input_data).encode("utf-8", errors="replace")

    with tempfile.TemporaryDirectory(prefix="codebug_proc_") as tmp:
        stdout_path = os.path.join(tmp, "stdout.txt")
        stderr_path = os.path.join(tmp, "stderr.txt")
        with open(stdout_path, "wb") as stdout_file, open(stderr_path, "wb") as stderr_file:
            started = time.monotonic()
            proc = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                preexec_fn=preexec_fn,
            )
            timed_out = False
            try:
                proc.communicate(input=input_bytes, timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                proc.communicate()
            elapsed_ms = int((time.monotonic() - started) * 1000)

        stdout_text, stdout_truncated = _read_limited(stdout_path)
        stderr_text, stderr_truncated = _read_limited(stderr_path)
        if stdout_truncated:
            stdout_text += "\n[output truncated]\n"
        if stderr_truncated:
            stderr_text += "\n[stderr truncated]\n"

    return proc.returncode, stdout_text, stderr_text, timed_out, elapsed_ms


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
            f"--memory-swap={memory}",
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
        returncode, stdout_text, stderr_text, timed_out, elapsed_ms = _run_process(
            docker_cmd,
            input_data=input_data,
            timeout=timeout,
        )
        stderr_clean, memory_mb_value = _extract_rss(stderr_text)
        if timed_out:
            return SandboxResult(
                -1,
                stdout_text,
                stderr_clean,
                timeout=True,
                duration_ms=elapsed_ms,
                memory_mb=memory_mb_value,
            )
        memory_exceeded = _looks_memory_exceeded(returncode, stderr_clean)
        if memory_exceeded and memory_mb_value is None:
            memory_mb_value = _memory_limit_mb(memory)
        return SandboxResult(
            returncode,
            stdout_text,
            stderr_clean,
            memory_exceeded=memory_exceeded,
            duration_ms=elapsed_ms,
            memory_mb=memory_mb_value,
        )

    if not _allow_unsafe_runner():
        raise SandboxError(
            "Docker is required for CodeBug sandbox. "
            "Set ALLOW_UNSAFE_RUNNER=1 only for local development."
        )

    returncode, stdout_text, stderr_text, timed_out, elapsed_ms = _run_process(
        _with_time(command),
        cwd=workdir,
        input_data=input_data,
        timeout=timeout,
        preexec_fn=_limit_child_resources(memory, timeout),
    )
    stderr_clean, memory_mb_value = _extract_rss(stderr_text)
    if timed_out:
        return SandboxResult(
            -1,
            stdout_text,
            stderr_clean,
            timeout=True,
            duration_ms=elapsed_ms,
            memory_mb=memory_mb_value,
        )
    memory_exceeded = _looks_memory_exceeded(returncode, stderr_clean)
    if memory_exceeded and memory_mb_value is None:
        memory_mb_value = _memory_limit_mb(memory)
    return SandboxResult(
        returncode,
        stdout_text,
        stderr_clean,
        memory_exceeded=memory_exceeded,
        duration_ms=elapsed_ms,
        memory_mb=memory_mb_value,
    )
