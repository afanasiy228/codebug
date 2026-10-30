"""Small public read models. No judge secrets, private tests or reference code."""
import base64
import hashlib
import io
import json
import os
import time

from flask import jsonify, request, send_file


def submission_rows(runtime, field, value):
    key = ("submission-read", field, value)
    cached = runtime._cache_get(key)
    if cached is not None:
        return cached
    ref = runtime.db.reference("submissions/global")
    try:
        raw = ref.order_by_child(field).equal_to(value).get() or {}
    except (AttributeError, ValueError):
        raw = runtime._cache_get(("submission-legacy-read",))
        if raw is None:
            raw = ref.get() or {}
            runtime._cache_set(("submission-legacy-read",), raw, 5)
    except Exception as exc:
        # Older deployments can serve clients while the new RTDB indexes deploy.
        if "index" not in str(exc).lower():
            raise
        raw = runtime._cache_get(("submission-legacy-read",))
        if raw is None:
            raw = ref.get() or {}
            runtime._cache_set(("submission-legacy-read",), raw, 5)
    fields = {"login", "task", "contestId", "verdict", "status", "statusLabel", "rawVerdict", "score", "date", "createdAt", "ts", "timeMs", "memoryMb", "firstFail", "passedGroups"}
    rows = []
    for identifier, item in raw.items():
        if not isinstance(item, dict) or item.get(field) != value:
            continue
        rows.append({"_id": identifier, **{key: item[key] for key in fields if key in item}})
    rows.sort(key=lambda item: float(item.get("date") or 0))
    return runtime._cache_set(key, rows, 10)


def invalidate_submissions(runtime, login, contest_id=None):
    runtime._cache_delete(("submission-read", "login", login))
    runtime._cache_delete(("submission-legacy-read",))
    if contest_id:
        runtime._cache_delete(("submission-read", "contestId", contest_id))


def register_read_api(app, runtime):
    def response(data, seconds=30, private=False):
        result = jsonify(data)
        result.headers["Cache-Control"] = "private, no-store" if private else f"public, max-age={seconds}, stale-while-revalidate={seconds}"
        if private:
            result.headers["Vary"] = "Authorization"
        else:
            result.set_etag(hashlib.sha256(result.get_data()).hexdigest())
            result.make_conditional(request)
        return result

    def contest_access(contest):
        if str(contest.get("visibility", "public")).lower() != "private":
            return True
        login, admin = runtime._viewer_from_auth_header()
        return bool(admin or (login and (login == contest.get("ownerLogin") or login in (contest.get("allowedUsers") or []))))

    def public_files(meta):
        statement = meta.get("statement") or {}
        files = meta.get("files") or {}
        paths = [statement.get(key) for key in ("html", "markdown", "hint")]
        paths.append(files.get("code"))
        for test in (meta.get("openTests") or [])[:2]:
            paths.extend([test.get("input"), test.get("answer")])
        return list(dict.fromkeys(path for path in paths if isinstance(path, str) and path))

    @app.get("/tasks/catalog")
    def task_catalog():
        if not runtime._ready_tasks_for_read():
            return runtime._api_error("tasks_sync_failed", 503, "TASKS_SYNC_FAILED")
        # Local metadata mtimes also cover immediate admin edits before a Git commit.
        fingerprint = []
        for name in sorted(os.listdir(runtime.TASKS_REPO_DIR)):
            if not name.isdigit():
                continue
            for filename in ("problem.json", "meta.json"):
                path = os.path.join(runtime.TASKS_REPO_DIR, name, filename)
                if os.path.isfile(path):
                    fingerprint.append((name, filename, os.stat(path).st_mtime_ns))
        key = ("task-catalog", tuple(fingerprint))
        catalog = runtime._cache_get(key)
        if catalog is None:
            catalog = []
            seen = set()
            for name, _, _ in fingerprint:
                if name in seen:
                    continue
                seen.add(name)
                problem = runtime.read_problem_config(name)
                if not problem or runtime.task_verification_status(problem) != "approved" or str(problem.get("visibility", "public")).lower() == "private":
                    continue
                catalog.append({
                    "id": int(name), "title": problem.get("title", ""),
                    "difficulty": problem.get("difficulty", ""),
                    "language": problem.get("language", "cpp"), "taskType": problem.get("taskType", "standard"),
                    "tags": problem.get("tags") or [], "kinds": runtime.task_kinds(problem),
                    "mainTag": (runtime.task_kinds(problem) or [""])[0],
                    "verificationStatus": "approved", "visibility": "public",
                    "shortDescription": problem.get("shortDescription", ""),
                })
            catalog.sort(key=lambda item: item["id"])
            runtime._cache_set(key, catalog, 60)
        return response(catalog, 60)

    @app.get("/tasks/<int:task_id>/view")
    def task_view(task_id):
        if not runtime._ready_tasks_for_read():
            return runtime._api_error("tasks_sync_failed", 503, "TASKS_SYNC_FAILED")
        login, admin = runtime._viewer_from_auth_header()
        if not runtime._task_access_allowed(task_id, viewer_login=login, viewer_is_admin=admin):
            return runtime._api_error("forbidden", 403, "FORBIDDEN")
        problem = runtime.read_problem_config(task_id)
        if not problem:
            return runtime._api_error("not_found", 404, "NOT_FOUND")
        meta = runtime.public_problem_meta(problem)
        private = str(problem.get("visibility", "public")).lower() == "private" or runtime.task_verification_status(problem) != "approved"
        paths = public_files(meta)
        stat = []
        for path in paths + ["problem.json", "meta.json"]:
            full = runtime.safe_task_file(task_id, path)
            if full and os.path.isfile(full):
                stat.append((path, os.stat(full).st_mtime_ns, os.path.getsize(full)))
        revision = hashlib.sha256(json.dumps([meta, stat], sort_keys=True).encode()).hexdigest()[:20]
        key = ("task-view", task_id, revision)
        package = runtime._cache_get(key)
        if package is None:
            contents = {}
            total = 0
            for path in paths:
                full = runtime.safe_task_file(task_id, path)
                if not full or not os.path.isfile(full):
                    continue
                size = os.path.getsize(full)
                total += size
                if total > 2 * 1024 * 1024:
                    return runtime._api_error("task_view_too_large", 413, "TASK_VIEW_TOO_LARGE")
                contents[path] = runtime._read_text(full)
            package = {"meta": {**meta, "revision": revision}, "files": contents}
            runtime._cache_set(key, package, 60)
        return response(package, 60, private=private or bool(request.headers.get("Authorization")))

    @app.get("/users/<login>/submissions")
    def user_submissions(login):
        if not runtime._is_valid_login_name(login):
            return runtime._api_error("invalid_login", 400, "INVALID_LOGIN")
        if not runtime._ensure_firebase_ready():
            return runtime._api_error("unavailable", 503, "UNAVAILABLE")
        # The underlying submission records are public; expose only display fields.
        return response(submission_rows(runtime, "login", login), 5)

    @app.get("/contests/<contest_id>/submissions")
    def contest_submissions(contest_id):
        if not runtime._is_valid_firebase_path_part(contest_id):
            return runtime._api_error("invalid_contest_id", 400, "INVALID_CONTEST_ID")
        if not runtime._ensure_firebase_ready():
            return runtime._api_error("unavailable", 503, "UNAVAILABLE")
        contest = runtime.db.reference(f"contests/{contest_id}").get()
        if not isinstance(contest, dict) or not contest_access(contest):
            return runtime._api_error("forbidden", 403, "FORBIDDEN")
        return response(submission_rows(runtime, "contestId", contest_id), 5, private=str(contest.get("visibility", "public")).lower() == "private")

    @app.get("/contests/list")
    def contest_list():
        if not runtime._ensure_firebase_ready():
            return runtime._api_error("unavailable", 503, "UNAVAILABLE")
        cached = runtime._cache_get(("contests-read",))
        if cached is None:
            raw = runtime.db.reference("contests").get() or {}
            cached = []
            for identifier, item in raw.items():
                if not isinstance(item, dict):
                    continue
                contest = {**item, "id": identifier}
                logo = str(contest.get("logo") or "")
                if logo.startswith("data:image/") and str(contest.get("visibility", "public")).lower() != "private":
                    revision = hashlib.sha256(logo.encode()).hexdigest()[:16]
                    contest["logo"] = runtime.PUBLIC_API_BASE + f"/contests/{identifier}/logo?v={revision}"
                cached.append(contest)
            runtime._cache_set(("contests-read",), cached, 30)
        visible = [item for item in cached if contest_access(item)]
        return response(visible, 30, private=bool(request.headers.get("Authorization")))

    @app.get("/contests/<contest_id>/logo")
    def contest_logo(contest_id):
        if not runtime._is_valid_firebase_path_part(contest_id):
            return runtime._api_error("invalid_contest_id", 400, "INVALID_CONTEST_ID")
        if not runtime._ensure_firebase_ready():
            return runtime._api_error("unavailable", 503, "UNAVAILABLE")
        key = ("contest-logo", contest_id, request.args.get("v", ""))
        cached = runtime._cache_get(key)
        if cached is None:
            contest = runtime.db.reference(f"contests/{contest_id}").get() or {}
            if str(contest.get("visibility", "public")).lower() == "private":
                return runtime._api_error("forbidden", 403, "FORBIDDEN")
            logo = str(contest.get("logo") or "")
            try:
                prefix, encoded = logo.split(";base64,", 1)
                mime = prefix.removeprefix("data:")
                if mime not in {"image/png", "image/jpeg", "image/webp", "image/gif"} or len(encoded) > 700000:
                    raise ValueError("invalid image")
                cached = (base64.b64decode(encoded, validate=True), mime)
            except (ValueError, TypeError):
                return runtime._api_error("not_found", 404, "NOT_FOUND")
            runtime._cache_set(key, cached, 300)
        return send_file(io.BytesIO(cached[0]), mimetype=cached[1], max_age=86400, etag=hashlib.sha256(cached[0]).hexdigest())
