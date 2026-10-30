import base64
import json
from pathlib import Path

import read_api


def task(root, identifier, **extra):
    directory = root / str(identifier)
    directory.mkdir()
    config = {"id": identifier, "title": "Public task", "language": "cpp", "formatVersion": 2,
              "schemaVersion": 2, "statement": {"html": "statement/russian.html"},
              "files": {"code": "solutions/wa.cpp", "solution": "solutions/main.cpp"},
              "tests": [{"name": "001", "input": "tests/001", "answer": "tests/001.a", "visibility": "open"},
                        {"name": "002", "input": "tests/002", "answer": "tests/002.a", "visibility": "private"}], **extra}
    (directory / "problem.json").write_text(json.dumps(config))
    for name, content in {"statement/russian.html": "<p>Public statement</p>", "solutions/wa.cpp": "broken",
                          "solutions/main.cpp": "secret reference", "tests/001": "public input",
                          "tests/001.a": "public output", "tests/002": "private input", "tests/002.a": "private answer"}.items():
        path = directory / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(content)
    return directory


def test_catalog_is_compact_public_and_conditionally_cached(srv, tmp_path, monkeypatch):
    task(tmp_path, 1)
    task(tmp_path, 2, visibility="private", ownerLogin="student")
    task(tmp_path, 3, verificationStatus="pending")
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(tmp_path))
    monkeypatch.setattr(srv.module, "sync_tasks_repo", lambda: (_ for _ in ()).throw(AssertionError("Git on read path")))
    result = srv.client.get("/tasks/catalog")
    assert result.status_code == 200
    assert [item["id"] for item in result.json] == [1]
    assert not {"tests", "groups", "files", "solution"} & result.json[0].keys()
    assert "public" in result.headers["Cache-Control"]
    assert srv.client.get("/tasks/catalog", headers={"If-None-Match": result.headers["ETag"]}).status_code == 304


def test_view_contains_only_public_files_and_revision_changes_on_edit(srv, tmp_path, monkeypatch):
    directory = task(tmp_path, 1)
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(tmp_path))
    first = srv.client.get("/tasks/1/view")
    assert first.status_code == 200
    assert set(first.json["files"]) == {"statement/russian.html", "solutions/wa.cpp", "tests/001", "tests/001.a"}
    assert "secret reference" not in first.get_data(as_text=True)
    assert "private answer" not in first.get_data(as_text=True)
    assert srv.client.get("/tasks/1/view", headers={"If-None-Match": first.headers["ETag"]}).status_code == 304
    (directory / "solutions/wa.cpp").write_text("updated broken code")
    second = srv.client.get("/tasks/1/view")
    assert second.json["meta"]["revision"] != first.json["meta"]["revision"]
    assert second.json["files"]["solutions/wa.cpp"] == "updated broken code"


def test_view_checks_authorization_before_using_cache(srv, tmp_path, monkeypatch):
    task(tmp_path, 1, visibility="private", ownerLogin="student")
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(tmp_path))
    monkeypatch.setattr(srv.module, "_task_access_allowed", lambda _id, viewer_login=None, **kw: viewer_login == "student")
    token = srv.add_user("student")
    allowed = srv.client.get("/tasks/1/view", headers={"Authorization": f"Bearer {token}"})
    assert allowed.status_code == 200
    assert allowed.headers["Cache-Control"] == "private, no-store"
    assert srv.client.get("/tasks/1/view").status_code == 403


def test_submission_query_filters_users_and_strips_internal_fields(srv):
    srv.db.data["submissions"] = {"global": {
        "one": {"login": "alice", "task": 1, "verdict": "OK", "date": 1, "code": "private code", "log": "private log"},
        "two": {"login": "bob", "task": 2, "verdict": "WA", "date": 2},
    }}
    result = srv.client.get("/users/alice/submissions")
    assert result.status_code == 200
    assert result.json == [{"_id": "one", "login": "alice", "task": 1, "verdict": "OK", "date": 1}]
    srv.db.data["submissions"]["global"]["three"] = {"login": "alice", "task": 3, "verdict": "OK", "date": 3}
    read_api.invalidate_submissions(srv.module, "alice")
    assert len(srv.client.get("/users/alice/submissions").json) == 2


def test_contest_catalog_excludes_private_and_extracts_inline_logo(srv):
    image = b"test image"
    srv.db.data["contests"] = {
        "open": {"title": "Open", "logo": "data:image/png;base64," + base64.b64encode(image).decode()},
        "closed": {"title": "Private", "visibility": "private", "ownerLogin": "alice", "allowedUsers": []},
    }
    result = srv.client.get("/contests/list")
    assert [item["id"] for item in result.json] == ["open"]
    assert "base64" not in result.json[0]["logo"]
    assert "/contests/open/logo?v=" in result.json[0]["logo"]
    logo = srv.client.get("/contests/open/logo")
    assert logo.data == image
    assert "max-age=86400" in logo.headers["Cache-Control"]
    assert srv.client.get("/contests/closed/logo").status_code == 403
    token = srv.add_user("alice")
    own = srv.client.get("/contests/list", headers={"Authorization": f"Bearer {token}"})
    assert {item["id"] for item in own.json} == {"open", "closed"}
    assert own.headers["Cache-Control"] == "private, no-store"


def test_private_contest_submissions_need_a_permitted_viewer(srv):
    srv.db.data["contests"] = {"closed": {"visibility": "private", "ownerLogin": "alice"}}
    assert srv.client.get("/contests/closed/submissions").status_code == 403
    token = srv.add_user("alice")
    result = srv.client.get("/contests/closed/submissions", headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "private, no-store"
