import os
import subprocess
import sys
import glob
import json
import tempfile
import shutil
import time
from runner import get_runner
from sandbox import SandboxError, run_in_sandbox

# --- Настройки ---
TIME_LIMIT = int(os.getenv("TIME_LIMIT", "5"))  # лимит времени на один тест
SOURCE = os.getenv("JUDGE_SOURCE", "sol.cpp")
BINARY = os.getenv("JUDGE_BINARY", "sol")
LOG_FILE = os.getenv("JUDGE_LOG_FILE", "log.txt")
LANG = os.getenv("JUDGE_LANG", "cpp").strip().lower()
RUNNER = get_runner(LANG, SOURCE, BINARY)

def task_dir(task):
    base = os.getenv("TASKS_REPO_DIR", ".tasks_repo")
    return os.path.join(base, task)


def load_json(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return None


def load_problem(task):
    path = os.path.join(task_dir(task), "problem.json")
    problem = load_json(path)
    if problem:
        problem.setdefault("formatVersion", problem.get("schemaVersion", 2))
        problem.setdefault("checker", {"type": "standard"})
        problem.setdefault("tests", [])
        problem.setdefault("groups", problem.get("subtasks", []))
        return problem
    return None


def task_type(problem):
    value = (problem or {}).get("taskType", "standard")
    value = str(value or "standard").strip().lower()
    return value if value in ("standard", "grader", "interactive") else "standard"


def scoring_mode(problem):
    value = (problem or {}).get("scoringMode", "ioi")
    value = str(value or "ioi").strip().lower()
    return value if value in ("ioi", "icpc") else "ioi"


def copy_task_file(task_path, relpath, dest_relpath=None):
    if not relpath:
        return None
    src = os.path.abspath(os.path.join(task_path, relpath))
    base = os.path.abspath(task_path)
    if src != base and not src.startswith(base + os.sep):
        return None
    if not os.path.isfile(src):
        return None
    dest = os.path.abspath(dest_relpath or relpath)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(src, dest)
    return os.path.relpath(dest, os.getcwd())


def write_text(path, content):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def sandbox_compile_cpp(sources, output, log, include_dirs=None):
    include_args = []
    for item in include_dirs or []:
        include_args.extend(["-I", item])
    try:
        res = run_in_sandbox(
            ["g++", "-std=c++17", "-O2", *include_args, *sources, "-o", output],
            workdir=os.getcwd(),
            language="cpp",
            timeout=30,
        )
    except SandboxError as e:
        log.write("Sandbox Error\n")
        log.write(str(e) + "\n")
        setattr(log, "_sandbox_error", True)
        return None
    return res


def has_sandbox_error(log):
    return bool(getattr(log, "_sandbox_error", False))


def compile_solution(log, problem=None, task_path=None):
    if not os.path.exists(SOURCE):
        log.write("Compilation Error\n")
        log.write(f"{SOURCE} not found\n")
        log.write("Final verdict: CE\n")
        return False

    if task_type(problem) == "grader":
        if LANG != "cpp":
            log.write("Compilation Error\n")
            log.write("grader tasks currently require C++ submissions\n")
            log.write("Final verdict: CE\n")
            return False
        grader_cfg = (problem or {}).get("grader") or {}
        grader_src = copy_task_file(task_path, grader_cfg.get("source") or "grader/grader.cpp")
        grader_header = copy_task_file(task_path, grader_cfg.get("header") or "grader/grader.h")
        if not grader_src:
            log.write("Compilation Error\n")
            log.write("grader/grader.cpp not found\n")
            log.write("Final verdict: CE\n")
            return False
        include_dirs = sorted({os.path.dirname(grader_src), os.path.dirname(grader_header or grader_src)})
        res = sandbox_compile_cpp([SOURCE, grader_src], BINARY, log, include_dirs=include_dirs)
        if res is None:
            log.write(f"Final verdict: {'SE' if has_sandbox_error(log) else 'CE'}\n")
            return False
    elif task_type(problem) == "interactive":
        if LANG != "cpp":
            log.write("Compilation Error\n")
            log.write("interactive tasks currently require C++ submissions\n")
            log.write("Final verdict: CE\n")
            return False
        res = sandbox_compile_cpp([SOURCE], BINARY, log)
        if res is None:
            log.write(f"Final verdict: {'SE' if has_sandbox_error(log) else 'CE'}\n")
            return False
    else:
        try:
            res = RUNNER.compile()
        except SandboxError as e:
            log.write("Sandbox Error\n")
            log.write(str(e) + "\n")
            log.write("Final verdict: SE\n")
            return False

    if res.returncode != 0:
        log.write("Compilation Error\n")
        log.write(res.stderr)
        if not str(res.stderr).endswith("\n"):
            log.write("\n")
        log.write("Final verdict: CE\n")
        return False

    return True


def compile_checker(task_path, checker_cfg, log):
    if not checker_cfg or checker_cfg.get("type") != "custom":
        return None
    checker_src = copy_task_file(task_path, checker_cfg.get("path") or "checker/checker.cpp")
    if not checker_src:
        log.write("Checker Error: checker.cpp not found\n")
        return False
    checker_bin = "checker_bin"
    res = sandbox_compile_cpp([checker_src], checker_bin, log)
    if res is None:
        return False
    if res.returncode != 0:
        log.write("Checker Compilation Error\n")
        log.write(res.stderr)
        if not str(res.stderr).endswith("\n"):
            log.write("\n")
        return False
    return checker_bin


def compare_with_checker(checker_bin, inp_file, answer_file, program_output):
    local_in = "checker_input.txt"
    local_answer = "checker_answer.txt"
    local_out = "checker_output.txt"
    write_text(local_in, read_text(inp_file))
    write_text(local_answer, read_text(answer_file))
    write_text(local_out, program_output)
    try:
        res = run_in_sandbox(
            [f"./{checker_bin}", local_in, local_out, local_answer],
            workdir=os.getcwd(),
            language="cpp",
            timeout=5
        )
    except SandboxError:
        return {"verdict": "RE", "time_ms": 0, "memory_mb": None}
    if res.timeout:
        return {"verdict": "TL", "time_ms": res.duration_ms, "memory_mb": res.memory_mb}
    if getattr(res, "memory_exceeded", False) or res.returncode == 137:
        return {"verdict": "ML", "time_ms": res.duration_ms, "memory_mb": res.memory_mb}
    return {"verdict": ("OK" if res.returncode == 0 else "WA"), "time_ms": res.duration_ms, "memory_mb": res.memory_mb}


def run_standard_test(inp_file, out_file, checker_bin=None):
    started = time.monotonic()
    try:
        input_data = read_text(inp_file)
        proc = run_in_sandbox(
            RUNNER.command(),
            workdir=os.getcwd(),
            language=LANG,
            input_data=input_data,
            timeout=TIME_LIMIT,
        )
    except SandboxError:
        return {"verdict": "RE", "time_ms": int((time.monotonic() - started) * 1000), "memory_mb": None}

    if proc.timeout:
        return {"verdict": "TL", "time_ms": proc.duration_ms, "memory_mb": proc.memory_mb}
    if getattr(proc, "memory_exceeded", False) or proc.returncode == 137:
        return {"verdict": "ML", "time_ms": proc.duration_ms, "memory_mb": proc.memory_mb}

    if proc.returncode != 0:
        return {"verdict": "RE", "time_ms": proc.duration_ms, "memory_mb": proc.memory_mb}

    if checker_bin:
        checker_result = compare_with_checker(checker_bin, inp_file, out_file, proc.stdout)
        checker_result["time_ms"] = max(proc.duration_ms, checker_result.get("time_ms", 0))
        checker_result["memory_mb"] = proc.memory_mb
        return checker_result

    try:
        with open(out_file, "r") as f:
            correct_output = f.read().strip()
    except Exception:
        return {"verdict": "RE", "time_ms": proc.duration_ms, "memory_mb": proc.memory_mb}

    program_output = proc.stdout.strip()
    return {
        "verdict": ("OK" if program_output == correct_output else "WA"),
        "time_ms": proc.duration_ms,
        "memory_mb": proc.memory_mb
    }


def compile_interactor(task_path, problem, log):
    interactor_cfg = (problem or {}).get("interactor") or {}
    interactor_src = copy_task_file(task_path, interactor_cfg.get("source") or "interactor/interactor.cpp")
    if not interactor_src:
        log.write("Interactor Error: interactor/interactor.cpp not found\n")
        return False
    res = sandbox_compile_cpp([interactor_src], "interactor_bin", log)
    if res is None:
        return False
    if res.returncode != 0:
        log.write("Interactor Compilation Error\n")
        log.write(res.stderr)
        if not str(res.stderr).endswith("\n"):
            log.write("\n")
        return False
    return "interactor_bin"


def run_interactive_test(inp_file, out_file, interactor_bin, test_name, log):
    started = time.monotonic()
    local_in = f"interactive_{test_name}.in"
    local_answer = f"interactive_{test_name}.ans"
    protocol = f"protocol_{test_name}.log"
    write_text(local_in, read_text(inp_file))
    write_text(local_answer, read_text(out_file))
    script = (
        "rm -f to_solution to_interactor; "
        "mkfifo to_solution to_interactor; "
        "exec 3<>to_solution; "
        "exec 4<>to_interactor; "
        f"./{BINARY} <&3 >&4 2> solution.err & "
        "solution_pid=$!; "
        f"./{interactor_bin} {local_in} {local_answer} {protocol} "
        "<&4 >&3 2> interactor.err; "
        "interactor_code=$?; "
        "exec 3>&-; exec 4>&-; "
        "if [ $interactor_code -ne 0 ]; then "
        "kill $solution_pid 2>/dev/null || true; "
        "wait $solution_pid 2>/dev/null || true; "
        "cat solution.err interactor.err >&2; "
        "exit $interactor_code; "
        "fi; "
        "wait $solution_pid; "
        "solution_code=$?; "
        "cat solution.err interactor.err >&2; "
        "exit $solution_code"
    )
    try:
        res = run_in_sandbox(
            ["sh", "-c", script],
            workdir=os.getcwd(),
            language="cpp",
            timeout=TIME_LIMIT,
        )
    except SandboxError as e:
        write_text(protocol, str(e) + "\n")
        return {"verdict": "RE", "time_ms": int((time.monotonic() - started) * 1000), "memory_mb": None}
    protocol_text = read_text(protocol) if os.path.isfile(protocol) else ""
    if res.stderr:
        protocol_text += ("\n" if protocol_text else "") + res.stderr
    if protocol_text:
        log.write(f"Protocol log {test_name}:\n{protocol_text}\n")
    if res.timeout:
        return {"verdict": "TL", "time_ms": res.duration_ms, "memory_mb": res.memory_mb}
    if getattr(res, "memory_exceeded", False) or res.returncode == 137:
        return {"verdict": "ML", "time_ms": res.duration_ms, "memory_mb": res.memory_mb}
    return {"verdict": ("OK" if res.returncode == 0 else "WA"), "time_ms": res.duration_ms, "memory_mb": res.memory_mb}


def run_test(inp_file, out_file, checker_bin=None, problem=None, interactor_bin=None, test_name="test", log=None):
    if task_type(problem) == "interactive":
        if not interactor_bin:
            return {"verdict": "RE", "time_ms": 0, "memory_mb": None}
        return run_interactive_test(inp_file, out_file, interactor_bin, test_name, log)
    return run_standard_test(inp_file, out_file, checker_bin)


def discover_tests(task_path, problem):
    if problem:
        tests = []
        for item in problem.get("tests") or []:
            inp = os.path.join(task_path, item.get("input", ""))
            out = os.path.join(task_path, item.get("answer", ""))
            if os.path.isfile(inp) and os.path.isfile(out):
                tests.append({
                    "name": item.get("name") or os.path.basename(inp),
                    "input": inp,
                    "answer": out,
                    "visibility": item.get("visibility", "private"),
                    "group": item.get("group", item.get("subtask", 1)),
                    "subtask": item.get("subtask", item.get("group", 1)),
                    "points": item.get("points", 0)
                })
        return tests

    tests_path = os.path.join(task_path, "tests")
    tests = []
    for inp in sorted(glob.glob(os.path.join(tests_path, "*.in"))):
        test_num = os.path.splitext(os.path.basename(inp))[0]
        out_file = os.path.join(tests_path, test_num + ".out")
        if os.path.isfile(out_file):
            tests.append({
                "name": test_num,
                "input": inp,
                "answer": out_file,
                "visibility": "legacy",
                "group": 1,
                "subtask": 1,
                "points": 0
            })
    return tests


def group_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


def normalize_groups(problem, tests):
    tests_by_group = {}
    for test in tests:
        gid = group_id(test.get("group", test.get("subtask", 1)))
        tests_by_group.setdefault(gid, []).append(test["name"])

    groups = []
    seen = set()
    for raw in (problem or {}).get("groups") or []:
        if not isinstance(raw, dict):
            continue
        gid = group_id(raw.get("id"))
        if gid <= 0 or gid in seen:
            continue
        deps = []
        for dep in raw.get("dependencies") or []:
            dep_id = group_id(dep)
            if dep_id > 0 and dep_id != gid:
                deps.append(dep_id)
        seen.add(gid)
        groups.append({
            "id": gid,
            "name": raw.get("name") or f"group {gid}",
            "points": group_id(raw.get("points", 0)),
            "dependencies": sorted(set(deps)),
            "tests": [str(name) for name in (raw.get("tests") or tests_by_group.get(gid, []))]
        })

    for gid in sorted(tests_by_group):
        if gid in seen:
            continue
        groups.append({
            "id": gid,
            "name": f"group {gid}",
            "points": 100 if len(tests_by_group) == 1 else 0,
            "dependencies": [],
            "tests": tests_by_group[gid]
        })

    return sorted(groups, key=lambda item: item["id"])


def final_from_results(results):
    if "RE" in results:
        return "RE"
    if "ML" in results:
        return "ML"
    if "TL" in results:
        return "TL"
    if "WA" in results:
        return "WA"
    if results and all(r in ("OK", "SKIP") for r in results):
        return "OK" if "SKIP" not in results else "PARTIAL"
    return "PARTIAL"


def judge(task_id):
    task_path = task_dir(task_id)
    tests_path = os.path.join(task_path, "tests")
    problem = load_problem(task_id)

    with open(LOG_FILE, "w") as log:
        log.write(f"Task {task_id}\n")
        if problem:
            log.write(f"Task format: v{problem.get('formatVersion', problem.get('schemaVersion', 2))}\n")
        current_task_type = task_type(problem)
        current_scoring_mode = scoring_mode(problem)
        log.write(f"Task type: {current_task_type}\n")
        log.write(f"Scoring mode: {current_scoring_mode}\n")

        if not os.path.isdir(tests_path):
            log.write("Error: tests folder not found\n")
            log.write("Final verdict: NO_TESTS\n")
            return "NO_TESTS"

        # Компиляция
        if not compile_solution(log, problem, task_path):
            return "SE" if has_sandbox_error(log) else "CE"

        checker_bin = compile_checker(task_path, problem.get("checker") if problem else None, log)
        if checker_bin is False:
            final = "SE" if has_sandbox_error(log) else "CE"
            log.write(f"Final verdict: {final}\n")
            return final
        interactor_bin = None
        if current_task_type == "interactive":
            interactor_bin = compile_interactor(task_path, problem, log)
            if interactor_bin is False:
                final = "SE" if has_sandbox_error(log) else "CE"
                log.write(f"Final verdict: {final}\n")
                return final
        tests = discover_tests(task_path, problem)
        tests_by_name = {str(test["name"]): test for test in tests}
        groups = normalize_groups(problem, tests)
        results = []
        group_results = {}
        total_score = 0
        first_fail_label = None
        max_time_ms = 0
        max_memory_mb = None
        stop_all_tests = False

        if not tests:
            log.write("Error: no tests found\n")
            log.write("Final verdict: NO_TESTS\n")
            return "NO_TESTS"

        for group in groups:
            gid = group["id"]
            deps = group.get("dependencies", [])
            blocked_by = [dep for dep in deps if group_results.get(dep) != "OK"]
            log.write(
                f"Group {gid}: {group.get('name', f'group {gid}')}"
                f" [points={group.get('points', 0)}, dependencies={deps}]\n"
            )

            if blocked_by:
                log.write(f"Group {gid}: SKIP [blocked_by={blocked_by}]\n")
                group_results[gid] = "SKIP"
                results.append("SKIP")
                continue

            group_test_results = []
            for name in group.get("tests") or []:
                test = tests_by_name.get(str(name))
                if not test:
                    continue
                test_result = run_test(
                    test["input"],
                    test["answer"],
                    checker_bin,
                    problem=problem,
                    interactor_bin=interactor_bin,
                    test_name=str(test["name"]),
                    log=log,
                )
                verdict = test_result["verdict"]
                test_time = int(test_result.get("time_ms", 0) or 0)
                mem = test_result.get("memory_mb")
                mem_text = f"{mem:.2f}" if isinstance(mem, (int, float)) else "?"
                max_time_ms = max(max_time_ms, test_time)
                if isinstance(mem, (int, float)):
                    max_memory_mb = mem if max_memory_mb is None else max(max_memory_mb, mem)
                if verdict in {"WA", "TL", "ML", "RE"} and first_fail_label is None:
                    first_fail_label = f"{verdict}{test['name']}"
                log.write(
                    f"Test {test['name']}: {verdict}"
                    f" [visibility={test.get('visibility', 'private')}, group={test.get('group', test.get('subtask', 1))}, points={test.get('points', 0)}, time={test_time} ms, memory={mem_text} MB]\n"
                )
                group_test_results.append(verdict)
                results.append(verdict)
                if verdict != "OK":
                    log.write(f"Group {gid}: STOP after first non-OK test ({verdict})\n")
                    stop_all_tests = True
                    break

            if not group_test_results:
                group_results[gid] = "SKIP"
                continue

            group_final = final_from_results(group_test_results)
            group_results[gid] = group_final
            if group_final == "OK":
                total_score += group.get("points", 0)
            log.write(f"Group {gid} verdict: {group_final}\n")
            if stop_all_tests:
                log.write("Testing stopped after first non-OK test\n")
                break

        missing_tests = [test for test in tests if str(test["name"]) not in {
            str(name) for group in groups for name in group.get("tests", [])
        }]
        for test in ([] if stop_all_tests else missing_tests):
            test_result = run_test(
                test["input"],
                test["answer"],
                checker_bin,
                problem=problem,
                interactor_bin=interactor_bin,
                test_name=str(test["name"]),
                log=log,
            )
            verdict = test_result["verdict"]
            test_time = int(test_result.get("time_ms", 0) or 0)
            mem = test_result.get("memory_mb")
            mem_text = f"{mem:.2f}" if isinstance(mem, (int, float)) else "?"
            max_time_ms = max(max_time_ms, test_time)
            if isinstance(mem, (int, float)):
                max_memory_mb = mem if max_memory_mb is None else max(max_memory_mb, mem)
            if verdict in {"WA", "TL", "ML", "RE"} and first_fail_label is None:
                first_fail_label = f"{verdict}{test['name']}"
            log.write(
                f"Test {test['name']}: {verdict}"
                f" [visibility={test.get('visibility', 'private')}, group={test.get('group', test.get('subtask', 1))}, points={test.get('points', 0)}, time={test_time} ms, memory={mem_text} MB]\n"
            )
            results.append(verdict)
            if verdict != "OK":
                log.write(f"Testing stopped after first non-OK test ({verdict})\n")
                break

        final = final_from_results(results)

        peak_memory_text = f"{max_memory_mb:.2f}" if isinstance(max_memory_mb, (int, float)) else "?"
        log.write(f"Peak time: {max_time_ms} ms\n")
        log.write(f"Peak memory: {peak_memory_text} MB\n")
        log.write(f"Score: {total_score}\n")
        if first_fail_label is not None:
            log.write(f"First failing test: {first_fail_label}\n")
        log.write(f"Final verdict: {final}\n")
        return final



# CLI запуск
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 judge.py <task_id>")
        sys.exit(1)

    TASK = sys.argv[1]
    result = judge(TASK)
    print("Вердикт:", result)
