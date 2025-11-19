import os
import subprocess
import sys
import glob

# --- Настройки ---
SOURCE = "code.cpp"
BINARY = "code"
TIME_LIMIT = 2  # сек

def task_dir(task):
    return os.path.join("tasks", task)

def compile_solution(task):
    source_path = os.path.join(task_dir(task), SOURCE)
    binary_path = os.path.join(task_dir(task), BINARY)

    if not os.path.exists(source_path):
        print(f"{source_path} not found")
        sys.exit(1)

    res = subprocess.run(
        ["g++", "-std=c++17", "-O2", "-Wall",
         source_path, "-o", binary_path],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print("Compilation Error:")
        print(res.stderr)
        sys.exit(1)

    return binary_path

def generate_outputs(task):
    binary_path = compile_solution(task)
    test_inputs = sorted(glob.glob(os.path.join(task_dir(task), "tests", "*.in")))

    for inp in test_inputs:
        num = os.path.splitext(os.path.basename(inp))[0]
        out_file = os.path.join(task_dir(task), "tests", f"{num}.out")

        with open(inp, "r") as fin, open(out_file, "w") as fout:
            subprocess.run(
                [binary_path],
                stdin=fin,
                stdout=fout,
                stderr=subprocess.PIPE,
                timeout=TIME_LIMIT,
                text=True,
            )
            print(f"{num}.out generated")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 gen_tests.py <task_number>")
        sys.exit(1)

    TASK = sys.argv[1]
    generate_outputs(TASK)