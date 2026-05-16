import os
import json
import subprocess
import tempfile
import re
import shutil
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import time
import platform
import resource
import urllib.parse
import urllib.request
import html

import firebase_admin
from firebase_admin import credentials, db
from firebase_admin import auth as admin_auth

app = Flask(__name__)
CORS(app)  # разрешаем CORS всем источникам

JUDGE_SCRIPT = "judge.py"
TASKS_REPO_URL = os.getenv("TASKS_REPO_URL", "git@github.com:afanasiy228/taskscodebug.git")
TASKS_REPO_DIR = os.getenv("TASKS_REPO_DIR", ".tasks_repo")
TASKS_REPO_KEY_FILE = os.getenv("TASKS_REPO_KEY_FILE", "/etc/secrets/codebug_tasks_deploy")
TASKS_SYNC_TTL = int(os.getenv("TASKS_SYNC_TTL", "300"))
TASKS_COMMIT_NAME = os.getenv("TASKS_COMMIT_NAME", "CodeBug Admin")
TASKS_COMMIT_EMAIL = os.getenv("TASKS_COMMIT_EMAIL", "admin@codebug.local")
LAST_TASKS_SYNC = 0.0
MAX_GENERATED_TESTS = int(os.getenv("MAX_GENERATED_TESTS", "200"))
JUDGE_PROCESS_TIMEOUT = int(os.getenv("JUDGE_PROCESS_TIMEOUT", "120"))
SUPPORTED_LANGUAGES = {"cpp", "python"}

FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")
FIREBASE_SERVICE_ACCOUNT = os.getenv("FIREBASE_SERVICE_ACCOUNT")
FIREBASE_SERVICE_ACCOUNT_FILE = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE", "/etc/secrets/serviceAccountKey.json")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")
RECAPTCHA_VERIFY_URL = os.getenv("RECAPTCHA_VERIFY_URL", "https://www.google.com/recaptcha/api/siteverify")
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "")
PUBLIC_FIREBASE_WEB_API_KEY = os.getenv("PUBLIC_FIREBASE_WEB_API_KEY", "")
PUBLIC_FIREBASE_WEB_AUTH_DOMAIN = os.getenv("PUBLIC_FIREBASE_WEB_AUTH_DOMAIN", "")
PUBLIC_FIREBASE_WEB_DATABASE_URL = os.getenv("PUBLIC_FIREBASE_WEB_DATABASE_URL", "")
PUBLIC_FIREBASE_WEB_PROJECT_ID = os.getenv("PUBLIC_FIREBASE_WEB_PROJECT_ID", "")
PUBLIC_FIREBASE_WEB_STORAGE_BUCKET = os.getenv("PUBLIC_FIREBASE_WEB_STORAGE_BUCKET", "")
PUBLIC_FIREBASE_WEB_MESSAGING_SENDER_ID = os.getenv("PUBLIC_FIREBASE_WEB_MESSAGING_SENDER_ID", "")
PUBLIC_FIREBASE_WEB_APP_ID = os.getenv("PUBLIC_FIREBASE_WEB_APP_ID", "")


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


def _is_admin_request():
    if ADMIN_API_KEY:
        header_key = request.headers.get("X-Admin-Key", "")
        body = request.get_json(silent=True) or {}
        body_key = body.get("adminKey", "")
        if header_key == ADMIN_API_KEY or body_key == ADMIN_API_KEY:
            return True

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False

    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return False

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return False

    try:
        decoded = admin_auth.verify_id_token(token)
        uid = decoded.get("uid")
        if not uid:
            return False
        login = db.reference(f"userAuthMap/{uid}").get()
        if not login:
            return False
        return bool(db.reference(f"admins/{login}").get())
    except Exception as e:
        print("Admin auth failed:", e)
        return False


def _git_env():
    return {
        **os.environ,
        "GIT_SSH_COMMAND": (
            f"ssh -i {TASKS_REPO_KEY_FILE} "
            "-o IdentitiesOnly=yes -o StrictHostKeyChecking=no"
        )
    }


def _verify_captcha_token(token, remote_ip=None):
    if not RECAPTCHA_SECRET_KEY:
        return False, "captcha_not_configured"
    if not token:
        return False, "captcha_token_required"

    payload = {
        "secret": RECAPTCHA_SECRET_KEY,
        "response": token
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        RECAPTCHA_VERIFY_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            result = json.loads(raw)
    except Exception as e:
        print("Captcha verify request failed:", e)
        return False, "captcha_verify_unavailable"

    if result.get("success"):
        return True, None
    codes = result.get("error-codes") or []
    if isinstance(codes, list) and codes:
        return False, "captcha_" + str(codes[0]).replace("-", "_")
    return False, "captcha_invalid"


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


def normalize_language(lang):
    val = str(lang or "").strip().lower()
    if val in ("c++", "cpp", "cc", "cxx"):
        return "cpp"
    if val in ("py", "python", "python3"):
        return "python"
    return "cpp"


def language_file_map(lang):
    norm = normalize_language(lang)
    if norm == "python":
        return {
            "code": "code.py",
            "solution": "sol.py",
            "generator": "generator.py"
        }
    return {
        "code": "code.cpp",
        "solution": "sol.cpp",
        "generator": "generator.cpp"
    }


def _read_json(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        print(f"JSON load failed for {path}:", e)
        return None


def _problem_path(task_id):
    return os.path.join(task_dir(task_id), "problem.json")


def _meta_path(task_id):
    return os.path.join(task_dir(task_id), "meta.json")


def _task_has_v2(task_id):
    return os.path.isfile(_problem_path(task_id))


def _pad_test_name(idx):
    return str(idx).zfill(3)


def _legacy_tests_manifest(task_id):
    tests_path = os.path.join(task_dir(task_id), "tests")
    if not os.path.isdir(tests_path):
        return []
    tests = []
    for filename in os.listdir(tests_path):
        match = re.fullmatch(r"([1-9]\d*)\.in", filename)
        if not match:
            continue
        num = match.group(1)
        out_name = f"{num}.out"
        if not os.path.isfile(os.path.join(tests_path, out_name)):
            continue
        tests.append({
            "name": num,
            "input": f"tests/{num}.in",
            "answer": f"tests/{num}.out",
            "visibility": "open" if len(tests) < 2 else "private",
            "subtask": 1
        })
    tests.sort(key=lambda item: int(item["name"]))
    return tests


def read_problem_config(task_id):
    problem = _read_json(_problem_path(task_id))
    if problem:
        problem["id"] = int(problem.get("id", task_id))
        problem["formatVersion"] = int(problem.get("formatVersion", problem.get("schemaVersion", 2)))
        problem["schemaVersion"] = int(problem.get("schemaVersion", 2))
        problem["language"] = normalize_language(problem.get("language"))
        problem.setdefault("taskType", "standard")
        problem.setdefault("checker", {"type": "standard"})
        problem.setdefault("statement", {
            "html": "statement/russian.html",
            "tex": "statement/russian.tex"
        })
        problem.setdefault("files", {})
        problem.setdefault("tests", [])
        problem.setdefault("groups", problem.get("subtasks", []))
        problem.setdefault("subtasks", [])
        problem.pop("author", None)
        return problem

    if not os.path.isfile(_meta_path(task_id)):
        return None

    meta = _read_json(_meta_path(task_id)) or {}
    lang = normalize_language(meta.get("language"))
    file_names = language_file_map(lang)
    problem = {
        "formatVersion": 1,
        "schemaVersion": 1,
        "id": int(meta.get("id", task_id)),
        "title": meta.get("title") or f"Задача {task_id}",
        "difficulty": meta.get("difficulty", ""),
        "language": lang,
        "type": meta.get("type", ""),
        "tags": meta.get("tags") or [],
        "taskType": "standard",
        "checker": {"type": "standard"},
        "statement": {
            "markdown": "statement.md"
        },
        "files": {
            "code": file_names["code"],
            "solution": file_names["solution"],
            "generator": file_names["generator"]
        },
        "tests": _legacy_tests_manifest(task_id),
        "groups": [{
            "id": 1,
            "name": "all",
            "points": 100,
            "dependencies": [],
            "tests": []
        }],
        "subtasks": [{
            "id": 1,
            "name": "all",
            "score": 100
        }]
    }
    problem.pop("author", None)
    return problem


def read_task_meta(task_id):
    problem = read_problem_config(task_id)
    if not problem:
        return {}
    return {
        "id": problem.get("id"),
        "title": problem.get("title", ""),
        "difficulty": problem.get("difficulty", ""),
        "language": normalize_language(problem.get("language")),
        "type": problem.get("type", ""),
        "tags": problem.get("tags") or []
    }


def public_problem_meta(problem):
    tests = problem.get("tests") or []
    open_tests = [t for t in tests if t.get("visibility", "private") == "open"]
    public_tests = [{
        "id": t.get("id"),
        "name": t.get("name"),
        "visibility": t.get("visibility", "private"),
        "group": t.get("group", t.get("subtask", 1)),
        "subtask": t.get("subtask", 1),
        "points": t.get("points", 0)
    } for t in tests]
    checker = problem.get("checker") or {"type": "standard"}
    files = problem.get("files") or {}
    return {
        "formatVersion": problem.get("formatVersion", problem.get("schemaVersion", 2)),
        "schemaVersion": problem.get("schemaVersion", 2),
        "id": problem.get("id"),
        "title": problem.get("title", ""),
        "difficulty": problem.get("difficulty", ""),
        "language": normalize_language(problem.get("language")),
        "type": problem.get("type", ""),
        "tags": problem.get("tags") or [],
        "taskType": problem.get("taskType", "standard"),
        "statement": problem.get("statement") or {},
        "files": {
            "code": files.get("code")
        },
        "checker": {
            "type": checker.get("type", "standard")
        },
        "groups": problem.get("groups") or problem.get("subtasks") or [],
        "subtasks": problem.get("subtasks") or [],
        "tests": public_tests,
        "openTests": open_tests,
        "testCount": len(tests),
        "openTestCount": len(open_tests)
    }


def _test_entry_by_path(task_id, filename):
    problem = read_problem_config(task_id)
    if not problem:
        return None
    for test in problem.get("tests") or []:
        if filename in (test.get("input"), test.get("answer")):
            return test
    return None


def safe_task_file(task_id, filename):
    if ".." in filename or filename.startswith("/") or "\\\\" in filename:
        return None
    if filename == "problem.json":
        path = _problem_path(task_id)
        return path if os.path.isfile(path) else None

    problem = read_problem_config(task_id)
    if not problem:
        return None

    statement = problem.get("statement") or {}
    files = problem.get("files") or {}
    public_exact = {
        statement.get("html"),
        statement.get("tex"),
        statement.get("hint"),
        files.get("code")
    }
    public_exact = {item for item in public_exact if item}
    if filename.startswith("statement/assets/"):
        public_exact.add(filename)

    if problem.get("schemaVersion") == 1:
        public_exact.update({
            "statement.md",
            "help.md",
            files.get("code"),
        })

    allowed_exact = {
        "meta.json",
    }
    is_v2_test_file = re.fullmatch(r"tests/\d{3}(\.a)?", filename) is not None
    is_legacy_test_file = re.fullmatch(r"tests/[1-9]\d*\.(in|out)", filename) is not None
    if is_v2_test_file:
        test = _test_entry_by_path(task_id, filename)
        if not test or test.get("visibility", "private") != "open":
            return None
    if is_legacy_test_file:
        test = _test_entry_by_path(task_id, filename)
        if not test or test.get("visibility", "private") != "open":
            return None
    if filename not in allowed_exact and filename not in public_exact and not is_legacy_test_file and not is_v2_test_file:
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
        if not os.path.isfile(_problem_path(name)) and not os.path.isfile(_meta_path(name)):
            continue
        try:
            problem = read_problem_config(name)
            tasks.append(public_problem_meta(problem))
        except Exception as e:
            print(f"Task load failed for {name}:", e)
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


def _read_text(path):
    if not path or not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _task_text(task_id, relpath):
    if not relpath or ".." in relpath or relpath.startswith("/") or "\\\\" in relpath:
        return ""
    base = os.path.abspath(task_dir(task_id))
    path = os.path.abspath(os.path.join(base, relpath))
    if path != base and not path.startswith(base + os.sep):
        return ""
    return _read_text(path)


def _statement_to_html(text):
    escaped = html.escape(text or "").strip()
    if not escaped:
        return "<p>Условие пока не заполнено.</p>\n"
    blocks = [p.strip() for p in re.split(r"\n\s*\n", escaped) if p.strip()]
    return "\n".join(f"<p>{block.replace(chr(10), '<br>')}</p>" for block in blocks) + "\n"


def _safe_int(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_int_list(value):
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(result))


def _normalize_groups(raw_groups, test_manifest):
    tests_by_group = {}
    for test in test_manifest:
        gid = _safe_int(test.get("group"), 1)
        tests_by_group.setdefault(gid, []).append(test["name"])

    groups = []
    seen = set()
    if isinstance(raw_groups, list):
        for item in raw_groups:
            if not isinstance(item, dict):
                continue
            gid = _safe_int(item.get("id"), 0)
            if gid <= 0 or gid in seen:
                continue
            seen.add(gid)
            groups.append({
                "id": gid,
                "name": str(item.get("name") or f"group {gid}"),
                "points": _safe_int(item.get("points"), 0),
                "dependencies": _safe_int_list(item.get("dependencies")),
                "tests": [str(t) for t in (item.get("tests") or tests_by_group.get(gid, []))]
            })

    for gid in sorted(tests_by_group):
        if gid in seen:
            continue
        seen.add(gid)
        groups.append({
            "id": gid,
            "name": f"group {gid}",
            "points": 100 if len(tests_by_group) == 1 else 0,
            "dependencies": [],
            "tests": tests_by_group[gid]
        })

    if not groups:
        groups.append({
            "id": 1,
            "name": "group 1",
            "points": 100,
            "dependencies": [],
            "tests": []
        })
    return sorted(groups, key=lambda item: item["id"])


def _build_problem_v2(task_id, meta, files, tests):
    lang = normalize_language(meta.get("language"))
    ext = "py" if lang == "python" else "cpp"
    test_manifest = []
    for idx, t in enumerate(tests, start=1):
        name = _pad_test_name(idx)
        visibility = str(t.get("visibility") or ("open" if idx <= 2 else "private")).lower()
        if visibility not in ("open", "private"):
            visibility = "private"
        group = _safe_int(t.get("group", t.get("subtask", 1)), 1)
        if group <= 0:
            group = 1
        subtask = _safe_int(t.get("subtask", group), group)
        points = _safe_int(t.get("points"), 0)
        test_manifest.append({
            "id": idx,
            "name": name,
            "input": f"tests/{name}",
            "answer": f"tests/{name}.a",
            "visibility": visibility,
            "group": group,
            "subtask": subtask,
            "points": points
        })

    checker_path = "checker/checker.cpp" if files.get("checker") else None
    checker = {
        "type": "custom" if checker_path else "standard"
    }
    if checker_path:
        checker["path"] = checker_path

    groups = _normalize_groups(meta.get("groups"), test_manifest)
    subtasks = [{
        "id": group["id"],
        "name": group["name"],
        "score": group["points"],
        "dependencies": group["dependencies"],
        "tests": group["tests"]
    } for group in groups]

    return {
        "formatVersion": 2,
        "schemaVersion": 2,
        "id": task_id,
        "title": meta.get("title") or f"Задача {task_id}",
        "difficulty": meta.get("difficulty", ""),
        "language": lang,
        "type": meta.get("type", ""),
        "tags": meta.get("tags") or [],
        "taskType": meta.get("taskType", "standard"),
        "statement": {
            "language": "ru",
            "tex": "statement/russian.tex",
            "html": "statement/russian.html",
            "assets": "statement/assets",
            **({"hint": "statement/hint.md"} if files.get("help") else {})
        },
        "files": {
            "code": f"solutions/wa.{ext}",
            "solution": f"solutions/main.{ext}",
            "generator": f"generator/gen.{ext}",
            **({"validator": "validator/validator.cpp"} if files.get("validator") else {}),
            **({"checker": checker_path} if checker_path else {})
        },
        "checker": checker,
        "tests": test_manifest,
        "groups": groups,
        "subtasks": subtasks
    }


def _compile_cpp(src_path, out_path):
    result = subprocess.run(
        ["g++", "-std=c++17", "-O2", src_path, "-o", out_path],
        capture_output=True,
        text=True
    )
    return result


def _compile_python(src_path):
    return subprocess.run(
        ["python3", "-m", "py_compile", src_path],
        capture_output=True,
        text=True
    )


def _run_with_limits(cmd, input_data, timeout_sec):
    time_cmd = "/usr/bin/time"
    mem_kb = None
    start = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            if os.path.exists(time_cmd):
                mem_file = os.path.join(tmp, "mem.txt")
                run_res = subprocess.run(
                    [time_cmd, "-f", "%M", "-o", mem_file, *cmd],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec
                )
                try:
                    with open(mem_file, "r") as mf:
                        mem_kb = int(mf.read().strip() or "0")
                except Exception:
                    mem_kb = None
            else:
                before = resource.getrusage(resource.RUSAGE_CHILDREN)
                run_res = subprocess.run(
                    cmd,
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec
                )
                after = resource.getrusage(resource.RUSAGE_CHILDREN)
                delta = max(0, after.ru_maxrss - before.ru_maxrss)
                mem_kb = delta or after.ru_maxrss
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return {
                "timeout": True,
                "timeMs": elapsed_ms,
                "memoryMb": _format_memory_mb(mem_kb),
                "runRes": None
            }

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return {
        "timeout": False,
        "timeMs": elapsed_ms,
        "memoryMb": _format_memory_mb(mem_kb),
        "runRes": run_res
    }


def _format_memory_mb(kb_value):
    if kb_value is None:
        return None
    if platform.system().lower() == "darwin":
        return round(kb_value / (1024 * 1024), 2)
    return round(kb_value / 1024, 2)


def _run_cpp_single(code, input_data):
    with tempfile.TemporaryDirectory() as tmp:
        src_path = os.path.join(tmp, "main.cpp")
        bin_path = os.path.join(tmp, "main")
        _write_text(src_path, code)

        compile_res = _compile_cpp(src_path, bin_path)
        if compile_res.returncode != 0:
            return {
                "status": "CE",
                "output": "",
                "details": compile_res.stderr.strip() or "compile_error"
            }

        run_info = _run_with_limits([bin_path], input_data, 5)
        if run_info["timeout"]:
            return {
                "status": "TL",
                "output": "",
                "timeMs": run_info["timeMs"],
                "memoryMb": run_info["memoryMb"],
                "details": "timeout"
            }

        run_res = run_info["runRes"]
        if run_res.returncode != 0:
            return {
                "status": "RE",
                "output": run_res.stdout,
                "timeMs": run_info["timeMs"],
                "memoryMb": run_info["memoryMb"],
                "details": (run_res.stderr or "").strip() or "runtime_error"
            }

        return {
            "status": "OK",
            "output": run_res.stdout,
            "timeMs": run_info["timeMs"],
            "memoryMb": run_info["memoryMb"]
        }


def _run_python_single(code, input_data):
    with tempfile.TemporaryDirectory() as tmp:
        src_path = os.path.join(tmp, "main.py")
        _write_text(src_path, code)

        compile_res = _compile_python(src_path)
        if compile_res.returncode != 0:
            return {
                "status": "CE",
                "output": "",
                "details": compile_res.stderr.strip() or "compile_error"
            }

        run_info = _run_with_limits(["python3", src_path], input_data, 5)
        if run_info["timeout"]:
            return {
                "status": "TL",
                "output": "",
                "timeMs": run_info["timeMs"],
                "memoryMb": run_info["memoryMb"],
                "details": "timeout"
            }

        run_res = run_info["runRes"]
        if run_res.returncode != 0:
            return {
                "status": "RE",
                "output": run_res.stdout,
                "timeMs": run_info["timeMs"],
                "memoryMb": run_info["memoryMb"],
                "details": (run_res.stderr or "").strip() or "runtime_error"
            }

        return {
            "status": "OK",
            "output": run_res.stdout,
            "timeMs": run_info["timeMs"],
            "memoryMb": run_info["memoryMb"]
        }


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

    if not sync_tasks_repo():
        return jsonify({
            "error": "tasks_sync_failed",
            "status": "ERROR"
        }), 500

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

    # --- изолированный запуск judge для конкретной посылки ---
    print("Запуск judge.py...")
    log_text = "(log.txt не найден)"
    task_meta = read_task_meta(task)
    task_lang = normalize_language(task_meta.get("language"))
    source_name = "sol.py" if task_lang == "python" else "sol.cpp"
    try:
        with tempfile.TemporaryDirectory(prefix="codebug_submit_") as workdir:
            source_path = os.path.join(workdir, source_name)
            with open(source_path, "w") as f:
                f.write(code)

            judge_env = {
                **os.environ,
                "TASKS_REPO_DIR": os.path.abspath(TASKS_REPO_DIR),
                "JUDGE_SOURCE": source_name,
                "JUDGE_BINARY": "sol",
                "JUDGE_LANG": task_lang,
                "JUDGE_LOG_FILE": "log.txt"
            }
            result = subprocess.run(
                ["python3", os.path.abspath(JUDGE_SCRIPT), task],
                capture_output=True,
                text=True,
                timeout=JUDGE_PROCESS_TIMEOUT,
                cwd=workdir,
                env=judge_env
            )

            log_path = os.path.join(workdir, "log.txt")
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    log_text = f.read()
            else:
                log_text = (result.stdout or "") + "\n" + (result.stderr or "")
    except subprocess.TimeoutExpired:
        if submission_ref is not None:
            submission_ref.update({"verdict": "TL"})
        return jsonify({
            "status": "TL",
            "log": "Judge timeout",
            "submissionId": submission_ref.key if submission_ref is not None else None,
            "firebaseSaved": firebase_saved,
            "firebaseError": firebase_error
        })
    except Exception as e:
        print("Judge launch error:", e)
        return jsonify({"error": "judge_launch_failed"}), 500

    print("judge.py завершён")

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


@app.route("/auth/verify-captcha", methods=["POST", "OPTIONS"])
def auth_verify_captcha():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    token = str(data.get("token", "")).strip()
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    remote_ip = (forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr)

    ok, error_code = _verify_captcha_token(token, remote_ip=remote_ip)
    if not ok:
        status = 503 if error_code == "captcha_not_configured" else 400
        return jsonify({"ok": False, "error": error_code}), status

    return jsonify({"ok": True})


@app.route("/tasks/list", methods=["GET"])
def tasks_list():
    if not sync_tasks_repo():
        return jsonify({"error": "tasks_sync_failed"}), 500
    return jsonify(list_tasks())


@app.route("/tasks/<int:task_id>/admin-bundle", methods=["GET"])
def tasks_admin_bundle(task_id):
    if not _is_admin_request():
        return jsonify({"error": "admin_required"}), 403
    if not sync_tasks_repo():
        return jsonify({"error": "tasks_sync_failed"}), 500

    problem = read_problem_config(task_id)
    if not problem:
        return abort(404)

    statement = problem.get("statement") or {}
    files = problem.get("files") or {}
    checker = problem.get("checker") or {}

    tests = []
    for item in problem.get("tests") or []:
        tests.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "visibility": item.get("visibility", "private"),
            "group": item.get("group", item.get("subtask", 1)),
            "subtask": item.get("subtask", 1),
            "points": item.get("points", 0),
            "input": _task_text(task_id, item.get("input")),
            "output": _task_text(task_id, item.get("answer"))
        })

    return jsonify({
        "problem": problem,
        "files": {
            "statementTex": _task_text(task_id, statement.get("tex")),
            "statementHtml": _task_text(task_id, statement.get("html")),
            "help": _task_text(task_id, statement.get("hint")),
            "code": _task_text(task_id, files.get("code")),
            "solution": _task_text(task_id, files.get("solution")),
            "generator": _task_text(task_id, files.get("generator")),
            "validator": _task_text(task_id, files.get("validator")),
            "checker": _task_text(task_id, checker.get("path") or files.get("checker")),
        },
        "tests": tests
    })


@app.route("/tasks/<int:task_id>/<path:filename>", methods=["GET"])
def tasks_file(task_id, filename):
    if not sync_tasks_repo():
        return jsonify({"error": "tasks_sync_failed"}), 500
    if filename == "problem.json":
        problem = read_problem_config(task_id)
        if not problem:
            return abort(404)
        return jsonify(public_problem_meta(problem))
    if filename == "meta.json":
        meta = read_task_meta(task_id)
        if not meta:
            return abort(404)
        return jsonify(meta)
    path = safe_task_file(task_id, filename)
    if not path:
        return abort(404)
    return send_file(path)


@app.route("/tasks/create", methods=["POST"])
def tasks_create():
    if not _is_admin_request():
        return jsonify({"error": "admin_required"}), 403
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
    meta.pop("author", None)
    lang = normalize_language(meta.get("language"))
    if lang not in SUPPORTED_LANGUAGES:
        return jsonify({"error": "language_not_supported"}), 400
    meta["language"] = lang
    problem_v2 = _build_problem_v2(task_id, meta, files, tests)

    task_path = task_dir(task_id)
    if os.path.isdir(task_path):
        shutil.rmtree(task_path)
    os.makedirs(task_path, exist_ok=True)
    tests_path = os.path.join(task_path, "tests")

    # v2 Polygon-compatible layout
    _write_text(os.path.join(task_path, "problem.json"), json.dumps(problem_v2, ensure_ascii=False, indent=2))
    statement_text = files.get("statement", "")
    statement_tex = files.get("statementTex") or statement_text
    statement_html = files.get("statementHtml") or _statement_to_html(statement_text)
    _write_text(os.path.join(task_path, "statement", "russian.tex"), statement_tex)
    _write_text(os.path.join(task_path, "statement", "russian.html"), statement_html)
    os.makedirs(os.path.join(task_path, "statement", "assets"), exist_ok=True)
    if files.get("help"):
        _write_text(os.path.join(task_path, "statement", "hint.md"), files["help"])
    if files.get("code"):
        _write_text(os.path.join(task_path, problem_v2["files"]["code"]), files["code"])
    if files.get("solution"):
        _write_text(os.path.join(task_path, problem_v2["files"]["solution"]), files["solution"])
    if files.get("generator"):
        _write_text(os.path.join(task_path, problem_v2["files"]["generator"]), files["generator"])
    if files.get("checker"):
        _write_text(os.path.join(task_path, "checker", "checker.cpp"), files["checker"])
    if files.get("validator"):
        _write_text(os.path.join(task_path, "validator", "validator.cpp"), files["validator"])
    for idx, t in enumerate(tests, start=1):
        name = _pad_test_name(idx)
        _write_text(os.path.join(tests_path, name), t.get("input", ""))
        _write_text(os.path.join(tests_path, f"{name}.a"), t.get("output", ""))

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
    if not _is_admin_request():
        return jsonify({"error": "admin_required"}), 403
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
    if not _is_admin_request():
        return jsonify({"error": "admin_required"}), 403

    data = request.get_json(silent=True) or {}
    generator_code = data.get("generator", "")
    solution_code = data.get("solution", "")
    count = data.get("count", 0)
    lang = normalize_language(data.get("language"))

    if not isinstance(count, int) or count <= 0:
        return jsonify({"error": "count_required"}), 400
    if count > MAX_GENERATED_TESTS:
        return jsonify({"error": "count_too_large"}), 400
    if not generator_code.strip():
        return jsonify({"error": "generator_required"}), 400
    if not solution_code.strip():
        return jsonify({"error": "solution_required"}), 400

    with tempfile.TemporaryDirectory() as tmp:
        if lang == "python":
            gen_src = os.path.join(tmp, "generator.py")
            sol_src = os.path.join(tmp, "solution.py")
            _write_text(gen_src, generator_code)
            _write_text(sol_src, solution_code)

            gen_compile = _compile_python(gen_src)
            if gen_compile.returncode != 0:
                return jsonify({
                    "error": "generator_compile_failed",
                    "details": gen_compile.stderr
                }), 400

            sol_compile = _compile_python(sol_src)
            if sol_compile.returncode != 0:
                return jsonify({
                    "error": "solution_compile_failed",
                    "details": sol_compile.stderr
                }), 400
        else:
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
            try:
                if lang == "python":
                    gen_run = subprocess.run(
                        ["python3", gen_src, str(i)],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                else:
                    gen_run = subprocess.run(
                        [gen_bin, str(i)],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
            except subprocess.TimeoutExpired:
                return jsonify({
                    "error": "generator_timeout",
                    "index": i
                }), 400

            if gen_run.returncode != 0:
                return jsonify({
                    "error": "generator_runtime_failed",
                    "details": gen_run.stderr,
                    "index": i
                }), 400

            inp = gen_run.stdout
            try:
                if lang == "python":
                    sol_run = subprocess.run(
                        ["python3", sol_src],
                        input=inp,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                else:
                    sol_run = subprocess.run(
                        [sol_bin],
                        input=inp,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
            except subprocess.TimeoutExpired:
                return jsonify({
                    "error": "solution_timeout",
                    "index": i
                }), 400

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


@app.route("/run-single", methods=["POST"])
def run_single():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    input_data = data.get("input", "")
    lang = normalize_language(data.get("language"))

    if not code or not code.strip():
        return jsonify({"error": "code_required"}), 400

    if lang == "python":
        result = _run_python_single(code, input_data)
    else:
        result = _run_cpp_single(code, input_data)
    return jsonify(result)


@app.route("/admin/purge-users", methods=["POST"])
def admin_purge_users():
    if not _is_admin_request():
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    if data.get("confirm") != "DELETE_ALL_USERS":
        return jsonify({"error": "confirm_required"}), 400

    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return jsonify({"error": "firebase_not_ready"}), 500

    deleted_auth = 0
    next_token = None
    try:
        while True:
            page = admin_auth.list_users(page_token=next_token, max_results=1000)
            users_batch = list(page.users)
            if not users_batch:
                break
            for u in users_batch:
                admin_auth.delete_user(u.uid)
                deleted_auth += 1
            next_token = page.next_page_token
            if not next_token:
                break
    except Exception as e:
        return jsonify({
            "error": "auth_purge_failed",
            "details": str(e),
            "deletedAuth": deleted_auth
        }), 500

    try:
        db.reference("users").set(None)
        db.reference("userAuthMap").set(None)
        db.reference("emailToLogin").set(None)
        db.reference("admins").set(None)
    except Exception as e:
        return jsonify({
            "error": "db_purge_failed",
            "details": str(e),
            "deletedAuth": deleted_auth
        }), 500

    return jsonify({
        "status": "ok",
        "deletedAuth": deleted_auth,
        "deletedDbNodes": ["users", "userAuthMap", "emailToLogin", "admins"]
    })


@app.route("/public-config", methods=["GET"])
def public_config():
    firebase_public = {
        "apiKey": PUBLIC_FIREBASE_WEB_API_KEY,
        "authDomain": PUBLIC_FIREBASE_WEB_AUTH_DOMAIN,
        "databaseURL": PUBLIC_FIREBASE_WEB_DATABASE_URL,
        "projectId": PUBLIC_FIREBASE_WEB_PROJECT_ID,
        "storageBucket": PUBLIC_FIREBASE_WEB_STORAGE_BUCKET,
        "messagingSenderId": PUBLIC_FIREBASE_WEB_MESSAGING_SENDER_ID,
        "appId": PUBLIC_FIREBASE_WEB_APP_ID
    }
    return jsonify({
        "firebase": firebase_public,
        "recaptchaSiteKey": RECAPTCHA_SITE_KEY
    })


@app.route("/ping", methods=["GET", "HEAD"])
def ping():
    return jsonify({"status": "ok", "ts": int(time.time())})


@app.route("/", methods=["GET", "HEAD"])
def root():
    return jsonify({"status": "ok"})
    

if __name__ == "__main__":
    print("=== LOCAL JUDGE SERVER ===")
    port = int(os.getenv("PORT", "7777"))
    print(f"Запуск на http://127.0.0.1:{port}")
    sync_tasks_repo(force=True)
    app.run(host="0.0.0.0", port=port)
