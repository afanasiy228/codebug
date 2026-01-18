import os
import json
import subprocess
import tempfile
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import time

import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)  # разрешаем CORS всем источникам

JUDGE_SCRIPT = "judge.py"
SOL_FILE = "sol.cpp"
TASKS_REPO_URL = os.getenv("TASKS_REPO_URL", "git@github.com:afanasiy228/taskscodebug.git")
TASKS_REPO_DIR = os.getenv("TASKS_REPO_DIR", "tasks")
TASKS_REPO_KEY_FILE = os.getenv("TASKS_REPO_KEY_FILE", "/etc/secrets/codebug_tasks_deploy")
TASKS_SYNC_TTL = int(os.getenv("TASKS_SYNC_TTL", "300"))
TASKS_COMMIT_NAME = os.getenv("TASKS_COMMIT_NAME", "CodeBug Admin")
TASKS_COMMIT_EMAIL = os.getenv("TASKS_COMMIT_EMAIL", "admin@codebug.local")
LAST_TASKS_SYNC = 0.0
MAX_GENERATED_TESTS = int(os.getenv("MAX_GENERATED_TESTS", "200"))

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


def _git_env():
    return {
        **os.environ,
        "GIT_SSH_COMMAND": (
            f"ssh -i {TASKS_REPO_KEY_FILE} "
            "-o IdentitiesOnly=yes -o StrictHostKeyChecking=no"
        )
    }


def sync_tasks_repo(force=False):
    global LAST_TASKS_SYNC
    now = time.time()
    if not force and LAST_TASKS_SYNC and now - LAST_TASKS_SYNC < TASKS_SYNC_TTL:
        return True

    try:
        if os.path.isdir(os.path.join(TASKS_REPO_DIR, ".git")):
            subprocess.run(
                ["git", "-C", TASKS_REPO_DIR, "pull", "--ff-only"],
                check=True,
                capture_output=True,
                text=True,
                env=_git_env()
            )
        else:
            if os.path.isdir(TASKS_REPO_DIR):
                subprocess.run(
                    ["rm", "-rf", TASKS_REPO_DIR],
                    check=True
                )
            subprocess.run(
                ["git", "clone", TASKS_REPO_URL, TASKS_REPO_DIR],
                check=True,
                capture_output=True,
                text=True,
                env=_git_env()
            )
        LAST_TASKS_SYNC = now
        return True
    except Exception as e:
        print("Tasks sync failed:", e)
        return False


def task_dir(task_id):
    return os.path.join(TASKS_REPO_DIR, str(task_id))


def safe_task_file(task_id, filename):
    if ".." in filename or filename.startswith("/") or "\\\\" in filename:
        return None
    allowed = {
        "meta.json",
        "statement.md",
        "help.md",
        "code.cpp",
        "tests/1.in",
        "tests/1.out",
        "tests/2.in",
        "tests/2.out",
    }
    if filename not in allowed:
        return None
    path = os.path.join(task_dir(task_id), filename)
    if not os.path.isfile(path):
        return None
    return path


def list_tasks():
    tasks = []
    if not os.path.isdir(TASKS_REPO_DIR):
        return tasks
    for name in os.listdir(TASKS_REPO_DIR):
        if not name.isdigit():
            continue
        meta_path = os.path.join(TASKS_REPO_DIR, name, "meta.json")
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            tasks.append(meta)
        except Exception as e:
            print(f"Meta load failed for {name}:", e)
    tasks.sort(key=lambda x: int(x.get("id", 0)))
    return tasks


def _ensure_git_identity():
    try:
        subprocess.run(
            ["git", "-C", TASKS_REPO_DIR, "config", "user.name", TASKS_COMMIT_NAME],
            check=True,
            capture_output=True,
            text=True
        )
        subprocess.run(
            ["git", "-C", TASKS_REPO_DIR, "config", "user.email", TASKS_COMMIT_EMAIL],
            check=True,
            capture_output=True,
            text=True
        )
    except Exception as e:
        print("Git identity config failed:", e)


def _next_task_id():
    existing = []
    if not os.path.isdir(TASKS_REPO_DIR):
        return 0
    for name in os.listdir(TASKS_REPO_DIR):
        if name.isdigit():
            existing.append(int(name))
    return (max(existing) + 1) if existing else 0


def _write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _compile_cpp(src_path, out_path):
    result = subprocess.run(
        ["g++", "-std=c++17", "-O2", src_path, "-o", out_path],
        capture_output=True,
        text=True
    )
    return result


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
    final = "CE"
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


@app.route("/tasks/list", methods=["GET"])
def tasks_list():
    if not sync_tasks_repo():
        return jsonify({"error": "tasks_sync_failed"}), 500
    return jsonify(list_tasks())


@app.route("/tasks/<int:task_id>/<path:filename>", methods=["GET"])
def tasks_file(task_id, filename):
    if not sync_tasks_repo():
        return jsonify({"error": "tasks_sync_failed"}), 500
    path = safe_task_file(task_id, filename)
    if not path:
        return abort(404)
    return send_file(path)


@app.route("/tasks/create", methods=["POST"])
def tasks_create():
    if not sync_tasks_repo():
        return jsonify({"error": "tasks_sync_failed"}), 500

    data = request.get_json(silent=True) or {}
    meta = data.get("meta") or {}
    files = data.get("files") or {}
    tests = data.get("tests") or []

    task_id = meta.get("id")
    if not isinstance(task_id, int):
        task_id = _next_task_id()
        meta["id"] = task_id

    title = meta.get("title")
    if not title:
        return jsonify({"error": "title_required"}), 400

    task_path = task_dir(task_id)
    _write_text(os.path.join(task_path, "meta.json"), json.dumps(meta, ensure_ascii=False, indent=2))

    if files.get("statement"):
        _write_text(os.path.join(task_path, "statement.md"), files["statement"])
    if files.get("help"):
        _write_text(os.path.join(task_path, "help.md"), files["help"])
    if files.get("code"):
        _write_text(os.path.join(task_path, "code.cpp"), files["code"])
    if files.get("solution"):
        _write_text(os.path.join(task_path, "sol.cpp"), files["solution"])
    if files.get("generator"):
        _write_text(os.path.join(task_path, "generator.cpp"), files["generator"])

    tests_path = os.path.join(task_path, "tests")
    for idx, t in enumerate(tests, start=1):
        inp = t.get("input", "")
        out = t.get("output", "")
        _write_text(os.path.join(tests_path, f"{idx}.in"), inp)
        _write_text(os.path.join(tests_path, f"{idx}.out"), out)

    _ensure_git_identity()
    try:
        subprocess.run(
            ["git", "-C", TASKS_REPO_DIR, "add", f"{task_id}"],
            check=True,
            capture_output=True,
            text=True
        )
        subprocess.run(
            ["git", "-C", TASKS_REPO_DIR, "commit", "-m", f"Add task {task_id}"],
            check=True,
            capture_output=True,
            text=True,
            env=_git_env()
        )
        subprocess.run(
            ["git", "-C", TASKS_REPO_DIR, "push"],
            check=True,
            capture_output=True,
            text=True,
            env=_git_env()
        )
    except Exception as e:
        print("Task create git failed:", e)
        return jsonify({"error": "git_failed"}), 500

    return jsonify({"status": "ok", "id": task_id})


@app.route("/tasks/delete", methods=["POST"])
def tasks_delete():
    if not sync_tasks_repo():
        return jsonify({"error": "tasks_sync_failed"}), 500

    data = request.get_json(silent=True) or {}
    task_id = data.get("id")
    if not isinstance(task_id, int):
        return jsonify({"error": "id_required"}), 400

    task_path = task_dir(task_id)
    if not os.path.isdir(task_path):
        return jsonify({"error": "not_found"}), 404

    try:
        subprocess.run(
            ["rm", "-rf", task_path],
            check=True
        )
    except Exception as e:
        print("Task delete failed:", e)
        return jsonify({"error": "delete_failed"}), 500

    _ensure_git_identity()
    try:
        subprocess.run(
            ["git", "-C", TASKS_REPO_DIR, "add", "-A"],
            check=True,
            capture_output=True,
            text=True
        )
        subprocess.run(
            ["git", "-C", TASKS_REPO_DIR, "commit", "-m", f"Delete task {task_id}"],
            check=True,
            capture_output=True,
            text=True,
            env=_git_env()
        )
        subprocess.run(
            ["git", "-C", TASKS_REPO_DIR, "push"],
            check=True,
            capture_output=True,
            text=True,
            env=_git_env()
        )
    except Exception as e:
        print("Task delete git failed:", e)
        return jsonify({"error": "git_failed"}), 500

    return jsonify({"status": "ok", "id": task_id})


@app.route("/tasks/generate-tests", methods=["POST"])
def tasks_generate_tests():
    data = request.get_json(silent=True) or {}
    generator_code = data.get("generator", "")
    solution_code = data.get("solution", "")
    count = data.get("count", 0)

    if not isinstance(count, int) or count <= 0:
        return jsonify({"error": "count_required"}), 400
    if count > MAX_GENERATED_TESTS:
        return jsonify({"error": "count_too_large"}), 400
    if not generator_code.strip():
        return jsonify({"error": "generator_required"}), 400
    if not solution_code.strip():
        return jsonify({"error": "solution_required"}), 400

    with tempfile.TemporaryDirectory() as tmp:
        gen_src = os.path.join(tmp, "generator.cpp")
        sol_src = os.path.join(tmp, "solution.cpp")
        gen_bin = os.path.join(tmp, "gen")
        sol_bin = os.path.join(tmp, "sol")

        _write_text(gen_src, generator_code)
        _write_text(sol_src, solution_code)

        gen_compile = _compile_cpp(gen_src, gen_bin)
        if gen_compile.returncode != 0:
            return jsonify({
                "error": "generator_compile_failed",
                "details": gen_compile.stderr
            }), 400

        sol_compile = _compile_cpp(sol_src, sol_bin)
        if sol_compile.returncode != 0:
            return jsonify({
                "error": "solution_compile_failed",
                "details": sol_compile.stderr
            }), 400

        tests = []
        for i in range(1, count + 1):
            gen_run = subprocess.run(
                [gen_bin, str(i)],
                capture_output=True,
                text=True,
                timeout=5
            )
            if gen_run.returncode != 0:
                return jsonify({
                    "error": "generator_runtime_failed",
                    "details": gen_run.stderr,
                    "index": i
                }), 400

            inp = gen_run.stdout
            sol_run = subprocess.run(
                [sol_bin],
                input=inp,
                capture_output=True,
                text=True,
                timeout=5
            )
            if sol_run.returncode != 0:
                return jsonify({
                    "error": "solution_runtime_failed",
                    "details": sol_run.stderr,
                    "index": i
                }), 400
            tests.append({
                "input": inp,
                "output": sol_run.stdout
            })

        return jsonify({"tests": tests})
    

if __name__ == "__main__":
    print("=== LOCAL JUDGE SERVER ===")
    port = int(os.getenv("PORT", "7777"))
    print(f"Запуск на http://127.0.0.1:{port}")
    sync_tasks_repo(force=True)
    app.run(host="0.0.0.0", port=port)
