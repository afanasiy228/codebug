import os
import subprocess
import sys
import glob

# --- Настройки ---
TIME_LIMIT = 3  # лимит времени на программу
SOURCE = "sol.cpp"     # сервер сохраняет код сюда
BINARY = "sol"         # бинарник
LOG_FILE = "log.txt"   # вывод для просмотра

def task_dir(task):
    return os.path.join("tasks", task)

def compile_cpp():
    if not os.path.exists(SOURCE):
        with open(LOG_FILE, "w") as log:
            log.write("Compilation Error\nsol.cpp not found\n")
        return False

    res = subprocess.run(
        [
            "g++", "-std=c++17", "-O2",
            SOURCE, "-o", BINARY
        ],
        capture_output=True,
        text=True
    )

    if res.returncode != 0:
        with open(LOG_FILE, "w") as log:
            log.write("Compilation Error\n")
            log.write(res.stderr)
        return False

    return True


def run_test(binary, inp_file, out_file):
    try:
        with open(inp_file, "r") as fin:
            proc = subprocess.run(
                [f"./{binary}"],
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

    program_output = proc.stdout.strip()

    with open(out_file, "r") as f:
        correct_output = f.read().strip()

    return "OK" if program_output == correct_output else "WA"


def judge(task_id):
    task_path = task_dir(task_id)
    tests_path = os.path.join(task_path, "tests")

    if not os.path.isdir(tests_path):
        with open(LOG_FILE, "w") as log:
            log.write("Error: tests folder not found\n")
        return "NO_TESTS"

    # Компиляция
    if not compile_cpp():
        return "CE"

    tests = sorted(glob.glob(os.path.join(tests_path, "*.in")))

    results = []

    with open(LOG_FILE, "w") as log:
        log.write(f"Task {task_id}\n")

        for inp in tests:
            test_num = os.path.splitext(os.path.basename(inp))[0]
            out_file = os.path.join(tests_path, test_num + ".out")

            verdict = run_test(BINARY, inp, out_file)
            log.write(f"Test {test_num}: {verdict}\n")
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