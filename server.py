import os
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app)  # разрешаем CORS всем источникам

JUDGE_SCRIPT = "judge.py"
SOL_FILE = "sol.cpp"


@app.route("/submit", methods=["POST", "OPTIONS"])
def submit():
    # --- OPTIONS preflight ---
    if request.method == "OPTIONS":
        print("=== OPTIONS OK ===")
        return ("", 200)

    print("\n=== ПОЛУЧЕН POST /submit ===")

    # --- читаем JSON ---
    data = request.get_json(silent=True)
    print("JSON RAW:", data)

    if not data:
        return jsonify({
            "error": "No JSON received",
            "status": "BAD_REQUEST"
        }), 400

    task = str(data.get("task"))
    code = data.get("code")

    if not task or not code:
        return jsonify({
            "error": "task / code missing",
            "status": "BAD_REQUEST"
        }), 400

    print(f"Task = {task}")
    print("Code length:", len(code))

    # --- записываем sol.cpp ---
    try:
        with open(SOL_FILE, "w") as f:
            f.write(code)
        print("sol.cpp записан")
    except Exception as e:
        print("Ошибка записи sol.cpp:", e)
        return jsonify({"error": "write_error"}), 500

    # --- запускаем judge ---
    print("Запуск judge.py...")
    try:
        result = subprocess.run(
            ["python3", JUDGE_SCRIPT, task],
            capture_output=True,
            text=True,
            timeout=20
        )
    except subprocess.TimeoutExpired:
        return jsonify({"status": "JUDGE_TIMEOUT"}), 500

    print("judge.py завершён")

    # читаем log.txt
    try:
        with open("log.txt", "r") as f:
            log_text = f.read()
    except:
        log_text = "(log.txt не найден)"

    # --- определение финального вердикта ---
    final = "UNKNOWN"
    for line in log_text.splitlines():
        if line.startswith("Final verdict:"):
            final = line.split(":")[1].strip()

    print("Final verdict =", final)

    return jsonify({
        "status": final,
        "log": log_text
    })
    

if __name__ == "__main__":
    print("=== LOCAL JUDGE SERVER ===")
    print("Запуск на http://127.0.0.1:7777")
    app.run(host="0.0.0.0", port=7777)