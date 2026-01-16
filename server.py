import os
import json
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS
import time

import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)  # разрешаем CORS всем источникам

JUDGE_SCRIPT = "judge.py"
SOL_FILE = "sol.cpp"

FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")
FIREBASE_SERVICE_ACCOUNT = os.getenv("FIREBASE_SERVICE_ACCOUNT")
FIREBASE_SERVICE_ACCOUNT_FILE = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE", "/etc/secrets/serviceAccountKey.json")


def init_firebase():
    if firebase_admin._apps:
        return True
    if not FIREBASE_DB_URL:
        print("FIREBASE_DB_URL не задан")
        return False

    cred_data = None
    if FIREBASE_SERVICE_ACCOUNT:
        try:
            cred_data = json.loads(FIREBASE_SERVICE_ACCOUNT)
        except json.JSONDecodeError:
            print("FIREBASE_SERVICE_ACCOUNT невалидный JSON")
            return False
    elif os.path.exists(FIREBASE_SERVICE_ACCOUNT_FILE):
        with open(FIREBASE_SERVICE_ACCOUNT_FILE, "r") as f:
            cred_data = json.load(f)
    else:
        print("Ключ Firebase не найден")
        return False

    cred = credentials.Certificate(cred_data)
    firebase_admin.initialize_app(cred, {
        "databaseURL": FIREBASE_DB_URL
    })
    print("Firebase Admin init OK")
    return True


FIREBASE_READY = init_firebase()


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
    login = data.get("user")
    contest_id = data.get("contestId")

    if not task or not code or not login:
        return jsonify({
            "error": "task / code / user missing",
            "status": "BAD_REQUEST"
        }), 400

    print(f"Task = {task}")
    print("Code length:", len(code))
    print("User =", login)

    submission_ref = None
    firebase_error = None
    firebase_saved = False

    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()

    if FIREBASE_READY:
        record = {
            "login": str(login),
            "task": int(task),
            "verdict": "QUEUE",
            "date": int(time.time() * 1000),
            "contestId": contest_id or None
        }
        try:
            submission_ref = db.reference("submissions/global").push()
            submission_ref.set(record)
            submission_ref.update({"verdict": "TESTING"})
            firebase_saved = True
        except Exception as e:
            firebase_error = f"firebase_write_error: {e}"
            print(firebase_error)
    else:
        firebase_error = "firebase_not_ready"

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
        if submission_ref is not None:
            submission_ref.update({"verdict": "TL"})
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
    if submission_ref is not None:
        try:
            submission_ref.update({"verdict": final})
        except Exception as e:
            firebase_error = f"firebase_update_error: {e}"
            print(firebase_error)

    return jsonify({
        "status": final,
        "log": log_text,
        "submissionId": submission_ref.key if submission_ref is not None else None,
        "firebaseSaved": firebase_saved,
        "firebaseError": firebase_error
    })
    

if __name__ == "__main__":
    print("=== LOCAL JUDGE SERVER ===")
    port = int(os.getenv("PORT", "7777"))
    print(f"Запуск на http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port)
