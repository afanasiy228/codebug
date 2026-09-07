import os
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
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


def _runner_uid():
    """uid the sandbox container runs as.

    Mirrors the server's uid so the bind-mounted workdir stays writable, but never
    root: if the server runs as root, fall back to a fixed unprivileged id.
    """
    uid = os.getuid()
    if uid == 0:
        return int(os.getenv("CODEBUG_RUNNER_UID", "65534"))
    return uid


def _runner_gid():
    gid = os.getgid()
    if os.getuid() == 0:
        return int(os.getenv("CODEBUG_RUNNER_GID", "65534"))
    return gid


def _image_for(language):
    lang = str(language or "").strip().lower()
    if lang in ("py", "python", "python3"):
        return "codebug-runner-python"
    return "codebug-runner-cpp"


_RSS_MARKER = "__CB_MAXRSS_KB__:"
_OUTPUT_LIMIT_BYTES = int(os.getenv("CODEBUG_OUTPUT_LIMIT_BYTES", str(4 * 1024 * 1024)))
_INPUT_LIMIT_BYTES = int(os.getenv("CODEBUG_INPUT_LIMIT_BYTES", str(2 * 1024 * 1024)))
# Hard ceiling on bytes a single run may spill to the host filesystem. The reported
# output is already truncated at _OUTPUT_LIMIT_BYTES; this is only a backstop against
# a program that prints forever, which would otherwise fill the judge disk for the
# whole wall-clock window. Deliberately far above _OUTPUT_LIMIT_BYTES so that no
# realistic solution changes verdict because of it.
_OUTPUT_HARD_LIMIT_BYTES = int(os.getenv("CODEBUG_OUTPUT_HARD_LIMIT_BYTES", str(64 * 1024 * 1024)))
_WATCHDOG_POLL_SECONDS = 0.1


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


def _docker_kill(container_name):
    """Stop a container by name.

    Killing the `docker run` client does NOT stop the container - the daemon owns its
    lifecycle. Without this, every timed-out submission leaks a container that keeps
    burning a CPU forever.
    """
    if not container_name:
        return
    for args in (["docker", "kill", container_name], ["docker", "rm", "-f", container_name]):
        try:
            subprocess.run(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except Exception:
            pass


def _kill_process_tree(proc):
    """Kill the whole process group, not just the direct child.

    The direct child is the `docker run` client, or `/usr/bin/time` in the local
    fallback - in both cases the process that actually runs user code is a
    descendant, and anything it forked survives a plain proc.kill().
    """
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _terminate_run(proc, container_name):
    _docker_kill(container_name)
    _kill_process_tree(proc)


def _watch_output_size(paths, budget, stop_event, on_exceeded):
    """Kill a run that spills more than `budget` bytes to disk.

    Output is only truncated after the process exits, so without this a program
    printing in a tight loop fills the host disk for the entire timeout window.
    """
    while not stop_event.wait(_WATCHDOG_POLL_SECONDS):
        total = 0
        for path in paths:
            try:
                total += os.path.getsize(path)
            except OSError:
                pass
        if total > budget:
            on_exceeded()
            return


def _run_process(command, *, cwd=None, input_data=None, timeout=5, preexec_fn=None,
                 container_name=None):
    import tempfile

    input_bytes = None
    if input_data is not None:
        input_bytes = str(input_data).encode("utf-8", errors="replace")
        if len(input_bytes) > _INPUT_LIMIT_BYTES:
            input_bytes = input_bytes[:_INPUT_LIMIT_BYTES]

    with tempfile.TemporaryDirectory(prefix="codebug_proc_") as tmp:
        stdout_path = os.path.join(tmp, "stdout.txt")
        stderr_path = os.path.join(tmp, "stderr.txt")
        output_exceeded = threading.Event()
        stop_watchdog = threading.Event()
        with open(stdout_path, "wb") as stdout_file, open(stderr_path, "wb") as stderr_file:
            started = time.monotonic()
            proc = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                preexec_fn=preexec_fn,
                start_new_session=True,
            )

            def _on_output_exceeded():
                output_exceeded.set()
                _terminate_run(proc, container_name)

            watchdog = threading.Thread(
                target=_watch_output_size,
                args=((stdout_path, stderr_path), _OUTPUT_HARD_LIMIT_BYTES,
                      stop_watchdog, _on_output_exceeded),
                daemon=True,
            )
            watchdog.start()

            timed_out = False
            try:
                proc.communicate(input=input_bytes, timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _terminate_run(proc, container_name)
                try:
                    proc.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            except BrokenPipeError:
                # The run was killed by the output watchdog while stdin was being fed.
                _terminate_run(proc, container_name)
                try:
                    proc.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            finally:
                stop_watchdog.set()
                watchdog.join(timeout=2)
                # A run killed for runaway output reached the same place an infinite
                # loop reaches today: it exhausted its limits. Report it as a timeout
                # so verdicts stay exactly as they were.
                if output_exceeded.is_set():
                    timed_out = True
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
        # Do not wrap with `time` inside docker containers: many minimal images
        # don't have GNU time installed, which causes execution failure.
        wrapped_command = list(command)
        # A unique name is what makes the container killable on timeout: SIGKILLing the
        # `docker run` client leaves the container running under the daemon.
        container_name = f"codebug-{uuid.uuid4().hex}"
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--name",
            container_name,
            "--network=none",
            f"--memory={memory}",
            f"--memory-swap={memory}",
            f"--cpus={cpus}",
            f"--pids-limit={pids_limit}",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--user",
            f"{_runner_uid()}:{_runner_gid()}",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
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
            container_name=container_name,
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
