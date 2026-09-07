"""Blanket authorization coverage across every private endpoint.

Items 2, 3, 5 and 6 of the audit checklist: no token, a forged token, acting on
another user, and a plain user reaching admin endpoints.
"""
import pytest

# (method, path, json body) for every endpoint that must require a verified token.
PRIVATE_ENDPOINTS = [
    ("POST", "/auth/finalize-profile", {"login": "someone"}),
    ("POST", "/submit", {"task": 1, "code": "x"}),
    ("POST", "/run-single", {"code": "x", "input": ""}),
    ("POST", "/editor/diagnostics", {"code": "x"}),
    ("POST", "/editor/format", {"code": "x"}),
    ("POST", "/editor/ai-complete", {"prefix": "x"}),
    ("POST", "/profile/change-login", {"login": "newname"}),
    ("POST", "/profile/set-nick-color", {"color": "#60a5fa"}),
    ("POST", "/profile/set-cover", {"coverId": "cover_1"}),
    ("POST", "/payments/platega/create", {"tier": "pro"}),
    ("GET", "/payments/subscription-status", None),
    ("GET", "/profile/extended-stats/someone", None),
    ("GET", "/recommendations", None),
    ("POST", "/contests/create", {"title": "t"}),
    ("POST", "/contest/register", {"contestId": "c1"}),
    ("POST", "/tasks/create", {"title": "t"}),
    ("POST", "/tasks/generate-tests", {"generator": "x"}),
]

ADMIN_ENDPOINTS = [
    ("POST", "/admin/subscriptions/update", {"login": "someone", "tier": "pro", "action": "activate"}),
    ("POST", "/admin/purge-users", {"confirm": "DELETE_ALL_USERS"}),
    ("POST", "/admin/rebuild-user-stats", {}),
    ("POST", "/admin/contests/reset-foi", {"confirm": "RESET_ALL_CONTESTS"}),
    ("POST", "/admin/contests/finalize", {"contestId": "c1"}),
    ("POST", "/tasks/delete", {"taskId": 1}),
    ("GET", "/tasks/1/admin-bundle", None),
]


def _call(client, method, path, body, headers=None):
    kwargs = {"headers": headers or {}}
    if body is not None:
        kwargs["json"] = body
    return client.open(path, method=method, **kwargs)


@pytest.mark.parametrize("method,path,body", PRIVATE_ENDPOINTS)
def test_private_endpoint_requires_a_token(srv, method, path, body):
    res = _call(srv.client, method, path, body)
    assert res.status_code == 401, (path, res.status_code, res.get_json())


@pytest.mark.parametrize("method,path,body", PRIVATE_ENDPOINTS)
def test_private_endpoint_rejects_a_forged_token(srv, method, path, body):
    res = _call(srv.client, method, path, body,
                headers={"Authorization": "Bearer forged.token.value"})
    assert res.status_code == 401, (path, res.status_code, res.get_json())


@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS)
def test_admin_endpoint_rejects_an_anonymous_caller(srv, method, path, body):
    res = _call(srv.client, method, path, body)
    assert res.status_code in (401, 403), (path, res.status_code, res.get_json())


@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS)
def test_admin_endpoint_rejects_a_plain_user(srv, method, path, body):
    token = srv.add_user("regular")          # deliberately not in admins/
    res = _call(srv.client, method, path, body,
                headers={"Authorization": f"Bearer {token}"})
    assert res.status_code in (401, 403), (path, res.status_code, res.get_json())
    assert "admins" not in [w[1].split("/")[0] for w in srv.db.writes], srv.db.writes


@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS)
def test_admin_endpoint_rejects_a_pro_plus_user(srv, method, path, body):
    """A paid tier is not an admin role."""
    token = srv.add_user("paying")
    srv.db.data["users"]["paying"]["subscription"] = {
        "tier": "pro_plus", "status": "active",
        "expiresAt": 4102444800000, "source": "payment",
    }
    res = _call(srv.client, method, path, body,
                headers={"Authorization": f"Bearer {token}"})
    assert res.status_code in (401, 403), (path, res.status_code, res.get_json())


# --- item 5: acting on another user ----------------------------------------

def test_change_login_only_renames_the_caller(srv):
    """The new login is taken from the body; the account renamed must be the caller's."""
    token = srv.add_user("owner")
    srv.db.data["users"]["owner"]["subscription"] = {
        "tier": "pro", "status": "active",
        "expiresAt": 4102444800000, "source": "payment",
    }
    srv.add_user("victim")
    srv.db.reset_writes()

    srv.client.post(
        "/profile/change-login",
        json={"login": "stolen", "user": "victim", "uid": "uid-victim"},
        headers={"Authorization": f"Bearer {token}"},
    )
    touched = {w[1] for w in srv.db.writes if w[1].startswith("users/victim")}
    assert touched == set(), f"another user's node was modified: {touched}"


def test_set_cover_cannot_target_another_user(srv):
    token = srv.add_user("owner")
    srv.add_user("victim")
    srv.db.reset_writes()

    srv.client.post(
        "/profile/set-cover",
        json={"coverId": "cover_2", "login": "victim", "user": "victim"},
        headers={"Authorization": f"Bearer {token}"},
    )
    touched = {w[1] for w in srv.db.writes if "victim" in w[1]}
    assert touched == set(), f"another user's cover was modified: {touched}"


def test_subscription_status_reports_only_the_caller(srv):
    token = srv.add_user("owner")
    srv.add_user("victim")
    srv.db.data["users"]["victim"]["subscription"] = {
        "tier": "pro_plus", "status": "active",
        "expiresAt": 4102444800000, "source": "payment",
    }
    res = srv.client.get(
        "/payments/subscription-status?login=victim&user=victim",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.get_json()["login"] == "owner"
