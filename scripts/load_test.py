"""Bounded load checks for public reads and the local Docker judge.

Examples:
  python scripts/load_test.py api --base https://codebug.onrender.com \
      --path /tasks/list --requests 60 --concurrency 8 --allow-production
  python scripts/load_test.py judge --task 0 --jobs 4 --concurrency 2
"""

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit

import requests


ROOT = Path(__file__).resolve().parents[1]
SAFE_API_PATHS = {"/ping", "/tasks/list", "/tasks/catalog", "/contests/list", "/tasks/0/view"}
_THREAD = threading.local()


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction + 0.5)))
    return round(ordered[index], 1)


def _summary(values):
    return {
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "max_ms": round(max(values), 1) if values else None,
    }


def _api_request(url, timeout):
    session = getattr(_THREAD, "session", None)
    if session is None:
        session = requests.Session()
        _THREAD.session = session
    started = time.perf_counter()
    try:
        response = session.get(url, timeout=timeout, headers={"Cache-Control": "no-cache"})
        elapsed = (time.perf_counter() - started) * 1000
        timing = response.headers.get("Server-Timing", "")
        match = re.search(r"app;dur=([\d.]+)", timing)
        return response.status_code, elapsed, float(match.group(1)) if match else None
    except requests.RequestException:
        return "network_error", (time.perf_counter() - started) * 1000, None


def run_api(args):
    parsed = urlsplit(args.base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("--base must be an http(s) URL")
    if parsed.hostname not in {"localhost", "127.0.0.1"} and not args.allow_production:
        raise SystemExit("Add --allow-production for a remote API")
    if args.path not in SAFE_API_PATHS:
        raise SystemExit("Only allowlisted read-only paths can be load tested")
    url = args.base.rstrip("/") + args.path
    _api_request(url, args.timeout)  # Warm the service before measuring.
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda _: _api_request(url, args.timeout), range(args.requests)))
    wall = time.perf_counter() - started
    durations = [item[1] for item in results]
    app_durations = [item[2] for item in results if item[2] is not None]
    codes = {}
    for code, _, _ in results:
        codes[str(code)] = codes.get(str(code), 0) + 1
    print(json.dumps({
        "mode": "api", "path": args.path, "requests": args.requests,
        "concurrency": args.concurrency, "status_counts": codes,
        "elapsed_s": round(wall, 2), "throughput_rps": round(args.requests / wall, 1),
        "client": _summary(durations), "server_app": _summary(app_durations),
    }, ensure_ascii=False))


def _judge_job(task, source, task_repo):
    temp_root = ROOT / ".codebug_work"
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="codebug-judge-load-", dir=temp_root) as tmp:
        work = Path(tmp)
        shutil.copyfile(source, work / "sol.cpp")
        env = {
            key: value for key, value in os.environ.items()
            if key in {"PATH", "HOME", "TMPDIR", "LANG", "DOCKER_HOST", "DOCKER_CONTEXT"}
        }
        env.update({
            "TASKS_REPO_DIR": str(task_repo),
            "JUDGE_SOURCE": "sol.cpp",
            "JUDGE_BINARY": "sol",
            "JUDGE_LOG_FILE": str(work / "judge.log"),
            "JUDGE_LANG": "cpp",
        })
        started = time.perf_counter()
        try:
            result = subprocess.run(
                ["python3", str(ROOT / "judge.py"), str(task)],
                cwd=work, env=env, capture_output=True, text=True, timeout=180,
            )
            duration = (time.perf_counter() - started) * 1000
            log = (work / "judge.log").read_text(errors="replace") if (work / "judge.log").exists() else ""
            match = re.search(r"Final verdict: ([A-Z]+)", log)
            return match.group(1) if match else f"exit_{result.returncode}", duration, log.count("Test ")
        except subprocess.TimeoutExpired:
            return "timeout", (time.perf_counter() - started) * 1000, 0


def run_judge(args):
    task_repo = (ROOT / ".tasks_repo").resolve()
    source = task_repo / str(args.task) / "solutions" / "main.cpp"
    if not source.is_file():
        raise SystemExit("Local approved C++ reference solution is required")
    if subprocess.run(["docker", "info"], capture_output=True, timeout=10).returncode:
        raise SystemExit("Docker daemon is required; unsafe host execution is not used")
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda _: _judge_job(args.task, source, task_repo), range(args.jobs)))
    wall = time.perf_counter() - started
    verdicts = {}
    for verdict, _, _ in results:
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    print(json.dumps({
        "mode": "judge", "task": args.task, "jobs": args.jobs,
        "concurrency": args.concurrency, "verdicts": verdicts,
        "tests_per_job": [item[2] for item in results],
        "elapsed_s": round(wall, 2), "throughput_jobs_per_min": round(args.jobs / wall * 60, 1),
        "job": _summary([item[1] for item in results]),
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    api = sub.add_parser("api")
    api.add_argument("--base", default="http://127.0.0.1:7777")
    api.add_argument("--path", choices=sorted(SAFE_API_PATHS), default="/ping")
    api.add_argument("--requests", type=int, choices=range(1, 201), metavar="1..200", default=60)
    api.add_argument("--concurrency", type=int, choices=range(1, 17), metavar="1..16", default=4)
    api.add_argument("--timeout", type=float, default=15)
    api.add_argument("--allow-production", action="store_true")
    judge = sub.add_parser("judge")
    judge.add_argument("--task", type=int, default=0)
    judge.add_argument("--jobs", type=int, choices=range(1, 9), metavar="1..8", default=4)
    judge.add_argument("--concurrency", type=int, choices=range(1, 4), metavar="1..3", default=2)
    args = parser.parse_args()
    if args.mode == "api":
        run_api(args)
    else:
        run_judge(args)


if __name__ == "__main__":
    main()
