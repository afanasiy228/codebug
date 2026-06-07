import os
import json
import subprocess
import tempfile
import re
import shutil
import zipfile
import threading
from collections import deque
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import time
import urllib.parse
import urllib.request
import html
import traceback

try:
    import redis
except Exception:
    redis = None

import firebase_admin
from firebase_admin import credentials, db
from firebase_admin import auth as admin_auth
from polygon_importer import PolygonImportError, parse_polygon_package
from sandbox import SandboxError, run_in_sandbox
from statement_compiler import compile_latex_statement

app = Flask(__name__)

def _cors_origins():
    raw = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "https://codebug.onrender.com,https://codebug.online,https://www.codebug.online,http://localhost:7777,http://127.0.0.1:7777"
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

CORS(app, resources={r"/*": {"origins": _cors_origins()}}, supports_credentials=False)

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
AI_COMPLETION_API_KEY = (
    os.getenv("MISTRAL_API_KEY")
    or os.getenv("CODESTRAL_API_KEY")
    or os.getenv("AI_COMPLETION_API_KEY")
    or ""
)
AI_COMPLETION_API_URL = os.getenv("AI_COMPLETION_API_URL", "https://api.mistral.ai/v1/fim/completions")
AI_COMPLETION_MODEL = os.getenv("AI_COMPLETION_MODEL", "codestral-latest")
AI_COMPLETION_TIMEOUT = int(os.getenv("AI_COMPLETION_TIMEOUT", "12"))
PUBLIC_FIREBASE_WEB_API_KEY = os.getenv("PUBLIC_FIREBASE_WEB_API_KEY", "")
PUBLIC_FIREBASE_WEB_AUTH_DOMAIN = os.getenv("PUBLIC_FIREBASE_WEB_AUTH_DOMAIN", "")
PUBLIC_FIREBASE_WEB_DATABASE_URL = os.getenv("PUBLIC_FIREBASE_WEB_DATABASE_URL", "")
PUBLIC_FIREBASE_WEB_PROJECT_ID = os.getenv("PUBLIC_FIREBASE_WEB_PROJECT_ID", "")
PUBLIC_FIREBASE_WEB_STORAGE_BUCKET = os.getenv("PUBLIC_FIREBASE_WEB_STORAGE_BUCKET", "")
PUBLIC_FIREBASE_WEB_MESSAGING_SENDER_ID = os.getenv("PUBLIC_FIREBASE_WEB_MESSAGING_SENDER_ID", "")
PUBLIC_FIREBASE_WEB_APP_ID = os.getenv("PUBLIC_FIREBASE_WEB_APP_ID", "")
PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "https://codebug.online").rstrip("/")
PUBLIC_API_BASE = os.getenv("PUBLIC_API_BASE", "https://codebug.onrender.com").rstrip("/")
PLATEGA_API_BASE = os.getenv("PLATEGA_API_BASE", "https://app.platega.io").rstrip("/")
PLATEGA_CREATE_PATH = os.getenv("PLATEGA_CREATE_PATH", "/v2/transaction/process")
PLATEGA_MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID", "")
PLATEGA_SECRET = os.getenv("PLATEGA_SECRET", "")
PLATEGA_PAYMENT_METHOD = os.getenv("PLATEGA_PAYMENT_METHOD", "").strip()
PLATEGA_CURRENCY = os.getenv("PLATEGA_CURRENCY", "RUB")
PLATEGA_CALLBACK_URL = os.getenv("PLATEGA_CALLBACK_URL", f"{PUBLIC_API_BASE}/payments/platega/callback")
PLATEGA_SUCCESS_URL = os.getenv("PLATEGA_SUCCESS_URL", f"{PUBLIC_SITE_URL}/donate.html?payment=success")
PLATEGA_FAILED_URL = os.getenv("PLATEGA_FAILED_URL", f"{PUBLIC_SITE_URL}/donate.html?payment=failed")
SUBSCRIPTION_PRICE_PRO_RUB = float(os.getenv("SUBSCRIPTION_PRICE_PRO_RUB", "1"))
SUBSCRIPTION_PRICE_PRO_PLUS_RUB = float(os.getenv("SUBSCRIPTION_PRICE_PRO_PLUS_RUB", "2"))
PLATEGA_AMOUNT_MULTIPLIER = float(os.getenv("PLATEGA_AMOUNT_MULTIPLIER", "1.14"))
RUNTIME_WORK_DIR = os.getenv("CODEBUG_WORK_DIR", os.path.abspath(".codebug_work"))
SEED_ADMIN_LOGINS = [
    login.strip() for login in os.getenv("SEED_ADMIN_LOGINS", "afanasy").split(",")
    if login.strip()
]


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
    if SEED_ADMIN_LOGINS:
        try:
            for login in SEED_ADMIN_LOGINS:
                db.reference(f"admins/{login}").set(True)
            print("Seed admins applied:", ", ".join(SEED_ADMIN_LOGINS))
        except Exception as e:
            print("Seed admins apply failed:", e)
    print("Firebase Admin init OK")
    return True


FIREBASE_READY = init_firebase()
SUBMIT_QUEUE = deque()
SUBMIT_QUEUE_PRO = deque()
SUBMIT_QUEUE_LOCK = threading.Lock()
SUBMIT_QUEUE_COND = threading.Condition(SUBMIT_QUEUE_LOCK)
SUBMIT_WORKER_STARTED = False
TASKS_SYNC_WORKER_STARTED = False
REQUEST_RATE_STATE = {}
RATE_LOCK = threading.Lock()
RATE_LIMIT_BACKEND = (os.getenv("RATE_LIMIT_BACKEND", "memory") or "memory").strip().lower()
REDIS_URL = os.getenv("REDIS_URL", "").strip()
RATE_LIMIT_PREFIX = (os.getenv("RATE_LIMIT_PREFIX", "codebug:rl") or "codebug:rl").strip()
REDIS_RATE_CLIENT = None


def _ensure_firebase_ready():
    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    return FIREBASE_READY

MAX_CODE_SIZE_BYTES = int(os.getenv("MAX_CODE_SIZE_BYTES", str(512 * 1024)))
MAX_INPUT_SIZE_BYTES = int(os.getenv("MAX_INPUT_SIZE_BYTES", str(512 * 1024)))
MAX_EDITOR_PREFIX_BYTES = int(os.getenv("MAX_EDITOR_PREFIX_BYTES", str(512 * 1024)))
MAX_EDITOR_SUFFIX_BYTES = int(os.getenv("MAX_EDITOR_SUFFIX_BYTES", str(512 * 1024)))
MAX_TASK_TITLE_LEN = int(os.getenv("MAX_TASK_TITLE_LEN", "200"))
MAX_TAGS_COUNT = int(os.getenv("MAX_TAGS_COUNT", "16"))
MAX_TAG_LEN = int(os.getenv("MAX_TAG_LEN", "32"))
MAX_STATEMENT_LEN = int(os.getenv("MAX_STATEMENT_LEN", str(2 * 1024 * 1024)))
MAX_SUBMIT_QUEUE_SIZE = int(os.getenv("MAX_SUBMIT_QUEUE_SIZE", "300"))
SUBMIT_GLOBAL_RATE_LIMIT = int(os.getenv("SUBMIT_GLOBAL_RATE_LIMIT", "120"))
SUBMIT_GLOBAL_RATE_WINDOW = int(os.getenv("SUBMIT_GLOBAL_RATE_WINDOW", "60"))
RUN_SINGLE_TIMEOUT_FREE = float(os.getenv("RUN_SINGLE_TIMEOUT_FREE", "5"))
RUN_SINGLE_TIMEOUT_PRO = float(os.getenv("RUN_SINGLE_TIMEOUT_PRO", "10"))
RUN_SINGLE_INPUT_LIMIT_FREE = int(os.getenv("RUN_SINGLE_INPUT_LIMIT_FREE", str(512 * 1024)))
RUN_SINGLE_INPUT_LIMIT_PRO = int(os.getenv("RUN_SINGLE_INPUT_LIMIT_PRO", str(1024 * 1024)))
RUN_SINGLE_CODE_LIMIT_FREE = int(os.getenv("RUN_SINGLE_CODE_LIMIT_FREE", str(512 * 1024)))
RUN_SINGLE_CODE_LIMIT_PRO = int(os.getenv("RUN_SINGLE_CODE_LIMIT_PRO", str(1024 * 1024)))
NICKNAME_CHANGE_COOLDOWN_SECONDS = int(os.getenv("NICKNAME_CHANGE_COOLDOWN_SECONDS", str(14 * 24 * 60 * 60)))
SUBMIT_RATE_FREE = int(os.getenv("SUBMIT_RATE_FREE", "20"))
SUBMIT_RATE_PRO = int(os.getenv("SUBMIT_RATE_PRO", "35"))
EDITOR_RATE_FREE = int(os.getenv("EDITOR_RATE_FREE", "40"))
EDITOR_RATE_PRO = int(os.getenv("EDITOR_RATE_PRO", "55"))
PRO_NICK_COLORS = {
    "#60a5fa", "#38bdf8", "#a78bfa", "#22d3ee", "#34d399",
    "#f472b6", "#f59e0b", "#ef4444", "#14b8a6", "#8b5cf6",
}
PRO_PLUS_NICK_THEMES = {"grad_ocean", "grad_sunset", "grad_candy", "grad_aurora", "nutella", "rainbow", "fire_ice", "matrix", "blood_ink"}
PROFILE_COVER_PRESETS = {f"cover_{i}" for i in range(1, 11)}
DEFAULT_PROFILE_COVER_ID = "cover_1"
MAX_PROFILE_COVER_IMAGE_BYTES = int(os.getenv("MAX_PROFILE_COVER_IMAGE_BYTES", str(2 * 1024 * 1024)))
SUBSCRIPTION_PERIOD_DAYS = int(os.getenv("SUBSCRIPTION_PERIOD_DAYS", "30"))
SUBSCRIPTION_GRACE_DAYS = int(os.getenv("SUBSCRIPTION_GRACE_DAYS", "10"))


def _api_error(error, status=400, code=None):
    payload = {"error": str(error)}
    payload["code"] = str(code or error)
    return jsonify(payload), status


def _server_error(error, code, exc=None, status=500):
    print(f"[server-error] {error} code={code}")
    if exc is not None:
        print(exc)
        print(traceback.format_exc())
    return _api_error(error, status=status, code=code)


def _request_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    return (forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr) or "unknown"


def _allowed_origins():
    return set(_cors_origins())


def _origin_in_allowed(origin):
    return bool(origin and origin in _allowed_origins())


def _soft_check_request_origin(user_login=None):
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    path = request.path or ""
    if path in {"/ping", "/"}:
        return
    origin = (request.headers.get("Origin") or "").strip()
    referer = (request.headers.get("Referer") or "").strip()
    origin_ok = _origin_in_allowed(origin)
    referer_ok = any(referer.startswith(allowed) for allowed in _allowed_origins()) if referer else False
    if not origin_ok and not referer_ok:
        print(
            f"[security][origin-soft-fail] method={request.method} path={path} ip={_request_ip()} "
            f"user={user_login or '-'} origin={origin or '-'} referer={referer or '-'}"
        )


@app.before_request
def _before_write_request_soft_checks():
    _soft_check_request_origin()


def _is_admin_request():
    if ADMIN_API_KEY:
        header_key = request.headers.get("X-Admin-Key", "")
        if header_key == ADMIN_API_KEY:
            return True

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return False
    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
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


def _require_task_manager():
    if _is_admin_request():
        return "admin", None
    login, auth_error = _require_user_login()
    if auth_error:
        return None, auth_error
    if not _is_dev_active(login):
        return None, _api_error("forbidden", 403, "FORBIDDEN")
    return login, None

def _resolve_login_from_token(token):
    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return None
    try:
        decoded = admin_auth.verify_id_token(token)
        uid = decoded.get("uid")
        if not uid:
            return None
        login = db.reference(f"userAuthMap/{uid}").get()
        if not login:
            return None
        return str(login).strip() or None
    except Exception:
        return None


def _require_user_login():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, _api_error("auth_required", status=401, code="AUTH_REQUIRED")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return None, _api_error("auth_required", status=401, code="AUTH_REQUIRED")
    login = _resolve_login_from_token(token)
    if not login:
        return None, _api_error("invalid_token", status=401, code="INVALID_TOKEN")
    return login, None


def _now_ms():
    return int(time.time() * 1000)


def _to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _subscription_features_for_tier(tier):
    tier = str(tier or "").strip().lower()
    return {
        "earlyAccess": tier in {"pro_plus", "creator_dev"}
    }


def _subscription_price_for_tier(tier):
    tier = str(tier or "").strip().lower()
    if tier == "pro":
        return SUBSCRIPTION_PRICE_PRO_RUB
    if tier == "pro_plus":
        return SUBSCRIPTION_PRICE_PRO_PLUS_RUB
    return None


def _platega_amount_for_price(price):
    try:
        price = float(price)
        multiplier = float(PLATEGA_AMOUNT_MULTIPLIER or 1)
        if multiplier <= 0:
            multiplier = 1
        return round(price / multiplier, 2)
    except Exception:
        return price


def _normalize_subscription(login, raw, write_back=False):
    if not isinstance(raw, dict):
        raw = {}
    now = _now_ms()
    status = str(raw.get("status") or "").strip().lower()
    tier = str(raw.get("tier") or "").strip().lower()
    expires_at = _to_int(raw.get("expiresAt"))
    grace_until = _to_int(raw.get("graceUntil") or raw.get("paymentGraceUntil"))
    changed = {}

    if status == "active" and expires_at and expires_at < now:
        if grace_until and grace_until >= now:
            status = "grace"
            changed["status"] = "grace"
        else:
            status = "disabled"
            changed.update({"status": "disabled", "disabledAt": now})
    elif status == "grace" and grace_until and grace_until < now:
        status = "disabled"
        changed.update({"status": "disabled", "disabledAt": now})

    days_left = None
    if status == "active" and expires_at:
        days_left = max(0, int((expires_at - now + 86_399_999) // 86_400_000))
    grace_days_left = None
    if status == "grace" and grace_until:
        grace_days_left = max(0, int((grace_until - now + 86_399_999) // 86_400_000))

    if changed and write_back and login and FIREBASE_READY:
        try:
            changed["updatedAt"] = now
            db.reference(f"users/{login}/subscription").update(changed)
        except Exception as e:
            print("subscription normalize write failed:", e)

    visuals = raw.get("visuals") if isinstance(raw.get("visuals"), dict) else {}
    features = raw.get("features") if isinstance(raw.get("features"), dict) else _subscription_features_for_tier(tier)
    return {
        "tier": tier,
        "status": status,
        "updatedAt": raw.get("updatedAt"),
        "activatedAt": raw.get("activatedAt"),
        "expiresAt": expires_at or raw.get("expiresAt"),
        "graceUntil": grace_until or raw.get("graceUntil"),
        "daysLeft": days_left,
        "graceDaysLeft": grace_days_left,
        "paymentWarning": raw.get("paymentWarning"),
        "failedPaymentAt": raw.get("failedPaymentAt"),
        "lastPaymentAt": raw.get("lastPaymentAt"),
        "nicknameChangedAt": raw.get("nicknameChangedAt"),
        "visuals": visuals,
        "features": features
    }


def _get_user_subscription(login):
    if not FIREBASE_READY or not login:
        return {}
    try:
        raw = db.reference(f"users/{login}/subscription").get() or {}
        if not isinstance(raw, dict):
            return {}
        return _normalize_subscription(login, raw, write_back=True)
    except Exception as e:
        print("subscription read failed:", e)
        return {}


def _is_pro_active(login):
    return _is_active_tier(login, "pro")


def _is_active_tier(login, tier):
    sub = _get_user_subscription(login)
    if sub.get("status") not in {"active", "grace"}:
        return False
    user_tier = sub.get("tier")
    rank = {"pro": 1, "pro_plus": 2, "creator_dev": 2}
    return rank.get(user_tier, 0) >= rank.get(str(tier or "").strip().lower(), 10)


def _is_pro_plus_active(login):
    return _is_active_tier(login, "pro_plus")


def _is_dev_active(login):
    return _is_active_tier(login, "pro_plus")


def _subscription_tier_label(login):
    sub = _get_user_subscription(login)
    tier = sub.get("tier", "")
    if sub.get("status") not in {"active", "grace"}:
        return "free"
    if tier == "creator_dev":
        return "pro_plus"
    if tier == "pro_plus":
        return "pro_plus"
    if tier == "pro":
        return "pro"
    return "free"


def _submission_rate_limit_for_tier(tier):
    if tier in {"pro", "pro_plus"}:
        return SUBMIT_RATE_PRO
    return SUBMIT_RATE_FREE


def _editor_rate_limit_for_tier(tier):
    if tier in {"pro", "pro_plus"}:
        return EDITOR_RATE_PRO
    return EDITOR_RATE_FREE


def _append_activity(login, kind, payload=None):
    if not FIREBASE_READY:
        return
    login = str(login or "").strip()
    if not login:
        return
    try:
        item = {
            "type": str(kind or "event"),
            "ts": int(time.time() * 1000),
        }
        if isinstance(payload, dict):
            item.update(payload)
        feed_ref = db.reference(f"users/{login}/activityFeed")
        feed_ref.push(item)
        raw = feed_ref.get() or {}
        if isinstance(raw, dict) and len(raw) > 100:
            keys = sorted(raw.keys(), key=lambda k: int((raw.get(k) or {}).get("ts") or 0))
            for key in keys[:-100]:
                feed_ref.child(key).delete()
    except Exception as e:
        print("activity append failed:", e)


def _rate_limit_key(route_key, user_login):
    ip = _request_ip()
    who = user_login or ip
    return f"{route_key}:{who}"


def _redis_rate_client():
    global REDIS_RATE_CLIENT
    if REDIS_RATE_CLIENT is not None:
        return REDIS_RATE_CLIENT
    if redis is None or not REDIS_URL:
        return None
    try:
        REDIS_RATE_CLIENT = redis.Redis.from_url(REDIS_URL, socket_timeout=1, socket_connect_timeout=1)
        REDIS_RATE_CLIENT.ping()
        return REDIS_RATE_CLIENT
    except Exception as e:
        print("Redis rate limit unavailable:", e)
        REDIS_RATE_CLIENT = None
        return None


def _rate_limit_memory(route_key, user_login, limit, per_seconds):
    now = time.time()
    key = _rate_limit_key(route_key, user_login)
    with RATE_LOCK:
        bucket = REQUEST_RATE_STATE.get(key, [])
        bucket = [ts for ts in bucket if now - ts < per_seconds]
        if len(bucket) >= limit:
            REQUEST_RATE_STATE[key] = bucket
            return False
        bucket.append(now)
        REQUEST_RATE_STATE[key] = bucket
    return True


def _rate_limit_redis(route_key, user_login, limit, per_seconds):
    client = _redis_rate_client()
    if client is None:
        return None
    key = f"{RATE_LIMIT_PREFIX}:{_rate_limit_key(route_key, user_login)}:{int(time.time() // per_seconds)}"
    try:
        count = client.incr(key)
        if count == 1:
            client.expire(key, per_seconds + 1)
        return count <= int(limit)
    except Exception as e:
        print("Redis rate limit failed, falling back to memory:", e)
        return None


def _rate_limit(route_key, user_login, limit, per_seconds):
    backend = RATE_LIMIT_BACKEND
    if backend == "redis":
        redis_allowed = _rate_limit_redis(route_key, user_login, limit, per_seconds)
        if redis_allowed is not None:
            return redis_allowed
    return _rate_limit_memory(route_key, user_login, limit, per_seconds)


def _rate_limit_global(route_key, limit, per_seconds):
    return _rate_limit(route_key, "__global__", limit, per_seconds)


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


def _strip_code_fences(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[A-Za-z0-9_+-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _trim_ai_completion(completion):
    completion = _strip_code_fences(completion)
    completion = completion.replace("\r\n", "\n").replace("\r", "\n")
    lines = completion.split("\n")
    completion = ""
    for line in lines:
        if line.strip():
            completion = line
            break
    if len(completion) > 240:
        completion = completion[:240]
    return completion


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _validate_language(value):
    lang = normalize_language(value)
    if lang not in SUPPORTED_LANGUAGES:
        return None
    return lang


def _validate_submit_payload(data):
    if not isinstance(data, dict):
        return None, _api_error("invalid_payload", 400, "INVALID_PAYLOAD")
    task_raw = data.get("task")
    code = data.get("code")
    user_raw = data.get("user")
    lang = _validate_language(data.get("language"))
    if not _is_nonempty_string(code):
        return None, _api_error("code_required", 400, "CODE_REQUIRED")
    if not _is_nonempty_string(user_raw):
        return None, _api_error("user_required", 400, "USER_REQUIRED")
    if len(code.encode("utf-8", errors="replace")) > MAX_CODE_SIZE_BYTES:
        return None, _api_error("code_too_large", 400, "CODE_TOO_LARGE")
    try:
        task_id = int(str(task_raw).strip())
    except (TypeError, ValueError):
        return None, _api_error("invalid_task", 400, "INVALID_TASK")
    user_login = str(user_raw).strip()
    if lang is None:
        lang = "cpp"
    return {
        "task_id": task_id,
        "code": code,
        "user_login": user_login,
        "language": lang,
        "contest_id": data.get("contestId")
    }, None


def _validate_run_payload(data, *, tier="free"):
    if not isinstance(data, dict):
        return None, _api_error("invalid_payload", 400, "INVALID_PAYLOAD")
    code = data.get("code", "")
    input_data = data.get("input", "")
    if not _is_nonempty_string(code):
        return None, _api_error("code_required", 400, "CODE_REQUIRED")
    if not isinstance(input_data, str):
        return None, _api_error("invalid_input", 400, "INVALID_INPUT")
    if tier in {"pro", "pro_plus"}:
        code_limit = RUN_SINGLE_CODE_LIMIT_PRO
        input_limit = RUN_SINGLE_INPUT_LIMIT_PRO
    else:
        code_limit = RUN_SINGLE_CODE_LIMIT_FREE
        input_limit = RUN_SINGLE_INPUT_LIMIT_FREE
    if len(code.encode("utf-8", errors="replace")) > code_limit:
        return None, _api_error("code_too_large", 400, "CODE_TOO_LARGE")
    if len(input_data.encode("utf-8", errors="replace")) > input_limit:
        return None, _api_error("input_too_large", 400, "INPUT_TOO_LARGE")
    lang = _validate_language(data.get("language"))
    if lang is None:
        lang = "cpp"
    return {"code": code, "input": input_data, "language": lang}, None


def _request_ai_code_completion(language, prefix, suffix):
    if not AI_COMPLETION_API_KEY or not AI_COMPLETION_MODEL:
        return None, "ai_completion_not_configured"

    lang = normalize_language(language)
    language_hint = "# Python 3\n" if lang == "python" else "// C++17\n"
    prefix_lines = (prefix or "").splitlines(keepends=True)
    prefix = "".join(prefix_lines[-8:])
    suffix_lines = (suffix or "").splitlines(keepends=True)
    suffix = "".join(suffix_lines[:4])
    prompt = language_hint + prefix
    if lang == "cpp":
        current_line = prefix.splitlines()[-1] if prefix.splitlines() else ""
        previous_lines = prefix.splitlines()[:-1]
        previous_line = previous_lines[-1].rstrip() if previous_lines else ""
        if not current_line.strip() and previous_line.endswith("{"):
            prompt += "// Complete one likely next C++ statement inside this block.\n"
    payload = {
        "model": AI_COMPLETION_MODEL,
        "temperature": 0.15,
        "max_tokens": 64,
        "prompt": prompt,
        "suffix": suffix,
        "stop": ["\n", "```"]
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        AI_COMPLETION_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_COMPLETION_API_KEY}"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=AI_COMPLETION_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
    except Exception as e:
        print("AI completion request failed:", e)
        return None, "ai_completion_failed"

    completion = ""
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] or {}
        message = choice.get("message") or {}
        completion = (
            choice.get("text")
            or choice.get("content")
            or message.get("content")
            or ""
        )
    completion = _trim_ai_completion(completion)
    if not completion:
        return None, "empty_completion"
    return completion, None


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
        # Fallback to already cloned local repository if it exists.
        if os.path.isdir(TASKS_REPO_DIR):
            for name in os.listdir(TASKS_REPO_DIR):
                if name.isdigit():
                    return True
        return False


def _parse_judge_log(log_text):
    final = "CE"
    score_value = None
    peak_time_ms = None
    peak_memory_mb = None
    first_fail_label = None
    passed_groups = []
    for line in log_text.splitlines():
        if line.startswith("Score:"):
            try:
                score_value = int(line.split(":", 1)[1].strip())
            except (TypeError, ValueError):
                score_value = None
        if line.startswith("Peak time:"):
            try:
                peak_time_ms = int(line.split(":", 1)[1].strip().split()[0])
            except (TypeError, ValueError, IndexError):
                peak_time_ms = None
        if line.startswith("Peak memory:"):
            try:
                peak_memory_mb = float(line.split(":", 1)[1].strip().split()[0])
            except (TypeError, ValueError, IndexError):
                peak_memory_mb = None
        if line.startswith("First failing test:"):
            first_fail_label = line.split(":", 1)[1].strip() or None
        if line.startswith("Group ") and " verdict:" in line:
            try:
                left, right = line.split(" verdict:", 1)
                gid = int(left.replace("Group", "").strip())
                verdict_value = right.strip().upper()
                if verdict_value == "OK":
                    passed_groups.append(gid)
            except Exception:
                pass
        if line.startswith("Final verdict:"):
            final = line.split(":")[1].strip()
            break
    return {
        "final": final,
        "score": score_value,
        "timeMs": peak_time_ms,
        "memoryMb": peak_memory_mb,
        "firstFail": first_fail_label,
        "passedGroups": sorted(set(passed_groups)),
    }


def _run_submission_job(job):
    task = str(job["task"])
    code = str(job["code"])
    login = str(job.get("login") or "")
    submission_id = job.get("submission_id")
    task_meta = read_task_meta(task)
    task_lang = normalize_language(task_meta.get("language"))
    source_name = "sol.py" if task_lang == "python" else "sol.cpp"

    if submission_id and FIREBASE_READY:
        try:
            db.reference(f"submissions/global/{submission_id}").update({"verdict": "TESTING"})
        except Exception as e:
            print("Queue update TESTING failed:", e)

    log_text = "(log.txt не найден)"
    result_obj = {
        "status": "SE",
        "statusLabel": "SE",
        "rawVerdict": "SE",
        "score": None,
        "timeMs": None,
        "memoryMb": None,
        "firstFail": None,
        "passedGroups": [],
        "log": log_text,
    }
    try:
        with _runtime_tempdir("codebug_submit_") as workdir:
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
        log_text = "Judge timeout"
        result_obj.update({
            "status": "TL",
            "statusLabel": "TL",
            "rawVerdict": "TL",
            "log": log_text
        })
    except Exception as e:
        print("Judge launch error in queue worker:", e)
        log_text = "judge_launch_failed"
        result_obj.update({
            "status": "SE",
            "statusLabel": "SE",
            "rawVerdict": "SE",
            "log": log_text
        })
    else:
        parsed = _parse_judge_log(log_text)
        final = str(parsed.get("final") or "").strip().upper()
        if not final:
            # Ensure we never leave a submission without terminal verdict.
            final = "SE"
        public_status = final
        status_label = final
        problem_cfg = read_problem_config(task)
        scoring_mode = str((problem_cfg or {}).get("scoringMode") or "ioi").strip().lower()
        has_groups = bool((problem_cfg or {}).get("groups")) and scoring_mode != "icpc"
        terminal_errors = {"CE", "TL", "RE", "ML", "SE", "NO_TESTS"}
        if has_groups and final not in terminal_errors and parsed["score"] is not None:
            try:
                score_value = float(parsed["score"])
            except Exception:
                score_value = None
            if score_value is not None and score_value >= 100:
                public_status = "OK"
                status_label = "OK"
            elif score_value is not None and score_value > 0:
                public_status = "PS"
                status_label = "PS"
            else:
                public_status = "WA"
                status_label = "WA"
        if status_label != "PS" and parsed["firstFail"] and final in {"WA", "TL", "ML", "RE"}:
            status_label = parsed["firstFail"]
        result_obj.update({
            "status": public_status,
            "statusLabel": status_label,
            "rawVerdict": final,
            "score": parsed["score"],
            "timeMs": parsed["timeMs"],
            "memoryMb": parsed["memoryMb"],
            "firstFail": parsed["firstFail"],
            "passedGroups": parsed["passedGroups"],
            "log": log_text,
        })
        print(
            "[XP TRACE][SERVER] judge parsed:",
            {
                "login": login,
                "task": task,
                "submissionId": submission_id,
                "final": final,
                "status": public_status,
                "statusLabel": status_label,
                "score": parsed.get("score"),
                "firstFail": parsed.get("firstFail"),
                "passedGroups": parsed.get("passedGroups"),
            },
        )

    if submission_id and FIREBASE_READY:
        updated = False
        for attempt in range(3):
            try:
                db.reference(f"submissions/global/{submission_id}").update({
                    "verdict": result_obj["status"],
                    "statusLabel": result_obj["statusLabel"],
                    "timeMs": result_obj["timeMs"],
                    "memoryMb": result_obj["memoryMb"],
                    "score": result_obj["score"],
                    "passedGroups": result_obj["passedGroups"],
                })
                updated = True
                print(
                    "[XP TRACE][SERVER] submission final status written:",
                    {
                        "submissionId": submission_id,
                        "login": login,
                        "task": task,
                        "status": result_obj.get("status"),
                        "statusLabel": result_obj.get("statusLabel"),
                        "score": result_obj.get("score"),
                    },
                )
                break
            except Exception as e:
                print(f"Queue final firebase update failed (attempt {attempt + 1}/3):", e)
                time.sleep(0.2)
        if not updated:
            print(f"Queue final firebase update permanently failed for submission={submission_id}")

    solved_like = _is_solved_submission({
        "verdict": result_obj.get("status"),
        "statusLabel": result_obj.get("statusLabel"),
        "rawVerdict": result_obj.get("rawVerdict"),
        "score": result_obj.get("score"),
    })
    print(
        "[XP TRACE][SERVER] solved check:",
        {
            "login": login,
            "task": task,
            "submissionId": submission_id,
            "status": result_obj.get("status"),
            "statusLabel": result_obj.get("statusLabel"),
            "rawVerdict": result_obj.get("rawVerdict"),
            "score": result_obj.get("score"),
            "isSolved": solved_like,
        },
    )
    _append_activity(login, "submission", {
        "task": task,
        "verdict": result_obj.get("status"),
        "score": result_obj.get("score"),
        "contestId": job.get("contestId"),
    })
    if solved_like:
        print(f"[XP TRACE][SERVER] calling _mark_task_solved_for_user(login={login}, task={task})")
        mark_trace = _mark_task_solved_for_user(login, task) or {}
        print("[XP TRACE][SERVER] mark trace:", mark_trace)
        if submission_id and FIREBASE_READY:
            try:
                db.reference(f"submissions/global/{submission_id}").update({
                    "xpMarked": bool(mark_trace.get("ok")),
                    "xpAlreadySolved": mark_trace.get("alreadySolved"),
                    "xpBeforeCnt": mark_trace.get("beforeCnt"),
                    "xpAfterCnt": mark_trace.get("afterCnt"),
                    "xpBeforeExp": mark_trace.get("beforeExp"),
                    "xpAfterExp": mark_trace.get("afterExp"),
                    "xpHasTaskAfter": mark_trace.get("hasTaskAfter"),
                    "xpError": mark_trace.get("error"),
                })
            except Exception as e:
                print("[XP TRACE][SERVER] failed to write xp trace to submission:", e)
    else:
        print(
            "[XP TRACE][SERVER] submission not solved-like, stats untouched:",
            {
                "submissionId": submission_id,
                "login": login,
                "task": task,
                "status": result_obj.get("status"),
                "statusLabel": result_obj.get("statusLabel"),
                "score": result_obj.get("score"),
            },
        )


def _submit_worker():
    while True:
        with SUBMIT_QUEUE_COND:
            while not SUBMIT_QUEUE and not SUBMIT_QUEUE_PRO:
                SUBMIT_QUEUE_COND.wait()
            if SUBMIT_QUEUE_PRO:
                job = SUBMIT_QUEUE_PRO.popleft()
            else:
                job = SUBMIT_QUEUE.popleft()
        try:
            _run_submission_job(job)
        except Exception as e:
            print("Submission worker fatal job error:", e)


def _ensure_submit_worker():
    global SUBMIT_WORKER_STARTED
    with SUBMIT_QUEUE_LOCK:
        if SUBMIT_WORKER_STARTED:
            return
        t = threading.Thread(target=_submit_worker, daemon=True, name="submit-worker")
        t.start()
        SUBMIT_WORKER_STARTED = True


def _tasks_sync_worker():
    # Keep tasks repo fresh outside the /submit hot path.
    while True:
        try:
            sync_tasks_repo(force=False)
        except Exception as e:
            print("Tasks sync worker error:", e)
        sleep_for = max(15, TASKS_SYNC_TTL)
        time.sleep(sleep_for)


def _ensure_tasks_sync_worker():
    global TASKS_SYNC_WORKER_STARTED
    with SUBMIT_QUEUE_LOCK:
        if TASKS_SYNC_WORKER_STARTED:
            return
        t = threading.Thread(target=_tasks_sync_worker, daemon=True, name="tasks-sync-worker")
        t.start()
        TASKS_SYNC_WORKER_STARTED = True


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
    visibility = str(problem.get("visibility") or "public").strip().lower()
    if visibility not in {"public", "private"}:
        visibility = "public"
    return {
        "id": problem.get("id"),
        "title": problem.get("title", ""),
        "difficulty": problem.get("difficulty", ""),
        "language": normalize_language(problem.get("language")),
        "type": problem.get("type", ""),
        "tags": problem.get("tags") or [],
        "visibility": visibility,
        "ownerLogin": str(problem.get("ownerLogin") or "").strip()
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
        "visibility": str(problem.get("visibility") or "public").strip().lower(),
        "ownerLogin": str(problem.get("ownerLogin") or "").strip(),
        "taskType": problem.get("taskType", "standard"),
        "grader": problem.get("grader") if problem.get("taskType") == "grader" else None,
        "interactor": problem.get("interactor") if problem.get("taskType") == "interactive" else None,
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


def list_tasks(*, viewer_login=None, viewer_is_admin=False):
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
            visibility = str(problem.get("visibility") or "public").strip().lower()
            if visibility == "private":
                owner = str(problem.get("ownerLogin") or "").strip()
                if not viewer_is_admin and (not viewer_login or owner != viewer_login):
                    continue
            tasks.append(public_problem_meta(problem))
        except Exception as e:
            print(f"Task load failed for {name}:", e)
    tasks.sort(key=lambda x: int(x.get("id", 0)))
    return tasks


def _viewer_from_auth_header():
    viewer_login = None
    viewer_is_admin = False
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        if token:
            viewer_login = _resolve_login_from_token(token)
            if viewer_login and FIREBASE_READY:
                try:
                    viewer_is_admin = bool(db.reference(f"admins/{viewer_login}").get())
                except Exception:
                    viewer_is_admin = False
    return viewer_login, viewer_is_admin


def _task_access_allowed(task_id, viewer_login=None, viewer_is_admin=False):
    problem = read_problem_config(task_id)
    if not problem:
        return False
    visibility = str(problem.get("visibility") or "public").strip().lower()
    if visibility != "private":
        return True
    if viewer_is_admin:
        return True
    owner = str(problem.get("ownerLogin") or "").strip()
    return bool(owner and viewer_login == owner)


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


def _runtime_tempdir(prefix):
    os.makedirs(RUNTIME_WORK_DIR, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=prefix, dir=RUNTIME_WORK_DIR)


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
    raw_task_type = str(meta.get("taskType") or "standard").strip().lower()
    task_type = raw_task_type if raw_task_type in ("standard", "grader", "interactive") else "standard"
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

    scoring_mode = str(meta.get("scoringMode") or "ioi").strip().lower()
    groups = _normalize_groups(meta.get("groups"), test_manifest)
    if scoring_mode == "icpc":
        groups = []
    subtasks = [{
        "id": group["id"],
        "name": group["name"],
        "score": group["points"],
        "dependencies": group["dependencies"],
        "tests": group["tests"]
    } for group in groups]

    problem = {
        "formatVersion": 2,
        "schemaVersion": 2,
        "id": task_id,
        "title": meta.get("title") or f"Задача {task_id}",
        "difficulty": meta.get("difficulty", ""),
        "language": lang,
        "type": meta.get("type", ""),
        "tags": meta.get("tags") or [],
        "visibility": str(meta.get("visibility") or "public").strip().lower(),
        "ownerLogin": str(meta.get("ownerLogin") or "").strip(),
        "taskType": task_type,
        "scoringMode": "icpc" if scoring_mode == "icpc" else "ioi",
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
    if task_type == "grader":
        problem["grader"] = {
            "language": "cpp",
            "source": "grader/grader.cpp",
            "header": "grader/grader.h"
        }
    if task_type == "interactive":
        problem["interactor"] = {
            "language": "cpp",
            "source": "interactor/interactor.cpp"
        }
    return problem


def _commit_task_change(task_id, message):
    _ensure_git_identity()
    subprocess.run(
        ["git", "-C", TASKS_REPO_DIR, "add", "-A", f"{task_id}"],
        check=True,
        capture_output=True,
        text=True
    )
    diff = subprocess.run(
        ["git", "-C", TASKS_REPO_DIR, "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True
    )
    if diff.returncode == 0:
        return
    subprocess.run(
        ["git", "-C", TASKS_REPO_DIR, "commit", "-m", message],
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


def _write_task_tree(task_path, problem_v2, files, tests):
    tests_path = os.path.join(task_path, "tests")

    _write_text(os.path.join(task_path, "problem.json"), json.dumps(problem_v2, ensure_ascii=False, indent=2))
    statement_text = files.get("statement", "")
    statement_tex = files.get("statementTex") or statement_text
    tex_path = os.path.join(task_path, "statement", "russian.tex")
    html_path = os.path.join(task_path, "statement", "russian.html")
    _write_text(tex_path, statement_tex)
    os.makedirs(os.path.join(task_path, "statement", "assets"), exist_ok=True)
    compile_result = compile_latex_statement(tex_path, html_path)
    if not compile_result.ok:
        return compile_result

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
    if files.get("grader"):
        _write_text(os.path.join(task_path, "grader", "grader.cpp"), files["grader"])
    if files.get("graderHeader"):
        _write_text(os.path.join(task_path, "grader", "grader.h"), files["graderHeader"])
    if files.get("interactor"):
        _write_text(os.path.join(task_path, "interactor", "interactor.cpp"), files["interactor"])
    for idx, t in enumerate(tests, start=1):
        name = _pad_test_name(idx)
        _write_text(os.path.join(tests_path, name), t.get("input", ""))
        _write_text(os.path.join(tests_path, f"{name}.a"), t.get("output", ""))
    return compile_result


def _save_task_payload(task_id, meta, files, tests, commit_message):
    problem_v2 = _build_problem_v2(task_id, meta, files, tests)
    parent = os.path.abspath(TASKS_REPO_DIR)
    os.makedirs(parent, exist_ok=True)
    tmp_path = tempfile.mkdtemp(prefix=f".task_{task_id}_", dir=parent)
    final_path = task_dir(task_id)
    backup_path = None
    try:
        compile_result = _write_task_tree(tmp_path, problem_v2, files, tests)
        if not compile_result.ok:
            print("statement compile failed:", (compile_result.stderr or "")[:2000])
            shutil.rmtree(tmp_path, ignore_errors=True)
            return False, {
                "error": "statement_compile_failed"
            }
        if os.path.isdir(final_path):
            backup_path = tempfile.mkdtemp(prefix=f".task_{task_id}_old_", dir=parent)
            shutil.rmtree(backup_path)
            os.replace(final_path, backup_path)
        os.replace(tmp_path, final_path)
        try:
            _commit_task_change(task_id, commit_message)
        except Exception:
            if os.path.isdir(final_path):
                shutil.rmtree(final_path, ignore_errors=True)
            if backup_path and os.path.isdir(backup_path):
                os.replace(backup_path, final_path)
            raise
        if backup_path:
            shutil.rmtree(backup_path, ignore_errors=True)
        return True, {"status": "ok", "id": task_id}
    finally:
        if os.path.isdir(tmp_path):
            shutil.rmtree(tmp_path, ignore_errors=True)
        if backup_path and os.path.isdir(backup_path):
            shutil.rmtree(backup_path, ignore_errors=True)


def _compile_cpp(src_path, out_path):
    workdir = os.path.dirname(os.path.abspath(src_path)) or os.getcwd()
    result = run_in_sandbox(
        ["g++", "-std=c++17", "-O2", os.path.basename(src_path), "-o", os.path.basename(out_path)],
        workdir=workdir,
        language="cpp",
        timeout=30,
    )
    return result


def _compile_python(src_path):
    workdir = os.path.dirname(os.path.abspath(src_path)) or os.getcwd()
    return run_in_sandbox(
        ["python3", "-m", "py_compile", os.path.basename(src_path)],
        workdir=workdir,
        language="python",
        timeout=30,
    )


def _run_with_limits(cmd, input_data, timeout_sec, workdir=None, language="cpp"):
    start = time.perf_counter()
    try:
        run_res = run_in_sandbox(
            cmd,
            workdir=workdir or os.getcwd(),
            language=language,
            input_data=input_data,
            timeout=timeout_sec,
        )
    except (subprocess.TimeoutExpired, SandboxError):
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "timeout": True,
            "timeMs": elapsed_ms,
            "memoryMb": None,
            "runRes": None
        }
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return {
        "timeout": bool(getattr(run_res, "timeout", False)),
        "timeMs": elapsed_ms,
        "memoryMb": run_res.memory_mb,
        "runRes": run_res
    }


def _run_cpp_single(code, input_data, timeout_sec):
    with _runtime_tempdir("run_cpp_") as tmp:
        src_path = os.path.join(tmp, "main.cpp")
        bin_path = os.path.join(tmp, "main")
        _write_text(src_path, code)

        compile_res = _compile_cpp(src_path, bin_path)
        if compile_res.returncode != 0:
            print("run-single cpp compile failed:", (compile_res.stderr or "")[:2000])
            return {
                "status": "CE",
                "output": ""
            }

        run_info = _run_with_limits(["./main"], input_data, timeout_sec, workdir=tmp, language="cpp")
        if run_info["timeout"]:
            return {
                "status": "TL",
                "output": "",
                "timeMs": run_info["timeMs"],
                "memoryMb": run_info["memoryMb"]
            }

        run_res = run_info["runRes"]
        if getattr(run_res, "memory_exceeded", False):
            return {
                "status": "ML",
                "output": run_res.stdout,
                "timeMs": run_info["timeMs"],
                "memoryMb": run_info["memoryMb"]
            }
        if run_res.returncode != 0:
            print("run-single cpp runtime failed:", (run_res.stderr or "")[:2000])
            return {
                "status": "RE",
                "output": run_res.stdout,
                "timeMs": run_info["timeMs"],
                "memoryMb": run_info["memoryMb"]
            }

        return {
            "status": "OK",
            "output": run_res.stdout,
            "timeMs": run_info["timeMs"],
            "memoryMb": run_info["memoryMb"]
        }


def _run_python_single(code, input_data, timeout_sec):
    with _runtime_tempdir("run_python_") as tmp:
        src_path = os.path.join(tmp, "main.py")
        _write_text(src_path, code)

        compile_res = _compile_python(src_path)
        if compile_res.returncode != 0:
            print("run-single py compile failed:", (compile_res.stderr or "")[:2000])
            return {
                "status": "CE",
                "output": ""
            }

        run_info = _run_with_limits(["python3", "main.py"], input_data, timeout_sec, workdir=tmp, language="python")
        if run_info["timeout"]:
            return {
                "status": "TL",
                "output": "",
                "timeMs": run_info["timeMs"],
                "memoryMb": run_info["memoryMb"]
            }

        run_res = run_info["runRes"]
        if getattr(run_res, "memory_exceeded", False):
            return {
                "status": "ML",
                "output": run_res.stdout,
                "timeMs": run_info["timeMs"],
                "memoryMb": run_info["memoryMb"]
            }
        if run_res.returncode != 0:
            print("run-single py runtime failed:", (run_res.stderr or "")[:2000])
            return {
                "status": "RE",
                "output": run_res.stdout,
                "timeMs": run_info["timeMs"],
                "memoryMb": run_info["memoryMb"]
            }

        return {
            "status": "OK",
            "output": run_res.stdout,
            "timeMs": run_info["timeMs"],
            "memoryMb": run_info["memoryMb"]
        }


def _parse_cpp_diagnostics(stderr_text):
    markers = []
    if not stderr_text:
        return markers
    pattern = re.compile(r"^(?:[^:\n]+):(\d+):(\d+):\s*(fatal error|error|warning|note):\s*(.+)$")
    severity_map = {
        "fatal error": 8,
        "error": 8,
        "warning": 4,
        "note": 2,
    }
    for raw_line in stderr_text.splitlines():
        line = raw_line.strip()
        m = pattern.match(line)
        if not m:
            continue
        line_no = int(m.group(1))
        col_no = int(m.group(2))
        kind = m.group(3).lower()
        msg = m.group(4).strip()
        markers.append({
            "startLineNumber": line_no,
            "startColumn": max(1, col_no),
            "endLineNumber": line_no,
            "endColumn": max(2, col_no + 1),
            "message": f"{kind}: {msg}",
            "severity": severity_map.get(kind, 8),
        })
    return markers


def _parse_python_diagnostics(stderr_text):
    markers = []
    if not stderr_text:
        return markers
    line_no = None
    col_no = 1
    message = ""
    file_line = re.search(r'File\s+"[^"]*",\s+line\s+(\d+)', stderr_text)
    if file_line:
        line_no = int(file_line.group(1))
    syntax_msg = re.search(r"^(SyntaxError|IndentationError|TabError):\s*(.+)$", stderr_text, re.MULTILINE)
    if syntax_msg:
        message = f"{syntax_msg.group(1)}: {syntax_msg.group(2)}"
    elif stderr_text.strip():
        message = stderr_text.strip().splitlines()[-1]
    if line_no:
        markers.append({
            "startLineNumber": line_no,
            "startColumn": col_no,
            "endLineNumber": line_no,
            "endColumn": col_no + 1,
            "message": message or "python error",
            "severity": 8,
        })
    return markers


def _diagnose_cpp(code):
    with _runtime_tempdir("diag_cpp_") as tmp:
        src_path = os.path.join(tmp, "main.cpp")
        _write_text(src_path, code)
        result = run_in_sandbox(
            ["g++", "-std=c++17", "-fsyntax-only", "main.cpp"],
            workdir=tmp,
            language="cpp",
            timeout=20,
        )
        stderr_text = (result.stderr or "").strip()
        markers = _parse_cpp_diagnostics(stderr_text)
        return {
            "ok": result.returncode == 0,
            "markers": markers
        }


def _diagnose_python(code):
    with _runtime_tempdir("diag_py_") as tmp:
        src_path = os.path.join(tmp, "main.py")
        _write_text(src_path, code)
        result = _compile_python(src_path)
        stderr_text = (result.stderr or "").strip()
        markers = _parse_python_diagnostics(stderr_text)
        return {
            "ok": result.returncode == 0,
            "markers": markers
        }


def _format_cpp(code):
    with _runtime_tempdir("fmt_cpp_") as tmp:
        src_path = os.path.join(tmp, "main.cpp")
        _write_text(src_path, code)
        result = run_in_sandbox(
            ["clang-format", "-i", "main.cpp"],
            workdir=tmp,
            language="cpp",
            timeout=20,
        )
        if result.returncode != 0:
            print("format cpp failed:", (result.stderr or "")[:2000])
            return {"ok": False, "formatted": code}
        with open(src_path, "r", encoding="utf-8") as f:
            formatted = f.read()
        return {"ok": True, "formatted": formatted}


def _format_python(code):
    with _runtime_tempdir("fmt_py_") as tmp:
        src_path = os.path.join(tmp, "main.py")
        _write_text(src_path, code)
        result = run_in_sandbox(
            ["python3", "-m", "black", "--quiet", "main.py"],
            workdir=tmp,
            language="python",
            timeout=20,
        )
        if result.returncode != 0:
            print("format py failed:", (result.stderr or "")[:2000])
            return {"ok": False, "formatted": code}
        with open(src_path, "r", encoding="utf-8") as f:
            formatted = f.read()
        return {"ok": True, "formatted": formatted}


@app.route("/submit", methods=["POST", "OPTIONS"])
def submit():
    # --- OPTIONS preflight ---
    if request.method == "OPTIONS":
        print("=== OPTIONS OK ===")
        return ("", 200)

    print("\n=== ПОЛУЧЕН POST /submit ===")

    # --- читаем JSON ---
    data = request.get_json(silent=True) or {}
    print("JSON RAW:", data)

    payload, payload_error = _validate_submit_payload(data)
    if payload_error:
        return payload_error

    task = str(payload["task_id"])
    code = payload["code"]
    login = payload["user_login"]
    contest_id = payload["contest_id"]
    auth_header = request.headers.get("Authorization", "")
    token_login = None
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        if token:
            token_login = _resolve_login_from_token(token)
            if token_login and token_login != login:
                print(
                    f"[submit] login override by token: payload_user={login} -> token_user={token_login}"
                )
                login = token_login
    # Temporary rollback: take login directly from payload (legacy behavior).
    # Auth token is not required for /submit in this mode.
    tier = _subscription_tier_label(login)
    has_priority = tier in {"pro", "pro_plus"}
    _ensure_tasks_sync_worker()
    if not _rate_limit_global("submit_global", SUBMIT_GLOBAL_RATE_LIMIT, SUBMIT_GLOBAL_RATE_WINDOW):
        return _api_error("service_busy", 429, "GLOBAL_RATE_LIMIT_EXCEEDED")
    if not _rate_limit("submit", login, limit=_submission_rate_limit_for_tier(tier), per_seconds=60):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")
    print(f"Task = {task}")
    print("Code length:", len(code))
    print("User =", login)
    _ensure_submit_worker()

    # Do not run git sync in the hot path. Verify task exists in local mirror.
    if not read_task_meta(task):
        return _api_error("task_not_found", 404, "TASK_NOT_FOUND")
    if not _task_access_allowed(task, viewer_login=login, viewer_is_admin=False):
        return _api_error("forbidden", 403, "FORBIDDEN")
    with SUBMIT_QUEUE_LOCK:
        if (len(SUBMIT_QUEUE) + len(SUBMIT_QUEUE_PRO)) >= MAX_SUBMIT_QUEUE_SIZE:
            return _api_error("queue_overloaded", 503, "QUEUE_OVERLOADED")

    submission_ref = None
    firebase_error = None
    firebase_saved = False

    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return _api_error("submit_storage_unavailable", 503, "SUBMIT_STORAGE_UNAVAILABLE")

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
        firebase_saved = True
    except Exception as e:
        firebase_error = f"firebase_write_error: {e}"
        print(firebase_error)
        return _api_error("submit_storage_write_failed", 503, "SUBMIT_STORAGE_WRITE_FAILED")

    submission_id = submission_ref.key if submission_ref is not None else None
    with SUBMIT_QUEUE_COND:
        if (len(SUBMIT_QUEUE) + len(SUBMIT_QUEUE_PRO)) >= MAX_SUBMIT_QUEUE_SIZE:
            if submission_id and FIREBASE_READY:
                try:
                    db.reference(f"submissions/global/{submission_id}").update({"verdict": "ERROR"})
                except Exception:
                    pass
            return _api_error("queue_overloaded", 503, "QUEUE_OVERLOADED")
        job = {
            "task": task,
            "code": code,
            "submission_id": submission_id,
            "login": login,
            "contestId": contest_id or None,
        }
        if has_priority:
            SUBMIT_QUEUE_PRO.append(job)
            queue_position = len(SUBMIT_QUEUE_PRO)
        else:
            SUBMIT_QUEUE.append(job)
            queue_position = len(SUBMIT_QUEUE) + len(SUBMIT_QUEUE_PRO)
        SUBMIT_QUEUE_COND.notify()

    return jsonify({
        "status": "QUEUE",
        "statusLabel": "QUEUE",
        "submissionId": submission_id,
        "queuePosition": queue_position,
        "firebaseSaved": firebase_saved,
        "priority": "pro" if has_priority else "free",
        "tier": tier
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
        return jsonify({"ok": False, "error": error_code or "captcha_invalid"}), status

    return jsonify({"ok": True})


@app.route("/tasks/list", methods=["GET"])
def tasks_list():
    if not sync_tasks_repo():
        return _api_error("tasks_sync_failed", 500, "TASKS_SYNC_FAILED")
    viewer_login, viewer_is_admin = _viewer_from_auth_header()
    return jsonify(list_tasks(viewer_login=viewer_login, viewer_is_admin=viewer_is_admin))


@app.route("/tasks/<int:task_id>/admin-bundle", methods=["GET"])
def tasks_admin_bundle(task_id):
    if not _is_admin_request():
        return _api_error("admin_required", 403, "ADMIN_REQUIRED")
    if not sync_tasks_repo():
        return _api_error("tasks_sync_failed", 500, "TASKS_SYNC_FAILED")

    problem = read_problem_config(task_id)
    if not problem:
        return abort(404)

    statement = problem.get("statement") or {}
    files = problem.get("files") or {}
    checker = problem.get("checker") or {}
    grader = problem.get("grader") or {}
    interactor = problem.get("interactor") or {}

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
            "grader": _task_text(task_id, grader.get("source")),
            "graderHeader": _task_text(task_id, grader.get("header")),
            "interactor": _task_text(task_id, interactor.get("source")),
        },
        "tests": tests
    })


@app.route("/tasks/<int:task_id>/<path:filename>", methods=["GET"])
def tasks_file(task_id, filename):
    if not sync_tasks_repo():
        return _api_error("tasks_sync_failed", 500, "TASKS_SYNC_FAILED")
    viewer_login, viewer_is_admin = _viewer_from_auth_header()
    if not _task_access_allowed(task_id, viewer_login=viewer_login, viewer_is_admin=viewer_is_admin):
        return _api_error("forbidden", 403, "FORBIDDEN")
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
    actor, actor_error = _require_task_manager()
    if actor_error:
        return actor_error
    if not _rate_limit("tasks_create", actor, limit=20, per_seconds=60):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")
    if not sync_tasks_repo():
        return _api_error("tasks_sync_failed", 500, "TASKS_SYNC_FAILED")

    data = request.get_json(silent=True) or {}
    meta = data.get("meta") or {}
    files = data.get("files") or {}
    tests = data.get("tests") or []
    if not isinstance(meta, dict) or not isinstance(files, dict) or not isinstance(tests, list):
        return _api_error("invalid_payload", 400, "INVALID_PAYLOAD")
    statement_text = files.get("statement")
    if statement_text is not None and (not isinstance(statement_text, str) or len(statement_text) > MAX_STATEMENT_LEN):
        return _api_error("invalid_statement", 400, "INVALID_STATEMENT")
    for key in ("code", "solution", "generator", "checker", "validator", "grader", "graderHeader", "interactor"):
        value = files.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            return _api_error("invalid_payload", 400, "INVALID_PAYLOAD")
        if len(value.encode("utf-8", errors="replace")) > MAX_CODE_SIZE_BYTES:
            return _api_error("payload_too_large", 400, "PAYLOAD_TOO_LARGE")

    task_id = meta.get("id")
    if not isinstance(task_id, int):
        return _api_error("new_task_creation_disabled", 400, "NEW_TASK_CREATION_DISABLED")
    if not os.path.isdir(task_dir(task_id)):
        return _api_error("new_task_creation_disabled", 400, "NEW_TASK_CREATION_DISABLED")

    title = meta.get("title")
    if not _is_nonempty_string(title) or len(str(title)) > MAX_TASK_TITLE_LEN:
        return _api_error("title_required", 400, "TITLE_REQUIRED")
    tags = meta.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or len(tags) > MAX_TAGS_COUNT:
            return _api_error("invalid_tags", 400, "INVALID_TAGS")
        for tag in tags:
            if not isinstance(tag, str) or not tag.strip() or len(tag) > MAX_TAG_LEN:
                return _api_error("invalid_tags", 400, "INVALID_TAGS")
    meta.pop("author", None)
    if actor != "admin":
        meta["ownerLogin"] = actor
        meta["visibility"] = str(meta.get("visibility") or "private").strip().lower()
    else:
        vis = str(meta.get("visibility") or "public").strip().lower()
        meta["visibility"] = vis if vis in {"public", "private"} else "public"
    lang = normalize_language(meta.get("language"))
    if lang not in SUPPORTED_LANGUAGES:
        return _api_error("language_not_supported", 400, "LANGUAGE_NOT_SUPPORTED")
    meta["language"] = lang

    try:
        ok, payload = _save_task_payload(task_id, meta, files, tests, f"Add task {task_id}")
    except Exception as e:
        return _server_error("git_failed", "TASK_CREATE_GIT_FAILED", exc=e)
    if not ok:
        return _api_error(payload.get("error", "task_create_failed"), 400, "TASK_CREATE_FAILED")
    return jsonify(payload)


def _safe_extract_zip(archive, dest_dir):
    with zipfile.ZipFile(archive) as zf:
        dest_abs = os.path.abspath(dest_dir)
        for info in zf.infolist():
            target = os.path.abspath(os.path.join(dest_abs, info.filename))
            if target != dest_abs and not target.startswith(dest_abs + os.sep):
                raise ValueError("unsafe_zip_path")
        zf.extractall(dest_abs)


@app.route("/tasks/import-polygon", methods=["POST"])
def tasks_import_polygon():
    actor, actor_error = _require_task_manager()
    if actor_error:
        return actor_error
    if not _rate_limit("tasks_import_polygon", actor, limit=15, per_seconds=60):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")
    if not sync_tasks_repo():
        return _api_error("tasks_sync_failed", 500, "TASKS_SYNC_FAILED")

    upload = request.files.get("archive")
    if not upload:
        return _api_error("archive_required", 400, "ARCHIVE_REQUIRED")
    buggy_code = (request.form.get("buggyCode") or "").strip()
    if not buggy_code:
        return _api_error("buggy_code_required", 400, "BUGGY_CODE_REQUIRED")
    if len(buggy_code.encode("utf-8", errors="replace")) > MAX_CODE_SIZE_BYTES:
        return _api_error("code_too_large", 400, "CODE_TOO_LARGE")

    language = normalize_language(request.form.get("language"))
    if language not in SUPPORTED_LANGUAGES:
        return _api_error("language_not_supported", 400, "LANGUAGE_NOT_SUPPORTED")
    task_type = str(request.form.get("taskType") or "standard").strip().lower()
    if task_type not in ("standard", "grader", "interactive"):
        task_type = "standard"
    scoring_mode = str(request.form.get("scoringMode") or "ioi").strip().lower()
    if scoring_mode not in ("ioi", "icpc"):
        scoring_mode = "ioi"

    title_override = (request.form.get("title") or "").strip()
    difficulty_override = (request.form.get("difficulty") or "").strip()
    type_override = (request.form.get("type") or "").strip()
    code_explanation_latex = (request.form.get("codeExplanationLatex") or "").strip()

    task_id = _next_task_id()

    with tempfile.TemporaryDirectory(prefix="polygon_import_") as tmp:
        archive_path = os.path.join(tmp, "polygon.zip")
        extract_path = os.path.join(tmp, "extract")
        os.makedirs(extract_path, exist_ok=True)
        upload.save(archive_path)
        try:
            _safe_extract_zip(archive_path, extract_path)
            payload = parse_polygon_package(extract_path, task_id)
            if title_override:
                payload["meta"]["title"] = title_override
            payload["meta"]["language"] = language
            payload["meta"]["taskType"] = task_type
            payload["meta"]["scoringMode"] = scoring_mode
            if actor != "admin":
                payload["meta"]["ownerLogin"] = actor
                payload["meta"]["visibility"] = "private"
            else:
                vis = str(payload["meta"].get("visibility") or "public").strip().lower()
                payload["meta"]["visibility"] = vis if vis in {"public", "private"} else "public"
            if difficulty_override:
                payload["meta"]["difficulty"] = difficulty_override
            if type_override:
                payload["meta"]["type"] = type_override
            payload["files"]["code"] = buggy_code
            if code_explanation_latex:
                payload["files"]["help"] = code_explanation_latex
            ok, result = _save_task_payload(
                task_id,
                payload["meta"],
                payload["files"],
                payload["tests"],
                f"Import Polygon task {task_id}"
            )
        except (PolygonImportError, zipfile.BadZipFile, ValueError) as e:
            print("polygon import failed:", e)
            return _api_error("polygon_import_failed", 400, "POLYGON_IMPORT_FAILED")
        except Exception as e:
            return _server_error("git_failed", "POLYGON_IMPORT_GIT_FAILED", exc=e)

    if not ok:
        return _api_error(result.get("error", "polygon_import_failed"), 400, "POLYGON_IMPORT_FAILED")
    return jsonify(result)


@app.route("/tasks/delete", methods=["POST"])
def tasks_delete():
    if not _is_admin_request():
        return _api_error("admin_required", 403, "ADMIN_REQUIRED")
    if not _rate_limit("tasks_delete", "admin", limit=20, per_seconds=60):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")
    if not sync_tasks_repo():
        return _api_error("tasks_sync_failed", 500, "TASKS_SYNC_FAILED")

    data = request.get_json(silent=True) or {}
    task_id = data.get("id")
    if not isinstance(task_id, int):
        return _api_error("id_required", 400, "ID_REQUIRED")

    task_path = task_dir(task_id)
    if not os.path.isdir(task_path):
        return _api_error("not_found", 404, "NOT_FOUND")

    try:
        subprocess.run(
            ["rm", "-rf", task_path],
            check=True
        )
    except Exception as e:
        return _server_error("delete_failed", "TASK_DELETE_FAILED", exc=e)

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
        return _server_error("git_failed", "TASK_DELETE_GIT_FAILED", exc=e)

    return jsonify({"status": "ok", "id": task_id})


@app.route("/tasks/generate-tests", methods=["POST"])
def tasks_generate_tests():
    actor, actor_error = _require_task_manager()
    if actor_error:
        return actor_error
    if not _rate_limit("tasks_generate_tests", actor, limit=10, per_seconds=60):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")

    data = request.get_json(silent=True) or {}
    generator_code = data.get("generator", "")
    solution_code = data.get("solution", "")
    count = data.get("count", 0)
    lang = normalize_language(data.get("language"))

    if not isinstance(count, int) or count <= 0:
        return _api_error("count_required", 400, "COUNT_REQUIRED")
    if count > MAX_GENERATED_TESTS:
        return _api_error("count_too_large", 400, "COUNT_TOO_LARGE")
    if not generator_code.strip():
        return _api_error("generator_required", 400, "GENERATOR_REQUIRED")
    if not solution_code.strip():
        return _api_error("solution_required", 400, "SOLUTION_REQUIRED")
    if len(generator_code.encode("utf-8", errors="replace")) > MAX_CODE_SIZE_BYTES:
        return _api_error("generator_too_large", 400, "GENERATOR_TOO_LARGE")
    if len(solution_code.encode("utf-8", errors="replace")) > MAX_CODE_SIZE_BYTES:
        return _api_error("solution_too_large", 400, "SOLUTION_TOO_LARGE")

    with _runtime_tempdir("generate_tests_") as tmp:
        if lang == "python":
            gen_src = os.path.join(tmp, "generator.py")
            sol_src = os.path.join(tmp, "solution.py")
            _write_text(gen_src, generator_code)
            _write_text(sol_src, solution_code)

            gen_compile = _compile_python(gen_src)
            if gen_compile.returncode != 0:
                print("generator compile failed:", (gen_compile.stderr or "")[:2000])
                return _api_error("generator_compile_failed", 400, "GENERATOR_COMPILE_FAILED")

            sol_compile = _compile_python(sol_src)
            if sol_compile.returncode != 0:
                print("solution compile failed:", (sol_compile.stderr or "")[:2000])
                return _api_error("solution_compile_failed", 400, "SOLUTION_COMPILE_FAILED")
        else:
            gen_src = os.path.join(tmp, "generator.cpp")
            sol_src = os.path.join(tmp, "solution.cpp")
            gen_bin = os.path.join(tmp, "gen")
            sol_bin = os.path.join(tmp, "sol")
            _write_text(gen_src, generator_code)
            _write_text(sol_src, solution_code)

            gen_compile = _compile_cpp(gen_src, gen_bin)
            if gen_compile.returncode != 0:
                print("generator compile failed:", (gen_compile.stderr or "")[:2000])
                return _api_error("generator_compile_failed", 400, "GENERATOR_COMPILE_FAILED")

            sol_compile = _compile_cpp(sol_src, sol_bin)
            if sol_compile.returncode != 0:
                print("solution compile failed:", (sol_compile.stderr or "")[:2000])
                return _api_error("solution_compile_failed", 400, "SOLUTION_COMPILE_FAILED")

        tests = []
        for i in range(1, count + 1):
            try:
                if lang == "python":
                    gen_run = run_in_sandbox(
                        ["python3", "generator.py", str(i)],
                        workdir=tmp,
                        language="python",
                        timeout=5,
                    )
                else:
                    gen_run = run_in_sandbox(
                        ["./gen", str(i)],
                        workdir=tmp,
                        language="cpp",
                        timeout=5,
                    )
            except (subprocess.TimeoutExpired, SandboxError):
                return _api_error("generator_timeout", 400, "GENERATOR_TIMEOUT")

            if gen_run.returncode != 0:
                print("generator runtime failed:", (gen_run.stderr or "")[:2000], "index=", i)
                if getattr(gen_run, "timeout", False):
                    return _api_error("generator_timeout", 400, "GENERATOR_TIMEOUT")
                return _api_error("generator_runtime_failed", 400, "GENERATOR_RUNTIME_FAILED")

            inp = gen_run.stdout
            try:
                if lang == "python":
                    sol_run = run_in_sandbox(
                        ["python3", "solution.py"],
                        workdir=tmp,
                        language="python",
                        input_data=inp,
                        timeout=5,
                    )
                else:
                    sol_run = run_in_sandbox(
                        ["./sol"],
                        workdir=tmp,
                        language="cpp",
                        input_data=inp,
                        timeout=5,
                    )
            except (subprocess.TimeoutExpired, SandboxError):
                return _api_error("solution_timeout", 400, "SOLUTION_TIMEOUT")

            if sol_run.returncode != 0:
                print("solution runtime failed:", (sol_run.stderr or "")[:2000], "index=", i)
                if getattr(sol_run, "timeout", False):
                    return _api_error("solution_timeout", 400, "SOLUTION_TIMEOUT")
                return _api_error("solution_runtime_failed", 400, "SOLUTION_RUNTIME_FAILED")
            tests.append({
                "input": inp,
                "output": sol_run.stdout
            })

        return jsonify({"tests": tests})


@app.route("/run-single", methods=["POST"])
def run_single():
    user_login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    tier = _subscription_tier_label(user_login)
    if not _rate_limit("run_single", user_login, limit=_editor_rate_limit_for_tier(tier), per_seconds=60):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")
    payload, payload_error = _validate_run_payload(request.get_json(silent=True) or {}, tier=tier)
    if payload_error:
        return payload_error
    if tier in {"pro", "pro_plus"}:
        timeout_sec = RUN_SINGLE_TIMEOUT_PRO
    else:
        timeout_sec = RUN_SINGLE_TIMEOUT_FREE

    if payload["language"] == "python":
        result = _run_python_single(payload["code"], payload["input"], timeout_sec)
    else:
        result = _run_cpp_single(payload["code"], payload["input"], timeout_sec)
    result["tier"] = tier
    return jsonify(result)


@app.route("/editor/diagnostics", methods=["POST"])
def editor_diagnostics():
    user_login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    tier = _subscription_tier_label(user_login)
    if not _rate_limit("editor_diag", user_login, limit=_editor_rate_limit_for_tier(tier), per_seconds=60):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")

    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    if not isinstance(code, str):
        return _api_error("invalid_payload", 400, "INVALID_PAYLOAD")
    if len(code.encode("utf-8", errors="replace")) > MAX_CODE_SIZE_BYTES:
        return _api_error("code_too_large", 400, "CODE_TOO_LARGE")
    lang = _validate_language(data.get("language")) or "cpp"
    if not code.strip():
        return jsonify({"ok": True, "markers": []})
    try:
        if lang == "python":
            result = _diagnose_python(code)
        else:
            result = _diagnose_cpp(code)
    except (subprocess.TimeoutExpired, SandboxError) as e:
        print("diagnostics timeout/error:", e)
        return _api_error("diagnostics_failed", 500, "DIAGNOSTICS_TIMEOUT")
    except Exception as e:
        return _server_error("diagnostics_failed", "DIAGNOSTICS_FAILED", exc=e)
    return jsonify({"ok": bool(result.get("ok")), "markers": result.get("markers") or []})


@app.route("/editor/format", methods=["POST"])
def editor_format():
    user_login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    tier = _subscription_tier_label(user_login)
    if not _rate_limit("editor_format", user_login, limit=_editor_rate_limit_for_tier(tier), per_seconds=60):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")

    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    if not isinstance(code, str):
        return _api_error("invalid_payload", 400, "INVALID_PAYLOAD")
    if len(code.encode("utf-8", errors="replace")) > MAX_CODE_SIZE_BYTES:
        return _api_error("code_too_large", 400, "CODE_TOO_LARGE")
    lang = _validate_language(data.get("language")) or "cpp"
    if not code.strip():
        return jsonify({"ok": True, "formatted": ""})
    try:
        if lang == "python":
            result = _format_python(code)
        else:
            result = _format_cpp(code)
    except (subprocess.TimeoutExpired, SandboxError) as e:
        print("format timeout/error:", e)
        return _api_error("format_failed", 500, "FORMAT_TIMEOUT")
    except Exception as e:
        return _server_error("format_failed", "FORMAT_FAILED", exc=e)
    return jsonify({"ok": bool(result.get("ok")), "formatted": result.get("formatted", code)})


@app.route("/editor/ai-complete", methods=["POST"])
def editor_ai_complete():
    user_login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    tier = _subscription_tier_label(user_login)
    limit = 20 if tier == "free" else 30
    if not _rate_limit("editor_ai", user_login, limit=limit, per_seconds=60):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")

    data = request.get_json(silent=True) or {}
    language = _validate_language(data.get("language")) or "cpp"
    prefix = data.get("prefix", "")
    suffix = data.get("suffix", "")

    if not isinstance(prefix, str) or not isinstance(suffix, str):
        return _api_error("invalid_payload", 400, "INVALID_PAYLOAD")
    if len(prefix.encode("utf-8", errors="replace")) > MAX_EDITOR_PREFIX_BYTES:
        return _api_error("prefix_too_large", 400, "PREFIX_TOO_LARGE")
    if len(suffix.encode("utf-8", errors="replace")) > MAX_EDITOR_SUFFIX_BYTES:
        return _api_error("suffix_too_large", 400, "SUFFIX_TOO_LARGE")
    if not prefix.strip():
        return jsonify({"ok": True, "completion": ""})

    completion, error = _request_ai_code_completion(language, prefix, suffix)
    if error:
        status = 503 if error == "ai_completion_not_configured" else 502
        return _api_error("ai_completion_failed", status, error.upper())
    return jsonify({"ok": True, "completion": completion})


@app.route("/admin/purge-users", methods=["POST"])
def admin_purge_users():
    if not _is_admin_request():
        return _api_error("forbidden", 403, "FORBIDDEN")
    if not _rate_limit("admin_purge_users", "admin", limit=3, per_seconds=300):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")

    data = request.get_json(silent=True) or {}
    if data.get("confirm") != "DELETE_ALL_USERS":
        return _api_error("confirm_required", 400, "CONFIRM_REQUIRED")

    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not _ensure_firebase_ready():
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")

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
        return _server_error("auth_purge_failed", "AUTH_PURGE_FAILED", exc=e)

    try:
        db.reference("users").set(None)
        db.reference("userAuthMap").set(None)
        db.reference("emailToLogin").set(None)
        db.reference("admins").set(None)
    except Exception as e:
        return _server_error("db_purge_failed", "DB_PURGE_FAILED", exc=e)

    return jsonify({
        "status": "ok",
        "deletedAuth": deleted_auth,
        "deletedDbNodes": ["users", "userAuthMap", "emailToLogin", "admins"]
    })


def _is_solved_submission(item):
    item = item or {}
    verdict = str(item.get("verdict", "")).strip().upper()
    status_label = str(item.get("statusLabel", "")).strip().upper()
    status = str(item.get("status", "")).strip().upper()
    raw_verdict = str(item.get("rawVerdict", "")).strip().upper()

    if verdict == "OK" or status_label == "OK" or status == "OK" or raw_verdict == "OK":
        return True

    score = item.get("score")
    try:
        if score is not None and float(str(score).replace(",", ".")) >= 100.0:
            return True
    except Exception:
        pass

    for field in (verdict, status_label, status):
        try:
            if field and float(str(field).replace(",", ".")) >= 100.0:
                return True
        except Exception:
            continue
    return False


def _normalize_solved_map(raw):
    if isinstance(raw, list):
        return {
            str(idx): True
            for idx, value in enumerate(raw)
            if bool(value)
        }
    if isinstance(raw, dict):
        return {
            str(task): True
            for task, value in raw.items()
            if bool(value)
        }
    return {}


def _mark_task_solved_for_user(login, task):
    trace = {
        "ok": False,
        "login": str(login or "").strip(),
        "task": str(task or "").strip(),
        "alreadySolved": None,
        "beforeCnt": None,
        "beforeExp": None,
        "afterCnt": None,
        "afterExp": None,
        "hasTaskAfter": None,
        "error": None,
    }
    if not FIREBASE_READY:
        trace["error"] = "FIREBASE_NOT_READY"
        return trace
    login = str(login or "").strip()
    task = str(task or "").strip()
    if not login or not task:
        trace["error"] = "INVALID_LOGIN_OR_TASK"
        return trace
    try:
        task_difficulties = _load_task_difficulties()
        stats_ref = db.reference(f"users/{login}/stats")
        current = stats_ref.get() or {}
        current = current if isinstance(current, dict) else {}
        before_solved = _normalize_solved_map(current.get("solved"))
        before_cnt = int(current.get("cnt") or 0)
        before_exp = int(current.get("exp") or 0)
        solved_map = _normalize_solved_map(current.get("solved"))
        already_solved = bool(solved_map.get(task))
        trace["alreadySolved"] = already_solved
        trace["beforeCnt"] = before_cnt
        trace["beforeExp"] = before_exp
        solved_map[task] = True
        exp = sum(
            _xp_for_difficulty(_task_difficulty_for_xp(task_id, task_difficulties))
            for task_id in solved_map
        )
        payload = {
            "solved": solved_map,
            "cnt": len(solved_map),
            "exp": exp,
        }
        print(
            "[XP TRACE][SERVER] stats recompute before write:",
            {
                "login": login,
                "task": task,
                "alreadySolved": already_solved,
                "beforeCnt": before_cnt,
                "beforeExp": before_exp,
                "beforeSolvedSize": len(before_solved),
                "afterCnt": payload["cnt"],
                "afterExp": payload["exp"],
                "afterSolvedSize": len(solved_map),
            },
        )
        stats_ref.update(payload)
        final_stats = stats_ref.get() or {}
        final_stats = final_stats if isinstance(final_stats, dict) else {}
        final_solved = _normalize_solved_map(final_stats.get("solved"))
        trace["afterCnt"] = int(final_stats.get("cnt") or 0)
        trace["afterExp"] = int(final_stats.get("exp") or 0)
        trace["hasTaskAfter"] = bool(final_solved.get(task))
        trace["ok"] = True
        print(
            "[XP TRACE][SERVER] stats committed:",
            {
                "login": login,
                "task": task,
                "finalCnt": final_stats.get("cnt"),
                "finalExp": final_stats.get("exp"),
                "hasTask": bool(final_solved.get(task)),
            },
        )
    except Exception as e:
        print(f"mark solved stats update failed (login={login}, task={task}):", e)
        trace["error"] = str(e)
    return trace


def _xp_for_difficulty(difficulty):
    difficulty = str(difficulty or "").strip().lower()
    values = {
        "tutorial": 2,
        "easy": 4,
        "casual": 7,
        "normal": 12,
        "hard": 20,
        "insane": 30,
        "extreme": 45,
        "ultra": 60,
        "impossible": 80,
        "tourist": 110,
    }
    return values.get(difficulty, 5)


def _rank_name_by_exp(exp):
    try:
        x = int(exp)
    except Exception:
        x = 0
    if x < 20:
        return "tutorial"
    if x < 50:
        return "easy"
    if x < 100:
        return "casual"
    if x < 180:
        return "normal"
    if x < 300:
        return "hard"
    if x < 450:
        return "insane"
    if x < 650:
        return "extreme"
    if x < 900:
        return "ultra"
    if x < 1200:
        return "impossible"
    return "tourist"


def _load_task_difficulties():
    difficulties = {}
    if not os.path.isdir(TASKS_REPO_DIR):
        return difficulties
    for name in os.listdir(TASKS_REPO_DIR):
        if not str(name).isdigit():
            continue
        problem = _read_json(os.path.join(TASKS_REPO_DIR, name, "problem.json")) or {}
        if problem:
            difficulties[str(name)] = str(problem.get("difficulty") or "")
            continue
        meta = _read_json(os.path.join(TASKS_REPO_DIR, name, "meta.json")) or {}
        difficulties[str(name)] = str(meta.get("difficulty") or "")
    return difficulties


def _task_difficulty_for_xp(task_id, task_difficulties):
    try:
        numeric_id = int(str(task_id))
    except (TypeError, ValueError):
        return task_difficulties.get(str(task_id), "")
    if 0 <= numeric_id <= 22:
        return "normal"
    if numeric_id in (23, 24):
        return "hard"
    if numeric_id in (25, 26):
        return "impossible"
    return task_difficulties.get(str(task_id), "")


def _is_valid_firebase_path_part(value):
    part = str(value or "").strip()
    if not part:
        return False
    return not bool(re.search(r"[.#$/\[\]]", part))


def _is_valid_login_name(login):
    if not isinstance(login, str):
        return False
    value = login.strip()
    return bool(re.fullmatch(r"[A-Za-z0-9_]{3,16}", value))


@app.route("/profile/change-login", methods=["POST"])
def profile_change_login():
    login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    if not _rate_limit("change_login", login, limit=5, per_seconds=3600):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")
    if not _is_pro_active(login):
        return _api_error("pro_required", 403, "PRO_REQUIRED")
    data = request.get_json(silent=True) or {}
    new_login = str(data.get("newLogin") or "").strip()
    if not _is_valid_login_name(new_login):
        return _api_error("invalid_login", 400, "INVALID_LOGIN")
    if new_login == login:
        return _api_error("same_login", 400, "SAME_LOGIN")
    sub = _get_user_subscription(login)
    now_ms = int(time.time() * 1000)
    changed_at = sub.get("nicknameChangedAt")
    try:
        changed_at = int(changed_at) if changed_at is not None else None
    except Exception:
        changed_at = None
    if changed_at is not None:
        cooldown_ms = NICKNAME_CHANGE_COOLDOWN_SECONDS * 1000
        left = changed_at + cooldown_ms - now_ms
        if left > 0:
            return _api_error("nickname_cooldown", 429, f"COOLDOWN_{left}")

    if not _ensure_firebase_ready():
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")
    try:
        current_uid = None
        # find uid by reverse lookup userAuthMap/{uid}=login
        user_auth_map = db.reference("userAuthMap").get() or {}
        for uid, mapped in (user_auth_map or {}).items():
            if str(mapped) == login:
                current_uid = str(uid)
                break
        if not current_uid:
            return _api_error("user_mapping_missing", 400, "USER_MAPPING_MISSING")
        # enforce uniqueness
        existing_user = db.reference(f"users/{new_login}").get()
        if existing_user:
            return _api_error("login_taken", 409, "LOGIN_TAKEN")
        for _, mapped in (user_auth_map or {}).items():
            if str(mapped) == new_login:
                return _api_error("login_taken", 409, "LOGIN_TAKEN")

        old_profile = db.reference(f"users/{login}").get() or {}
        if not isinstance(old_profile, dict):
            old_profile = {}
        old_profile["login"] = new_login
        if not isinstance(old_profile.get("subscription"), dict):
            old_profile["subscription"] = {}
        old_profile["subscription"]["nicknameChangedAt"] = now_ms
        old_profile["subscription"]["updatedAt"] = now_ms

        updates = {
            f"users/{new_login}": old_profile,
            f"users/{login}": None,
            f"userAuthMap/{current_uid}": new_login
        }
        email = str(old_profile.get("email") or "").strip().lower()
        if email:
            updates[f"emailToLogin/{email.replace('.', ',')}"] = new_login

        # Migrate incoming friend links in other user profiles.
        users_raw = db.reference("users").get() or {}
        if isinstance(users_raw, dict):
            for other_login, other_profile in users_raw.items():
                if not isinstance(other_profile, dict):
                    continue
                friends = other_profile.get("friends")
                if not isinstance(friends, dict):
                    continue
                if login in friends:
                    updates[f"users/{other_login}/friends/{new_login}"] = friends.get(login)
                    updates[f"users/{other_login}/friends/{login}"] = None

        # Migrate contest registration keys.
        contest_regs = db.reference("contest_regs").get() or {}
        if isinstance(contest_regs, dict):
            for contest_id, regs in contest_regs.items():
                if not isinstance(regs, dict):
                    continue
                if login in regs:
                    updates[f"contest_regs/{contest_id}/{new_login}"] = regs.get(login)
                    updates[f"contest_regs/{contest_id}/{login}"] = None

        db.reference("/").update(updates)
        _append_activity(new_login, "nickname_change", {"oldLogin": login, "newLogin": new_login})
        return jsonify({"status": "ok", "oldLogin": login, "newLogin": new_login, "nextChangeAt": now_ms + NICKNAME_CHANGE_COOLDOWN_SECONDS * 1000})
    except Exception as e:
        return _server_error("change_login_failed", "CHANGE_LOGIN_FAILED", exc=e)


def _platega_headers():
    return {
        "X-MerchantId": PLATEGA_MERCHANT_ID,
        "X-Secret": PLATEGA_SECRET,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def _platega_request(path, method="GET", payload=None, timeout=20):
    url = urllib.parse.urljoin(PLATEGA_API_BASE + "/", str(path or "").lstrip("/"))
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method.upper(), headers=_platega_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "ignore")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"Platega HTTP {e.code}: {body[:1000]}") from e


def _activate_paid_subscription(login, tier, transaction_id, amount=None):
    now = _now_ms()
    period_ms = SUBSCRIPTION_PERIOD_DAYS * 86_400_000
    ref = db.reference(f"users/{login}/subscription")
    current = ref.get() or {}
    if not isinstance(current, dict):
        current = {}
    normalized = _normalize_subscription(login, current, write_back=False)
    current_exp = _to_int(normalized.get("expiresAt"))
    base = current_exp if normalized.get("status") in {"active", "grace"} and current_exp > now else now
    expires_at = base + period_ms
    payload = {
        "tier": str(tier or "pro").lower(),
        "status": "active",
        "activatedAt": current.get("activatedAt") or now,
        "updatedAt": now,
        "expiresAt": expires_at,
        "graceUntil": None,
        "paymentWarning": None,
        "failedPaymentAt": None,
        "lastPaymentAt": now,
        "lastPaymentTransactionId": transaction_id,
        "lastPaymentAmount": amount,
        "visuals": current.get("visuals") if isinstance(current.get("visuals"), dict) else {"seasonalEnabled": True},
        "features": _subscription_features_for_tier(tier)
    }
    payload["visuals"]["seasonalEnabled"] = True
    ref.update(payload)
    _append_activity(login, "subscription_payment", {
        "tier": tier,
        "transactionId": transaction_id,
        "expiresAt": expires_at
    })
    return _normalize_subscription(login, payload, write_back=False)


def _mark_paid_subscription_problem(login, tier, transaction_id, status):
    now = _now_ms()
    ref = db.reference(f"users/{login}/subscription")
    current = ref.get() or {}
    if not isinstance(current, dict):
        current = {}
    normalized = _normalize_subscription(login, current, write_back=False)
    if str(status).upper() == "CHARGEBACKED":
        update = {
            "tier": str(tier or normalized.get("tier") or "pro").lower(),
            "status": "disabled",
            "paymentWarning": "chargeback",
            "failedPaymentAt": now,
            "updatedAt": now,
            "features": {"earlyAccess": False}
        }
    elif normalized.get("status") in {"active", "grace"}:
        update = {
            "tier": str(tier or normalized.get("tier") or "pro").lower(),
            "status": "grace",
            "paymentWarning": "payment_failed",
            "failedPaymentAt": now,
            "graceUntil": max(_to_int(normalized.get("graceUntil")), now + SUBSCRIPTION_GRACE_DAYS * 86_400_000),
            "updatedAt": now,
            "features": _subscription_features_for_tier(tier or normalized.get("tier"))
        }
    else:
        update = {
            "tier": str(tier or normalized.get("tier") or "pro").lower(),
            "status": "disabled",
            "paymentWarning": "payment_failed",
            "failedPaymentAt": now,
            "updatedAt": now,
            "features": {"earlyAccess": False}
        }
    ref.update(update)
    return _normalize_subscription(login, {**current, **update}, write_back=False)


@app.route("/payments/platega/create", methods=["POST"])
def platega_create_payment():
    login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    if not _ensure_firebase_ready():
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")
    if not PLATEGA_MERCHANT_ID or not PLATEGA_SECRET:
        return _api_error("payments_not_configured", 503, "PAYMENTS_NOT_CONFIGURED")

    data = request.get_json(silent=True) or {}
    tier = str(data.get("tier") or "").strip().lower()
    if tier not in {"pro", "pro_plus"}:
        return _api_error("invalid_tier", 400, "INVALID_TIER")
    public_price = _subscription_price_for_tier(tier)
    if public_price is None:
        return _api_error("invalid_tier", 400, "INVALID_TIER")
    amount = _platega_amount_for_price(public_price)

    label = "PRO+" if tier == "pro_plus" else "PRO"
    payload_obj = {
        "login": login,
        "tier": tier,
        "periodDays": SUBSCRIPTION_PERIOD_DAYS,
        "publicPrice": public_price,
        "providerAmount": amount,
        "amountMultiplier": PLATEGA_AMOUNT_MULTIPLIER,
        "createdAt": _now_ms()
    }
    body = {
        "paymentDetails": {
            "amount": amount,
            "currency": PLATEGA_CURRENCY
        },
        "description": f"CodeBug {label} на {SUBSCRIPTION_PERIOD_DAYS} дней для {login}",
        "return": PLATEGA_SUCCESS_URL,
        "failedUrl": PLATEGA_FAILED_URL,
        "payload": json.dumps(payload_obj, ensure_ascii=False)
    }
    if PLATEGA_PAYMENT_METHOD:
        try:
            body["paymentMethod"] = int(PLATEGA_PAYMENT_METHOD)
        except ValueError:
            body["paymentMethod"] = PLATEGA_PAYMENT_METHOD

    try:
        result = _platega_request(PLATEGA_CREATE_PATH, method="POST", payload=body)
        transaction_id = str(result.get("transactionId") or result.get("id") or "").strip()
        payment_url = str(result.get("redirect") or result.get("url") or result.get("payformSuccessUrl") or "").strip()
        if not transaction_id or not payment_url:
            print("[payments][platega] unexpected create response:", result)
            return _api_error("payment_provider_bad_response", 502, "PAYMENT_PROVIDER_BAD_RESPONSE")

        record = {
            "provider": "platega",
            "login": login,
            "tier": tier,
            "label": label,
            "publicPrice": public_price,
            "amountMultiplier": PLATEGA_AMOUNT_MULTIPLIER,
            "amount": amount,
            "currency": PLATEGA_CURRENCY,
            "status": str(result.get("status") or "PENDING").upper(),
            "transactionId": transaction_id,
            "paymentUrl": payment_url,
            "expiresIn": result.get("expiresIn"),
            "createdAt": _now_ms(),
            "updatedAt": _now_ms(),
            "request": body,
            "providerResponse": result
        }
        db.reference(f"subscriptions/payments/{transaction_id}").set(record)
        db.reference(f"subscriptions/requests/{transaction_id}").set({
            "login": login,
            "tier": tier,
            "label": label,
            "status": "awaiting_payment",
            "provider": "platega",
            "transactionId": transaction_id,
            "publicPrice": public_price,
            "amountMultiplier": PLATEGA_AMOUNT_MULTIPLIER,
            "amount": amount,
            "currency": PLATEGA_CURRENCY,
            "paymentUrl": payment_url,
            "createdAt": record["createdAt"],
            "updatedAt": record["updatedAt"]
        })
        return jsonify({
            "ok": True,
            "transactionId": transaction_id,
            "status": record["status"],
            "paymentUrl": payment_url,
            "redirect": payment_url
        })
    except Exception as e:
        return _server_error("payment_create_failed", "PAYMENT_CREATE_FAILED", exc=e, status=502)


@app.route("/payments/platega/callback", methods=["POST"])
def platega_callback():
    merchant_id = request.headers.get("X-MerchantId", "")
    secret = request.headers.get("X-Secret", "")
    if not PLATEGA_MERCHANT_ID or not PLATEGA_SECRET or merchant_id != PLATEGA_MERCHANT_ID or secret != PLATEGA_SECRET:
        print("[payments][platega] callback auth failed", {"merchant": merchant_id})
        return _api_error("forbidden", 403, "FORBIDDEN")
    if not _ensure_firebase_ready():
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")

    data = request.get_json(silent=True) or {}
    transaction_id = str(data.get("id") or data.get("transactionId") or "").strip()
    status = str(data.get("status") or "").strip().upper()
    if not transaction_id or not status:
        return _api_error("invalid_payload", 400, "INVALID_PAYLOAD")

    try:
        pay_ref = db.reference(f"subscriptions/payments/{transaction_id}")
        payment = pay_ref.get() or {}
        if not isinstance(payment, dict) or not payment:
            print("[payments][platega] callback for unknown transaction:", transaction_id, data)
            return _api_error("payment_not_found", 404, "PAYMENT_NOT_FOUND")
        login = str(payment.get("login") or "").strip()
        tier = str(payment.get("tier") or "pro").strip().lower()
        amount = data.get("amount", payment.get("amount"))
        now = _now_ms()
        pay_ref.update({
            "status": status,
            "callback": data,
            "updatedAt": now,
            "confirmedAt": now if status == "CONFIRMED" else payment.get("confirmedAt")
        })
        db.reference(f"subscriptions/requests/{transaction_id}").update({
            "status": "approved" if status == "CONFIRMED" else status.lower(),
            "callbackStatus": status,
            "updatedAt": now,
            "resolvedAt": now if status in {"CONFIRMED", "CANCELED", "CHARGEBACKED"} else None
        })
        if status == "CONFIRMED":
            subscription = _activate_paid_subscription(login, tier, transaction_id, amount)
            print("[payments][platega] subscription activated", login, tier, transaction_id)
        elif status in {"CANCELED", "CHARGEBACKED"}:
            subscription = _mark_paid_subscription_problem(login, tier, transaction_id, status)
            print("[payments][platega] subscription payment problem", login, tier, status, transaction_id)
        else:
            subscription = _get_user_subscription(login)
        return jsonify({"ok": True, "status": status, "subscription": subscription})
    except Exception as e:
        return _server_error("payment_callback_failed", "PAYMENT_CALLBACK_FAILED", exc=e)


@app.route("/payments/subscription-status", methods=["GET"])
def payment_subscription_status():
    login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    return jsonify({"ok": True, "login": login, "subscription": _get_user_subscription(login)})


@app.route("/users/<path:login>/profile-lite", methods=["GET"])
def user_profile_lite(login):
    if not _ensure_firebase_ready():
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")
    login = str(login or "").strip()
    if not login:
        return _api_error("invalid_login", 400, "INVALID_LOGIN")
    try:
        data = db.reference(f"users/{login}").get() or {}
        if not isinstance(data, dict) or not data:
            return _api_error("not_found", 404, "NOT_FOUND")
        profile_style = data.get("profileStyle") if isinstance(data.get("profileStyle"), dict) else {}
        stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
        raw_sub = data.get("subscription") if isinstance(data.get("subscription"), dict) else {}
        return jsonify({
            "login": data.get("login") or login,
            "avatar": data.get("avatar"),
            "profileStyle": profile_style,
            "subscription": _normalize_subscription(login, raw_sub, write_back=True),
            "stats": {
                "cnt": stats.get("cnt", 0),
                "exp": stats.get("exp", 0),
                "rating": stats.get("rating", 0)
            }
        })
    except Exception as e:
        return _server_error("profile_lite_failed", "PROFILE_LITE_FAILED", exc=e)


@app.route("/profile/set-nick-color", methods=["POST"])
def profile_set_nick_color():
    login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    if not _is_pro_active(login):
        return _api_error("pro_required", 403, "PRO_REQUIRED")
    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")
    data = request.get_json(silent=True) or {}
    color = str(data.get("color") or "").strip().lower()
    tier = _subscription_tier_label(login)
    allowed = set(PRO_NICK_COLORS)
    if tier in {"pro_plus"}:
        allowed.update(PRO_PLUS_NICK_THEMES)
    if color not in allowed:
        return _api_error("invalid_color", 400, "INVALID_COLOR")
    try:
        ref = db.reference(f"users/{login}/subscription")
        current = ref.get() or {}
        if not isinstance(current, dict):
            current = {}
        visuals = current.get("visuals") if isinstance(current.get("visuals"), dict) else {}
        visuals["nickColor"] = color
        ref.update({
            "visuals": visuals,
            "updatedAt": int(time.time() * 1000)
        })
        return jsonify({"ok": True, "color": color})
    except Exception as e:
        return _server_error("set_nick_color_failed", "SET_NICK_COLOR_FAILED", exc=e)


@app.route("/profile/set-cover", methods=["POST"])
def profile_set_cover():
    login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    if not _rate_limit("profile_set_cover", login, limit=30, per_seconds=3600):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")
    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")

    data = request.get_json(silent=True) or {}
    cover_id = str(data.get("coverId") or "").strip().lower()
    custom_image = data.get("customImage")
    clear_custom = bool(data.get("clearCustom"))

    if not cover_id and custom_image is None and not clear_custom:
        return _api_error("invalid_payload", 400, "INVALID_PAYLOAD")
    if cover_id and cover_id not in PROFILE_COVER_PRESETS:
        return _api_error("invalid_cover_id", 400, "INVALID_COVER_ID")

    has_custom_payload = custom_image is not None
    normalized_custom = None
    if has_custom_payload:
        if not isinstance(custom_image, str):
            return _api_error("invalid_custom_cover", 400, "INVALID_CUSTOM_COVER")
        normalized_custom = custom_image.strip()
        if normalized_custom:
            if not _is_pro_active(login):
                return _api_error("pro_required", 403, "PRO_REQUIRED")
            if not normalized_custom.startswith("data:image/"):
                return _api_error("invalid_custom_cover", 400, "INVALID_CUSTOM_COVER")
            if len(normalized_custom.encode("utf-8", errors="replace")) > MAX_PROFILE_COVER_IMAGE_BYTES:
                return _api_error("custom_cover_too_large", 400, "CUSTOM_COVER_TOO_LARGE")
        else:
            clear_custom = True

    try:
        ref = db.reference(f"users/{login}/profileStyle")
        current = ref.get() or {}
        if not isinstance(current, dict):
            current = {}

        next_style = dict(current)
        next_style["coverId"] = cover_id or str(next_style.get("coverId") or DEFAULT_PROFILE_COVER_ID)
        if clear_custom:
            next_style.pop("customCover", None)
        if normalized_custom:
            next_style["customCover"] = normalized_custom
        next_style["updatedAt"] = int(time.time() * 1000)

        ref.set(next_style)
        return jsonify({
            "ok": True,
            "coverId": next_style.get("coverId"),
            "hasCustomCover": bool(next_style.get("customCover"))
        })
    except Exception as e:
        return _server_error("set_cover_failed", "SET_COVER_FAILED", exc=e)


@app.route("/admin/rebuild-user-stats", methods=["POST"])
def admin_rebuild_user_stats():
    if not _is_admin_request():
        return _api_error("forbidden", 403, "FORBIDDEN")
    if not _rate_limit("admin_rebuild_user_stats", "admin", limit=6, per_seconds=300):
        return _api_error("rate_limit_exceeded", 429, "RATE_LIMIT_EXCEEDED")

    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")

    started_at = time.time()
    try:
        users_raw = db.reference("users").get() or {}
        submissions_raw = db.reference("submissions/global").get() or {}
        task_difficulties = _load_task_difficulties() or {}

        if isinstance(submissions_raw, dict):
            submissions_iter = submissions_raw.values()
            submissions_scanned = len(submissions_raw)
        elif isinstance(submissions_raw, list):
            submissions_iter = submissions_raw
            submissions_scanned = len(submissions_raw)
        else:
            submissions_iter = []
            submissions_scanned = 0

        solved_by_user = {}
        for sub in submissions_iter:
            if not isinstance(sub, dict):
                continue
            login = str(sub.get("login") or "").strip()
            if not login:
                continue
            task = str(sub.get("task") or "").strip()
            if not task or not task.isdigit():
                continue
            if not _is_solved_submission(sub):
                continue
            solved_by_user.setdefault(login, {})[task] = True

        users_map = users_raw if isinstance(users_raw, dict) else {}
        updates = {}
        updated = 0
        skipped_users = 0

        for login, udata in users_map.items():
            login = str(login or "").strip()
            if not _is_valid_firebase_path_part(login):
                skipped_users += 1
                continue
            stats = {}
            if isinstance(udata, dict):
                raw_stats = udata.get("stats")
                if isinstance(raw_stats, dict):
                    stats = dict(raw_stats)
            solved_map = solved_by_user.get(login, {})
            stats["solved"] = solved_map
            stats["cnt"] = len(solved_map)
            stats["exp"] = sum(
                _xp_for_difficulty(_task_difficulty_for_xp(task_id, task_difficulties))
                for task_id in solved_map
            )
            updates[f"users/{login}/stats"] = stats
            updated += 1

        failed_updates = 0
        if updates:
            items = list(updates.items())
            chunk_size = 120
            for start in range(0, len(items), chunk_size):
                chunk_items = items[start:start + chunk_size]
                chunk_payload = dict(chunk_items)
                try:
                    db.reference("/").update(chunk_payload)
                except Exception as chunk_err:
                    # Fallback: isolate bad record(s) instead of failing the whole rebuild.
                    for path, value in chunk_items:
                        try:
                            db.reference(path).set(value)
                        except Exception:
                            failed_updates += 1

        elapsed_ms = int((time.time() - started_at) * 1000)
        return jsonify({
            "status": "ok",
            "usersUpdated": updated,
            "usersWithSolved": len(solved_by_user),
            "submissionsScanned": submissions_scanned,
            "tasksLoaded": len(task_difficulties),
            "skippedUsers": skipped_users,
            "failedUpdates": failed_updates,
            "elapsedMs": elapsed_ms
        })
    except Exception as e:
        return _server_error("rebuild_user_stats_failed", "REBUILD_USER_STATS_FAILED", exc=e)


def _difficulty_rank(value):
    order = {
        "tutorial": 0,
        "easy": 1,
        "casual": 2,
        "normal": 3,
        "hard": 4,
        "insane": 5,
        "extreme": 6,
        "ultra": 7,
        "impossible": 8,
        "tourist": 9,
    }
    return order.get(str(value or "").strip().lower(), 3)


@app.route("/profile/extended-stats/<login>", methods=["GET"])
def profile_extended_stats(login):
    requester, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    if not _is_pro_plus_active(requester):
        return _api_error("pro_plus_required", 403, "PRO_PLUS_REQUIRED")
    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")
    try:
        submissions = db.reference("submissions/global").get() or {}
    except Exception as e:
        return _server_error("stats_load_failed", "STATS_LOAD_FAILED", exc=e)
    target = str(login or "").strip()
    now_ms = int(time.time() * 1000)
    day_ms = 24 * 60 * 60 * 1000
    verdicts = {}
    by_day_30 = {}
    by_day_90 = {}
    ac_times = []
    for sub in (submissions or {}).values():
        if not isinstance(sub, dict):
            continue
        if str(sub.get("login") or "").strip() != target:
            continue
        ts = int(sub.get("date") or 0)
        verdict = str(sub.get("verdict") or sub.get("statusLabel") or "UNKNOWN").strip().upper()
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
        d = ts // day_ms
        if now_ms - ts <= 30 * day_ms:
            by_day_30[str(d)] = by_day_30.get(str(d), 0) + 1
        if now_ms - ts <= 90 * day_ms:
            by_day_90[str(d)] = by_day_90.get(str(d), 0) + 1
        if _is_solved_submission(sub):
            try:
                ac_times.append(float(sub.get("timeMs") or 0))
            except Exception:
                pass
    avg_ac_time = round(sum(ac_times) / len(ac_times), 2) if ac_times else 0.0
    feed = db.reference(f"users/{target}/activityFeed").get() or {}
    feed_items = sorted(
        [v for v in feed.values() if isinstance(v, dict)],
        key=lambda x: int(x.get("ts") or 0),
        reverse=True
    )[:100]
    return jsonify({
        "ok": True,
        "target": target,
        "avgAcTimeMs": avg_ac_time,
        "verdictDistribution": verdicts,
        "dailySolved30": by_day_30,
        "dailySolved90": by_day_90,
        "activityFeed": feed_items,
    })


@app.route("/recommendations", methods=["GET"])
def recommendations():
    login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")
    if not _is_pro_plus_active(login):
        return _api_error("pro_plus_required", 403, "PRO_PLUS_REQUIRED")
    if not sync_tasks_repo():
        return _api_error("tasks_sync_failed", 500, "TASKS_SYNC_FAILED")
    solved = _normalize_solved_map((db.reference(f"users/{login}/stats/solved").get() if FIREBASE_READY else {}) or {})
    all_tasks = list_tasks(viewer_login=login, viewer_is_admin=False)
    user_stats = db.reference(f"users/{login}/stats").get() if FIREBASE_READY else {}
    user_exp = int((user_stats or {}).get("exp") or 0)
    target_rank = _difficulty_rank(_rank_name_by_exp(user_exp))
    recent_ac_tags = {}
    submissions = db.reference("submissions/global").get() if FIREBASE_READY else {}
    ac_tasks = []
    for sub in (submissions or {}).values():
        if not isinstance(sub, dict):
            continue
        if str(sub.get("login") or "").strip() != login:
            continue
        if not _is_solved_submission(sub):
            continue
        ac_tasks.append(str(sub.get("task") or ""))
    ac_tasks = ac_tasks[-40:]
    for task_meta in all_tasks:
        if str(task_meta.get("id")) in ac_tasks:
            for tag in (task_meta.get("tags") or []):
                key = str(tag or "").strip().lower()
                if key:
                    recent_ac_tags[key] = recent_ac_tags.get(key, 0) + 1
    candidates = []
    for task_meta in all_tasks:
        task_id = str(task_meta.get("id") or "")
        if not task_id or task_id in solved:
            continue
        tags = [str(t or "").strip().lower() for t in (task_meta.get("tags") or []) if str(t or "").strip()]
        tag_score = sum(recent_ac_tags.get(t, 0) for t in tags)
        diff_score = 5 - abs(_difficulty_rank(task_meta.get("difficulty")) - target_rank)
        candidates.append((tag_score * 3 + diff_score, task_meta))
    candidates.sort(key=lambda x: (x[0], -int(x[1].get("id") or 0)), reverse=True)
    return jsonify({
        "ok": True,
        "items": [c[1] for c in candidates[:25]]
    })


@app.route("/contests/create", methods=["POST"])
def contests_create():
    login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    is_admin = _is_admin_request()
    if not is_admin and not _is_pro_plus_active(login):
        return _api_error("pro_plus_required", 403, "PRO_PLUS_REQUIRED")
    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip()
    tasks = data.get("tasks") or []
    if not title or not isinstance(tasks, list) or not tasks:
        return _api_error("invalid_payload", 400, "INVALID_PAYLOAD")
    description = str(data.get("description") or "").strip()[:1000]
    logo = str(data.get("logo") or "").strip()
    if logo:
        if len(logo) > 500_000 or not re.match(r"^data:image/(png|jpe?g|webp|gif);base64,", logo, re.I):
            return _api_error("invalid_logo", 400, "INVALID_LOGO")
    start = int(data.get("start") or 0)
    end = int(data.get("end") or 0)
    try:
        start_year = time.gmtime(start / 1000).tm_year
        end_year = time.gmtime(end / 1000).tm_year
    except Exception:
        start_year = 0
        end_year = 0
    if end <= start or not (2020 <= start_year <= 2100) or not (2020 <= end_year <= 2100):
        return _api_error("invalid_time_range", 400, "INVALID_TIME_RANGE")
    visibility = str(data.get("visibility") or "private").strip().lower()
    if visibility not in {"private", "public"}:
        visibility = "private"
    if visibility == "public" and not is_admin:
        return _api_error("admin_required", 403, "ADMIN_REQUIRED")
    allowed = data.get("allowedUsers") or []
    if not isinstance(allowed, list):
        allowed = []
    allowed = [str(x).strip() for x in allowed if str(x).strip()]
    if login not in allowed:
        allowed.append(login)
    payload = {
        "title": title,
        "description": description,
        "logo": logo,
        "authors": [login],
        "tasks": [int(x) for x in tasks if str(x).isdigit()],
        "start": start,
        "end": end,
        "visibility": visibility,
        "ownerLogin": login,
        "allowedUsers": allowed,
        "createdAt": int(time.time() * 1000),
    }
    ref = db.reference("contests").push()
    ref.set(payload)
    _append_activity(login, "contest_create", {"contestId": ref.key, "title": title, "visibility": visibility})
    return jsonify({"ok": True, "id": ref.key})


@app.route("/contest/register", methods=["POST"])
def contest_register():
    login, auth_error = _require_user_login()
    if auth_error:
        return auth_error
    global FIREBASE_READY
    if not FIREBASE_READY:
        FIREBASE_READY = init_firebase()
    if not FIREBASE_READY:
        return _api_error("firebase_not_ready", 500, "FIREBASE_NOT_READY")
    data = request.get_json(silent=True) or {}
    contest_id = str(data.get("contestId") or "").strip()
    if not contest_id:
        return _api_error("contest_id_required", 400, "CONTEST_ID_REQUIRED")
    contest = db.reference(f"contests/{contest_id}").get() or {}
    if not isinstance(contest, dict) or not contest:
        return _api_error("contest_not_found", 404, "CONTEST_NOT_FOUND")
    if str(contest.get("visibility") or "public").lower() == "private":
        allowed = contest.get("allowedUsers") or []
        if login not in [str(x).strip() for x in allowed]:
            return _api_error("forbidden", 403, "FORBIDDEN")
    db.reference(f"contest_regs/{contest_id}/{login}").set({
        "registeredAt": int(time.time() * 1000)
    })
    _append_activity(login, "contest_register", {"contestId": contest_id})
    return jsonify({"ok": True})


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
        "recaptchaSiteKey": RECAPTCHA_SITE_KEY,
        "subscriptions": {
            "periodDays": SUBSCRIPTION_PERIOD_DAYS,
            "prices": {
                "pro": SUBSCRIPTION_PRICE_PRO_RUB,
                "pro_plus": SUBSCRIPTION_PRICE_PRO_PLUS_RUB
            },
            "currency": PLATEGA_CURRENCY
        }
    })


def _serve_site_page(filename):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path)


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
    _ensure_tasks_sync_worker()
    app.run(host="0.0.0.0", port=port)
