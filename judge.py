import os
import subprocess
import sys
import glob
import json
import tempfile
from runner import get_runner

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

def compile_solution(log):
    if not os.path.exists(SOURCE):
        log.write("Compilation Error\n")
        log.write(f"{SOURCE} not found\n")
        log.write("Final verdict: CE\n")
        return False

    res = RUNNER.compile()

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
    checker_path = os.path.join(task_path, checker_cfg.get("path") or "checker/checker.cpp")
    if not os.path.isfile(checker_path):
        log.write("Checker Error: checker.cpp not found\n")
        return False
    checker_bin = os.path.abspath("checker_bin")
    res = subprocess.run(
        ["g++", "-std=c++17", "-O2", checker_path, "-o", checker_bin],
        capture_output=True,
        text=True
    )
    if res.returncode != 0:
        log.write("Checker Compilation Error\n")
        log.write(res.stderr)
        if not str(res.stderr).endswith("\n"):
            log.write("\n")
        return False
    return checker_bin


def compare_with_checker(checker_bin, inp_file, answer_file, program_output):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as out:
        out.write(program_output)
        out_path = out.name
    try:
        res = subprocess.run(
            [checker_bin, inp_file, out_path, answer_file],
            capture_output=True,
            text=True,
            timeout=5
        )
    except subprocess.TimeoutExpired:
        try:
            os.remove(out_path)
        except OSError:
            pass
        return "TL"
    except Exception:
        try:
            os.remove(out_path)
        except OSError:
            pass
        return "RE"
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass
    return "OK" if res.returncode == 0 else "WA"


def run_test(inp_file, out_file, checker_bin=None):
    try:
        with open(inp_file, "r") as fin:
            proc = subprocess.run(
                RUNNER.command(),
                stdin=fin,
                capture_output=True,
                timeout=TIME_LIMIT,
                text=True
            )
    except subprocess.TimeoutExpired:
        return "TL"
    except Exception:
        return "RE"

    if proc.returncode != 0:
        return "RE"

    if checker_bin:
        return compare_with_checker(checker_bin, inp_file, out_file, proc.stdout)

    try:
        with open(out_file, "r") as f:
            correct_output = f.read().strip()
    except Exception:
        return "RE"

    program_output = proc.stdout.strip()
    return "OK" if program_output == correct_output else "WA"


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

        if not os.path.isdir(tests_path):
            log.write("Error: tests folder not found\n")
            log.write("Final verdict: NO_TESTS\n")
            return "NO_TESTS"

        # Компиляция
        if not compile_solution(log):
            return "CE"

        checker_bin = compile_checker(task_path, problem.get("checker") if problem else None, log)
        if checker_bin is False:
            log.write("Final verdict: CE\n")
            return "CE"
        tests = discover_tests(task_path, problem)
        tests_by_name = {str(test["name"]): test for test in tests}
        groups = normalize_groups(problem, tests)
        results = []
        group_results = {}
        total_score = 0

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
                verdict = run_test(test["input"], test["answer"], checker_bin)
                log.write(
                    f"Test {test['name']}: {verdict}"
                    f" [visibility={test.get('visibility', 'private')}, group={test.get('group', test.get('subtask', 1))}, points={test.get('points', 0)}]\n"
                )
                group_test_results.append(verdict)
                results.append(verdict)

            if not group_test_results:
                group_results[gid] = "SKIP"
                continue

            group_final = final_from_results(group_test_results)
            group_results[gid] = group_final
            if group_final == "OK":
                total_score += group.get("points", 0)
            log.write(f"Group {gid} verdict: {group_final}\n")

        missing_tests = [test for test in tests if str(test["name"]) not in {
            str(name) for group in groups for name in group.get("tests", [])
        }]
        for test in missing_tests:
            verdict = run_test(test["input"], test["answer"], checker_bin)
            log.write(
                f"Test {test['name']}: {verdict}"
                f" [visibility={test.get('visibility', 'private')}, group={test.get('group', test.get('subtask', 1))}, points={test.get('points', 0)}]\n"
            )
            results.append(verdict)

        final = final_from_results(results)

        log.write(f"Score: {total_score}\n")
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
