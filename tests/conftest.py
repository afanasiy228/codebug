"""Shared fixtures for CodeBug security regression tests.

Everything here runs against an in-memory fake of Firebase Realtime Database and a
fake Firebase ID-token verifier. No production credentials, no network, no Docker.
"""
import os
import sys
import types
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Keep the module import side effects inert: no real Firebase, no git sync, no judge.
os.environ.setdefault("FIREBASE_DB_URL", "")
os.environ.setdefault("ADMIN_API_KEY", "")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")
os.environ.setdefault("CODEBUG_WORK_DIR", "/tmp/codebug-test-work")


def _split(path):
    return [part for part in str(path or "").strip("/").split("/") if part]


class FakeRef:
    """Minimal stand-in for firebase_admin.db.Reference backed by a nested dict."""

    def __init__(self, store, path):
        self._store = store
        self._path = _split(path)
        self.key = self._path[-1] if self._path else None

    # -- navigation -------------------------------------------------------
    def child(self, path):
        return FakeRef(self._store, "/".join(self._path + _split(path)))

    # -- reads ------------------------------------------------------------
    def get(self):
        node = self._store.data
        for part in self._path:
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node

    # -- writes -----------------------------------------------------------
    def _parent(self, create=True):
        node = self._store.data
        for part in self._path[:-1]:
            if part not in node or not isinstance(node[part], dict):
                if not create:
                    return None
                node[part] = {}
            node = node[part]
        return node

    def set(self, value):
        self._store.writes.append(("set", "/".join(self._path), value))
        parent = self._parent()
        parent[self._path[-1]] = value
        return value

    def update(self, value):
        self._store.writes.append(("update", "/".join(self._path), value))
        parent = self._parent()
        current = parent.get(self._path[-1])
        if not isinstance(current, dict):
            current = {}
        current.update(value)
        parent[self._path[-1]] = current
        return current

    def delete(self):
        self._store.writes.append(("delete", "/".join(self._path), None))
        parent = self._parent(create=False)
        if parent is not None:
            parent.pop(self._path[-1], None)

    def push(self):
        self._store.counter += 1
        key = f"gen-{self._store.counter}"
        return FakeRef(self._store, "/".join(self._path + [key]))

    def transaction(self, fn):
        current = self.get()
        new_value = fn(current)
        if new_value is not None:
            self.set(new_value)
        return new_value


class FakeDb:
    """Namespace object mirroring the `firebase_admin.db` module surface used by server.py."""

    def __init__(self):
        self.data = {}
        self.writes = []
        self.counter = 0

    def reference(self, path="/"):
        return FakeRef(self, path)

    # convenience for assertions
    def writes_to(self, prefix):
        return [w for w in self.writes if w[1].startswith(prefix)]

    def reset_writes(self):
        self.writes.clear()


class FakeAuthError(Exception):
    pass


@pytest.fixture
def fake_db():
    return FakeDb()


@pytest.fixture
def srv(fake_db, monkeypatch):
    """Import server.py once and wire it to the in-memory fakes."""
    import server as server_module

    monkeypatch.setattr(server_module, "db", fake_db, raising=False)
    monkeypatch.setattr(server_module, "FIREBASE_READY", True, raising=False)
    monkeypatch.setattr(server_module, "init_firebase", lambda: True, raising=False)
    monkeypatch.setattr(server_module, "_ensure_firebase_ready", lambda: True, raising=False)

    # Never spawn the judge worker or the git-sync worker inside tests.
    monkeypatch.setattr(server_module, "_ensure_submit_worker", lambda: None, raising=False)
    monkeypatch.setattr(server_module, "_ensure_tasks_sync_worker", lambda: None, raising=False)
    monkeypatch.setattr(server_module, "sync_tasks_repo", lambda *a, **k: True, raising=False)

    # A single task (id 1) exists and is public.
    monkeypatch.setattr(
        server_module, "read_task_meta",
        lambda task_id: {"id": int(task_id), "title": "t"} if str(task_id) == "1" else None,
        raising=False,
    )
    monkeypatch.setattr(server_module, "_task_access_allowed", lambda *a, **k: True, raising=False)

    # Fresh rate-limit state per test so limits from one test cannot bleed into the next.
    server_module.REQUEST_RATE_STATE.clear()
    server_module.PROFILE_RUNTIME_CACHE.clear()
    server_module.SUBMIT_QUEUE.clear()
    server_module.SUBMIT_QUEUE_PRO.clear()

    # Token registry: token string -> uid. Unknown tokens raise, like the real SDK.
    tokens = {}

    def fake_verify_id_token(token, *args, **kwargs):
        if token not in tokens:
            raise FakeAuthError("invalid token")
        return {"uid": tokens[token]}

    fake_auth = types.SimpleNamespace(
        verify_id_token=fake_verify_id_token,
        list_users=lambda *a, **k: None,
        delete_user=lambda *a, **k: None,
    )
    monkeypatch.setattr(server_module, "admin_auth", fake_auth, raising=False)

    server_module.app.config["TESTING"] = True
    client = server_module.app.test_client()

    def add_user(login, uid=None, admin=False):
        uid = uid or f"uid-{login}"
        token = f"token-{login}"
        tokens[token] = uid
        fake_db.data.setdefault("userAuthMap", {})[uid] = login
        fake_db.data.setdefault("users", {})[login] = {"login": login}
        if admin:
            fake_db.data.setdefault("admins", {})[login] = True
        return token

    return types.SimpleNamespace(
        module=server_module,
        client=client,
        db=fake_db,
        add_user=add_user,
        tokens=tokens,
    )
