import os
import subprocess
import sys
import glob
import json
import tempfile

# --- Настройки ---
TIME_LIMIT = int(os.getenv("TIME_LIMIT", "5"))  # лимит времени на один тест
SOURCE = os.getenv("JUDGE_SOURCE", "sol.cpp")
BINARY = os.getenv("JUDGE_BINARY", "sol")
LOG_FILE = os.getenv("JUDGE_LOG_FILE", "log.txt")
LANG = os.getenv("JUDGE_LANG", "cpp").strip().lower()

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
        problem.setdefault("checker", {"type": "standard"})
        problem.setdefault("tests", [])
        return problem
    return None

def compile_solution(log):
    if not os.path.exists(SOURCE):
        log.write("Compilation Error\n")
        log.write(f"{SOURCE} not found\n")
        log.write("Final verdict: CE\n")
        return False

    if LANG in ("py", "python", "python3"):
        res = subprocess.run(
            ["python3", "-m", "py_compile", SOURCE],
            capture_output=True,
            text=True
        )
    else:
        res = subprocess.run(
            ["g++", "-std=c++17", "-O2", SOURCE, "-o", BINARY],
            capture_output=True,
            text=True
        )

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
            cmd = ["python3", SOURCE] if LANG in ("py", "python", "python3") else [f"./{BINARY}"]
            proc = subprocess.run(
                cmd,
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
                    "subtask": item.get("subtask", 1)
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
                "subtask": 1
            })
    return tests


def judge(task_id):
    task_path = task_dir(task_id)
    tests_path = os.path.join(task_path, "tests")
    problem = load_problem(task_id)

    with open(LOG_FILE, "w") as log:
        log.write(f"Task {task_id}\n")
        if problem:
            log.write(f"Task format: v{problem.get('schemaVersion', 2)}\n")

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
        results = []

        if not tests:
            log.write("Error: no tests found\n")
            log.write("Final verdict: NO_TESTS\n")
            return "NO_TESTS"

        for test in tests:
            verdict = run_test(test["input"], test["answer"], checker_bin)
            log.write(
                f"Test {test['name']}: {verdict}"
                f" [visibility={test.get('visibility', 'private')}, subtask={test.get('subtask', 1)}]\n"
            )
            results.append(verdict)

        # Финальный вердикт
        if "RE" in results:
            final = "RE"
        elif "TL" in results:
            final = "TL"
        elif "WA" in results:
            final = "WA"
        elif all(r == "OK" for r in results):
            final = "OK"
        else:
            final = "PARTIAL"

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
