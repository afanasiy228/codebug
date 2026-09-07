#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


TASKS_GIT_DIR = Path(".tasks_repo")
REF = "FETCH_HEAD"
OUT_DIR = Path(".tasks_repo_clean")
# Reports and state live in the git-ignored work dir. The repository root is the
# GitHub Pages document root, so anything written there is published on the site.
WORK_DIR = Path(os.getenv("CODEBUG_WORK_DIR", ".codebug_work"))
REPORT_PATH = WORK_DIR / "cleanup_report.json"
STATE_PATH = WORK_DIR / "cleanup_state.json"

SSH_CMD = "ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o IPQoS=throughput -o Compression=no -o StrictHostKeyChecking=accept-new"

TIME_LIMIT_SEC = 5


def run_cmd(cmd, check=True, retries=1, retry_sleep=1.0, timeout=None):
    env = {**os.environ, "GIT_SSH_COMMAND": SSH_CMD}
    last = None
    for attempt in range(1, retries + 1):
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
        if proc.returncode == 0:
            return proc
        last = proc
        if attempt < retries:
            time.sleep(retry_sleep * attempt)
    if check:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{last.stdout}\nSTDERR:\n{last.stderr}")
    return last


def git_list_task_ids():
    proc = run_cmd(["git", "-C", str(TASKS_GIT_DIR), "ls-tree", "-d", "--name-only", REF], retries=3)
    ids = []
    for line in proc.stdout.splitlines():
        name = line.strip()
        if name.isdigit():
            ids.append(int(name))
    ids.sort()
    return ids


def checkout_task_dir(task_id, retries=8):
    for attempt in range(1, retries + 1):
        proc = run_cmd(
            ["git", "-C", str(TASKS_GIT_DIR), "checkout", REF, "--", str(task_id)],
            check=False,
            retries=1,
            timeout=180
        )
        if proc.returncode == 0:
            return
        if attempt < retries:
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"git checkout failed for task {task_id}")


def strip_cpp_comments(src):
    out = []
    i = 0
    n = len(src)
    state = "normal"
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""

        if state == "normal":
            if ch == "/" and nxt == "/":
                state = "line_comment"
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block_comment"
                i += 2
                continue
            if ch == '"':
                state = "string"
                out.append(ch)
                i += 1
                continue
            if ch == "'":
                state = "char"
                out.append(ch)
                i += 1
                continue
            out.append(ch)
            i += 1
            continue

        if state == "line_comment":
            if ch == "\n":
                out.append("\n")
                state = "normal"
            i += 1
            continue

        if state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "normal"
                i += 2
                continue
            if ch == "\n":
                out.append("\n")
            i += 1
            continue

        if state == "string":
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if ch == '"':
                state = "normal"
            i += 1
            continue

        if state == "char":
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if ch == "'":
                state = "normal"
            i += 1
            continue

    return "".join(out)


def compile_cpp(src_path, bin_path):
    return subprocess.run(
        ["g++", "-std=c++17", "-O2", src_path, "-o", bin_path],
        capture_output=True,
        text=True
    )


def run_one(bin_path, test_input, expected_output):
    try:
        proc = subprocess.run(
            [bin_path],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=TIME_LIMIT_SEC
        )
    except subprocess.TimeoutExpired:
        return "TL"
    except Exception:
        return "RE"

    if proc.returncode != 0:
        return "RE"

    return "OK" if proc.stdout.strip() == expected_output.strip() else "WA"


def judge_source(source_text, tests):
    with tempfile.TemporaryDirectory(prefix="task_judge_") as td:
        tdp = Path(td)
        src = tdp / "main.cpp"
        binp = tdp / "main"
        src.write_text(source_text, encoding="utf-8")

        comp = compile_cpp(str(src), str(binp))
        if comp.returncode != 0:
            return "CE"

        for test in tests:
            verdict = run_one(str(binp), test["in"], test["out"])
            if verdict != "OK":
                return verdict

        if not tests:
            return "NO_TESTS"
        return "OK"


def load_task(task_id):
    checkout_task_dir(task_id)
    tdir = TASKS_GIT_DIR / str(task_id)
    meta = json.loads((tdir / "meta.json").read_text(encoding="utf-8"))
    statement = (tdir / "statement.md").read_text(encoding="utf-8")
    help_md = (tdir / "help.md").read_text(encoding="utf-8")
    code = (tdir / "code.cpp").read_text(encoding="utf-8")
    sol_file = tdir / "sol.cpp"
    sol = sol_file.read_text(encoding="utf-8") if sol_file.exists() else ""
    generator_file = tdir / "generator.cpp"
    generator = generator_file.read_text(encoding="utf-8") if generator_file.exists() else ""

    tests = []
    tests_dir = tdir / "tests"
    if tests_dir.exists():
        test_nums = set()
        for path in tests_dir.glob("*.in"):
            if path.stem.isdigit() and int(path.stem) >= 1:
                test_nums.add(int(path.stem))
        for idx in sorted(test_nums):
            in_file = tests_dir / f"{idx}.in"
            out_file = tests_dir / f"{idx}.out"
            if in_file.exists() and out_file.exists():
                tests.append({
                    "idx": idx,
                    "in": in_file.read_text(encoding="utf-8"),
                    "out": out_file.read_text(encoding="utf-8"),
                })

    return {
        "orig_id": task_id,
        "meta": meta,
        "statement": statement,
        "help": help_md,
        "code": code,
        "sol": sol,
        "generator": generator,
        "tests": tests,
    }


def write_task(task, new_id):
    tdir = OUT_DIR / str(new_id)
    tdir.mkdir(parents=True, exist_ok=True)
    tests_dir = tdir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    meta = dict(task["meta"])
    meta["id"] = new_id
    (tdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (tdir / "statement.md").write_text(task["statement"], encoding="utf-8")
    (tdir / "help.md").write_text(task["help"], encoding="utf-8")
    (tdir / "code.cpp").write_text(strip_cpp_comments(task["code"]), encoding="utf-8")
    (tdir / "sol.cpp").write_text(strip_cpp_comments(task["sol"]), encoding="utf-8")
    if task["generator"].strip():
        (tdir / "generator.cpp").write_text(strip_cpp_comments(task["generator"]), encoding="utf-8")

    for new_test_idx, test in enumerate(task["tests"], start=1):
        (tests_dir / f"{new_test_idx}.in").write_text(test["in"], encoding="utf-8")
        (tests_dir / f"{new_test_idx}.out").write_text(test["out"], encoding="utf-8")


def main():
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        results = state.get("results", {})
    else:
        results = {}

    task_ids = git_list_task_ids()
    if not task_ids:
        raise RuntimeError("No task ids found in FETCH_HEAD")

    for idx, tid in enumerate(task_ids, start=1):
        if str(tid) in results:
            continue

        print(f"[{idx}/{len(task_ids)}] task {tid}", flush=True)
        try:
            task = load_task(tid)
        except Exception as e:
            raise RuntimeError(f"load failed for task {tid}: {e}") from e

        tests_count = len(task["tests"])
        if tests_count <= 2:
            results[str(tid)] = {
                "keep": False,
                "reason": f"too_few_tests:{tests_count}",
                "tests": tests_count
            }
            STATE_PATH.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            continue

        bug_verdict = judge_source(task["code"], task["tests"])
        sol_verdict = None
        if task["sol"].strip():
            sol_verdict = judge_source(task["sol"], task["tests"])
            if sol_verdict != "OK":
                results[str(tid)] = {
                    "keep": False,
                    "reason": f"solution_not_ok:{sol_verdict}",
                    "bugVerdict": bug_verdict,
                    "solVerdict": sol_verdict,
                    "tests": tests_count
                }
                STATE_PATH.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                continue

        if bug_verdict == "OK":
            results[str(tid)] = {
                "keep": False,
                "reason": "buggy_ok",
                "bugVerdict": bug_verdict,
                "solVerdict": sol_verdict,
                "tests": tests_count
            }
            STATE_PATH.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            continue

        if bug_verdict not in {"WA", "TL", "RE"}:
            results[str(tid)] = {
                "keep": False,
                "reason": f"buggy_bad_verdict:{bug_verdict}",
                "bugVerdict": bug_verdict,
                "solVerdict": sol_verdict,
                "tests": tests_count
            }
            STATE_PATH.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            continue

        results[str(tid)] = {
            "keep": True,
            "bugVerdict": bug_verdict,
            "solVerdict": sol_verdict if sol_verdict is not None else "N/A",
            "tests": tests_count
        }
        STATE_PATH.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    removed = []
    kept_ids = []
    for tid in task_ids:
        entry = results.get(str(tid))
        if not entry:
            raise RuntimeError(f"Missing result for task {tid}")
        if entry.get("keep"):
            kept_ids.append(tid)
        else:
            removed.append({
                "id": tid,
                "reason": entry.get("reason", "unknown"),
                "bugVerdict": entry.get("bugVerdict"),
                "solVerdict": entry.get("solVerdict"),
                "tests": entry.get("tests")
            })

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    kept_report = []
    for new_id, old_id in enumerate(kept_ids):
        task = load_task(old_id)
        write_task(task, new_id)
        entry = results[str(old_id)]
        kept_report.append({
            "oldId": old_id,
            "newId": new_id,
            "bugVerdict": entry.get("bugVerdict"),
            "solVerdict": entry.get("solVerdict"),
            "tests": entry.get("tests")
        })

    report = {
        "total": len(task_ids),
        "kept": len(kept_ids),
        "removed": len(removed),
        "removedTasks": removed,
        "keptTasks": kept_report
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if STATE_PATH.exists():
        STATE_PATH.unlink()
    print(json.dumps({k: report[k] for k in ("total", "kept", "removed")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
