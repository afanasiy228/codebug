import json
from pathlib import Path

import server as server_module


REAL_TASK_ACCESS_ALLOWED = server_module._task_access_allowed
REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_problem(root, task_id, **extra):
    task_dir = root / str(task_id)
    task_dir.mkdir(parents=True)
    problem = {
        "formatVersion": 2,
        "schemaVersion": 2,
        "id": task_id,
        "title": f"Task {task_id}",
        "language": "cpp",
        "statement": {},
        "files": {},
        "tests": [],
        **extra,
    }
    (task_dir / "problem.json").write_text(
        json.dumps(problem, ensure_ascii=False), encoding="utf-8"
    )
    return task_dir / "problem.json"


def test_regular_users_only_receive_approved_tasks(srv, tmp_path, monkeypatch):
    _write_problem(tmp_path, 1)  # Legacy tasks without the field remain approved.
    _write_problem(tmp_path, 2, verificationStatus="pending")
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(tmp_path))

    regular = srv.module.list_tasks(viewer_login="student", viewer_is_admin=False)
    admin = srv.module.list_tasks(viewer_login="admin", viewer_is_admin=True)

    assert [task["id"] for task in regular] == [1]
    assert [task["id"] for task in admin] == [1, 2]
    assert admin[1]["verificationStatus"] == "pending"

    regular_token = srv.add_user("student")
    admin_token = srv.add_user("admin", admin=True)
    regular_response = srv.client.get(
        "/tasks/list", headers={"Authorization": f"Bearer {regular_token}"}
    )
    admin_response = srv.client.get(
        "/tasks/list", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert [task["id"] for task in regular_response.get_json()] == [1]
    assert [task["id"] for task in admin_response.get_json()] == [1, 2]


def test_pending_task_cannot_be_opened_without_admin(srv, tmp_path, monkeypatch):
    _write_problem(tmp_path, 2, verificationStatus="pending")
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(tmp_path))
    monkeypatch.setattr(srv.module, "_task_access_allowed", REAL_TASK_ACCESS_ALLOWED)

    assert not REAL_TASK_ACCESS_ALLOWED(2, viewer_login="student")
    assert REAL_TASK_ACCESS_ALLOWED(2, viewer_login="admin", viewer_is_admin=True)

    regular_token = srv.add_user("student")
    regular_response = srv.client.get(
        "/tasks/2/problem.json",
        headers={"Authorization": f"Bearer {regular_token}"},
    )
    admin_token = srv.add_user("moderator", admin=True)
    admin_response = srv.client.get(
        "/tasks/2/problem.json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert regular_response.status_code == 403
    assert admin_response.status_code == 200


def test_admin_can_approve_a_pending_task(srv, tmp_path, monkeypatch):
    problem_path = _write_problem(tmp_path, 2, verificationStatus="pending")
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(tmp_path))
    commits = []
    monkeypatch.setattr(
        srv.module,
        "_commit_task_change",
        lambda task_id, message: commits.append((task_id, message)),
    )
    token = srv.add_user("moderator", admin=True)

    response = srv.client.post(
        "/tasks/2/verification",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.get_json()
    assert json.loads(problem_path.read_text(encoding="utf-8"))["verificationStatus"] == "approved"
    assert commits and commits[0][0] == 2


def test_admin_can_remove_task_approval(srv, tmp_path, monkeypatch):
    problem_path = _write_problem(tmp_path, 2, verificationStatus="approved")
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(tmp_path))
    monkeypatch.setattr(srv.module, "_commit_task_change", lambda *_args: None)
    token = srv.add_user("moderator", admin=True)

    response = srv.client.post(
        "/tasks/2/verification",
        json={"status": "pending"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.get_json()
    assert json.loads(problem_path.read_text(encoding="utf-8"))["verificationStatus"] == "pending"


def test_admin_can_delete_task(srv, tmp_path, monkeypatch):
    problem_path = _write_problem(tmp_path, 2, verificationStatus="pending")
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(tmp_path))
    commits = []
    monkeypatch.setattr(
        srv.module,
        "_commit_task_change",
        lambda task_id, message: commits.append((task_id, message)),
    )
    token = srv.add_user("moderator", admin=True)

    response = srv.client.post(
        "/tasks/delete",
        json={"id": 2},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.get_json()
    assert not problem_path.parent.exists()
    assert commits == [(2, "Delete task 2")]


def test_new_task_payload_defaults_to_pending(srv):
    problem = srv.module._build_problem_v2(
        68,
        {"id": 68, "title": "New", "language": "cpp"},
        {},
        [],
    )

    assert problem["verificationStatus"] == "pending"


def test_default_seed_admins_include_the_moderation_team(srv):
    assert {"afanasy", "klinyks", "grospor", "foxserg"}.issubset(
        set(srv.module.SEED_ADMIN_LOGINS)
    )


def test_training_page_separates_pending_tasks_and_sends_admin_auth():
    page = (REPO_ROOT / "train.html").read_text(encoding="utf-8")

    assert "Подтверждённые задачи" in page
    assert "Неподтверждённые задачи" in page
    assert "/verification`" in page
    assert "Authorization: `Bearer ${token}`" in page
    assert "Убрать подтверждение" in page
    assert 'remove.textContent = "Удалить"' in page
    assert "createTaskRow(problem)" in page


def test_admin_can_open_pending_task_assets_with_auth():
    page = (REPO_ROOT / "problem.html").read_text(encoding="utf-8")

    assert "const taskFetch = (url) => fetch(url, taskRequestOptions)" in page
    assert "taskFetch(`${base}/tasks/${id}/problem.json`)" in page


def test_admin_can_reveal_editorial_and_solution(srv, tmp_path, monkeypatch):
    _write_problem(
        tmp_path,
        7,
        verificationStatus="approved",
        statement={"editorial": "statement/editorial.md"},
        files={"solution": "solutions/main.cpp"},
    )
    task_dir = tmp_path / "7"
    (task_dir / "statement").mkdir()
    (task_dir / "solutions").mkdir()
    (task_dir / "statement" / "editorial.md").write_text(
        "# Idea\n\nThe missing invariant.", encoding="utf-8"
    )
    (task_dir / "solutions" / "main.cpp").write_text(
        "int main() {}\n", encoding="utf-8"
    )
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(tmp_path))
    token = srv.add_user("moderator", admin=True)

    regular_response = srv.client.get("/tasks/7/admin-review")
    response = srv.client.get(
        "/tasks/7/admin-review",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert regular_response.status_code == 403
    assert response.status_code == 200
    review = response.get_json()
    assert "missing invariant" in review["editorial"]
    assert review["solution"] == "int main() {}\n"


def test_editorial_is_not_exposed_as_a_public_task_file(srv, tmp_path, monkeypatch):
    _write_problem(
        tmp_path,
        7,
        verificationStatus="approved",
        statement={"editorial": "statement/editorial.md"},
    )
    task_dir = tmp_path / "7"
    (task_dir / "statement").mkdir()
    (task_dir / "statement" / "editorial.md").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(tmp_path))

    meta_response = srv.client.get("/tasks/7/problem.json")
    file_response = srv.client.get("/tasks/7/statement/editorial.md")

    assert meta_response.status_code == 200
    assert "editorial" not in meta_response.get_json()["statement"]
    assert file_response.status_code == 404


def test_problem_page_only_loads_review_materials_for_admins():
    page = (REPO_ROOT / "problem.html").read_text(encoding="utf-8")

    assert "if (isAdmin)" in page
    assert "`${base}/tasks/${id}/admin-review`" in page
    assert 'block.addEventListener("toggle"' in page
    assert "Краткий разбор и где ошибка" in page
    assert "Правильное решение" in page


def test_admin_task_list_request_is_authenticated():
    page = (REPO_ROOT / "admin.html").read_text(encoding="utf-8")

    assert "headers: await adminRequestHeaders(false)" in page


def test_authenticated_task_responses_cannot_enter_a_shared_cache(srv, monkeypatch):
    monkeypatch.setattr(srv.module, "list_tasks", lambda **kwargs: [])
    token = srv.add_user("moderator", admin=True)

    response = srv.client.get(
        "/tasks/list", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "Authorization" in response.headers["Vary"]
    assert "X-Admin-Key" in response.headers["Vary"]
