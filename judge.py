import os
import subprocess
import sys
import glob

# --- Настройки ---
TIME_LIMIT = 5      # лимит времени в секундах
TASK = "-1"          # <-- номер задачи по умолчанию
SOURCE = "sol.cpp"  # sol.cpp всегда лежит в корне
BINARY = "sol"      # бинарник тоже в корне
LOG_FILE = "log.txt"  # итоговый лог в корне

def task_dir():
    return os.path.join("problems", TASK)

def compile_solution():
    if not os.path.exists(SOURCE):
        print(f"{SOURCE} not found in root folder")
        sys.exit(1)

    res = subprocess.run(
        ["g++", "-std=c++17", "-O2", "-Wall",
         SOURCE, "-o", BINARY,
         "-fsanitize=address,undefined,bounds",
         "-fno-sanitize-recover=all"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        with open(LOG_FILE, "w") as log:
            log.write("Compilation Error\n")
            log.write(res.stderr)
        sys.exit(1)

def run_test(input_file, output_file):
    try:
        with open(input_file, "r") as fin:
            proc = subprocess.run(
                [f"./{BINARY}"],
                stdin=fin,
                capture_output=True,
                timeout=TIME_LIMIT,
                text=True,
            )
    except subprocess.TimeoutExpired:
        return "TL"
    except Exception:
        return "RE"

    if proc.returncode != 0:
        return "RE"

    out_prog = proc.stdout.strip()
    with open(output_file, "r") as f2:
        out_corr = f2.read().strip()

    return "OK" if out_prog == out_corr else "WA"

def judge():
    compile_solution()
    test_inputs = sorted(glob.glob(os.path.join(task_dir(), "tests", "*.in")))

    results = []
    with open(LOG_FILE, "w") as log:
        log.write(f"Task {TASK}\n")
        for inp in test_inputs:
            num = os.path.splitext(os.path.basename(inp))[0]
            out_file = os.path.join(task_dir(), "tests", f"{num}.out")
            verdict = run_test(inp, out_file)
            log.write(f"Test {num}: {verdict}\n")
            results.append(verdict)

        # Итог
        if "RE" in results:
            final = "RE"
        elif "TL" in results:
            final = "TL"
        elif "WA" in results:
            final = "WA"
        elif all(v == "OK" for v in results):
            final = "OK"
        else:
            final = "PARTIAL"

        log.write(f"Final verdict: {final}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 judge.py <task_number>")
        sys.exit(1)

    TASK = sys.argv[1]
    judge()
    print(f"СПЕЦИАЛЬНО ДЛЯ ФОКИ, ВЫВОД ЛЕЖИТ В {LOG_FILE}!!!!!!!!")
