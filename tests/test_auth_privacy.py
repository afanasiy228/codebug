"""Authentication privacy and server-side profile finalization regressions."""


def test_username_login_returns_custom_token_without_email(srv, monkeypatch):
    srv.add_user("student", email="student@example.test")
    monkeypatch.setattr(srv.module, "PUBLIC_FIREBASE_WEB_API_KEY", "public-key")
    monkeypatch.setattr(
        srv.module,
        "_firebase_identity_request",
        lambda endpoint, payload: ({"localId": "uid-student"}, None),
    )

    res = srv.client.post(
        "/auth/login",
        json={"identity": "student", "password": "correct-password"},
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert payload["customToken"] == "custom-uid-student"
    assert payload["login"] == "student"
    assert "email" not in payload


def test_username_login_uses_generic_error_for_unknown_account(srv):
    res = srv.client.post(
        "/auth/login",
        json={"identity": "missing", "password": "wrong-password"},
    )
    assert res.status_code == 401
    assert res.get_json()["code"] == "INVALID_CREDENTIALS"


def test_password_reset_does_not_enumerate_accounts(srv, monkeypatch):
    called = []
    monkeypatch.setattr(
        srv.module,
        "_firebase_identity_request",
        lambda endpoint, payload: (called.append((endpoint, payload)) or ({}, None)),
    )
    missing = srv.client.post("/auth/password-reset", json={"identity": "missing"})
    assert missing.status_code == 200
    assert missing.get_json() == {"ok": True}
    assert called == []


def test_verified_user_finalizes_profile_only_for_own_uid(srv):
    srv.tokens["token-new"] = {
        "uid": "uid-new_user",
        "email": "new.user@example.test",
        "email_verified": True,
    }
    res = srv.client.post(
        "/auth/finalize-profile",
        json={"login": "new_user"},
        headers={"Authorization": "Bearer token-new"},
    )

    assert res.status_code == 200, res.get_json()
    assert res.get_json()["login"] == "new_user"
    user = srv.db.data["users"]["new_user"]
    assert user["id"] == "uid-new_user"
    assert user["email"] == "new.user@example.test"
    assert user["stats"] == {"exp": 0, "cnt": 0, "rating": 0, "solved": {}}
    assert srv.db.data["userAuthMap"]["uid-new_user"] == "new_user"
    assert srv.db.data["emailToLogin"]["new,user@example,test"] == "new_user"


def test_unverified_user_cannot_finalize_profile(srv):
    srv.tokens["token-unverified"] = {
        "uid": "uid-new_user",
        "email": "new.user@example.test",
        "email_verified": False,
    }
    res = srv.client.post(
        "/auth/finalize-profile",
        json={"login": "new_user"},
        headers={"Authorization": "Bearer token-unverified"},
    )
    assert res.status_code == 403
    assert "new_user" not in srv.db.data.get("users", {})


def test_finalize_profile_cannot_take_an_existing_login(srv):
    srv.add_user("victim")
    srv.tokens["token-attacker"] = {
        "uid": "uid-attacker",
        "email": "attacker@example.test",
        "email_verified": True,
    }
    res = srv.client.post(
        "/auth/finalize-profile",
        json={"login": "victim"},
        headers={"Authorization": "Bearer token-attacker"},
    )
    assert res.status_code == 409
    assert srv.db.data["users"]["victim"]["id"] == "uid-victim"


def test_captcha_uses_trusted_proxy_hop(srv, monkeypatch):
    seen = {}

    def verify(_token, remote_ip=None):
        seen["remote_ip"] = remote_ip
        return True, None

    monkeypatch.setattr(srv.module, "_verify_captcha_token", verify)
    res = srv.client.post(
        "/auth/verify-captcha",
        json={"token": "captcha"},
        headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.7"},
    )
    assert res.status_code == 200
    assert seen["remote_ip"] == "203.0.113.7"
