"""Regression tests for server-only admin subscription mutations."""


def _admin_headers(srv):
    token = srv.add_user("admin", admin=True)
    return {"Authorization": f"Bearer {token}"}


def test_admin_grant_is_server_backed_and_mirrored(srv):
    headers = _admin_headers(srv)
    srv.add_user("member")

    res = srv.client.post(
        "/admin/subscriptions/update",
        json={"login": "member", "tier": "pro_plus", "action": "add_days", "days": 30},
        headers=headers,
    )

    assert res.status_code == 200
    stored = srv.db.data["users"]["member"]["subscription"]
    assert stored["source"] == "admin"
    assert stored["tier"] == "pro_plus"
    assert stored["status"] == "active"
    assert stored["features"]["earlyAccess"] is True
    assert srv.db.data["publicProfiles"]["member"]["subscription"]["tier"] == "pro_plus"
    assert srv.db.data["ratingLeaderboard"]["member"]["subscription"]["tier"] == "pro_plus"


def test_admin_can_disable_subscription(srv):
    headers = _admin_headers(srv)
    srv.add_user("member")
    srv.db.data["users"]["member"]["subscription"] = {
        "tier": "pro", "status": "active", "expiresAt": 4102444800000,
        "source": "payment",
    }

    res = srv.client.post(
        "/admin/subscriptions/update",
        json={"login": "member", "tier": "pro", "action": "disable"},
        headers=headers,
    )

    assert res.status_code == 200
    stored = srv.db.data["users"]["member"]["subscription"]
    assert stored["status"] == "disabled"
    assert stored["expiresAt"] == 0
    assert stored["source"] == "admin"


def test_subscription_request_uses_server_side_login(srv):
    headers = _admin_headers(srv)
    srv.add_user("buyer")
    srv.add_user("victim")
    srv.db.data.setdefault("subscriptions", {}).setdefault("requests", {})["req-1"] = {
        "login": "buyer", "tier": "pro", "status": "pending_payment",
    }

    res = srv.client.post(
        "/admin/subscriptions/update",
        json={
            "requestId": "req-1", "resolution": "approve",
            "login": "victim", "tier": "pro_plus",
        },
        headers=headers,
    )

    assert res.status_code == 200
    assert "subscription" in srv.db.data["users"]["buyer"]
    assert "subscription" not in srv.db.data["users"]["victim"]
    request_value = srv.db.data["subscriptions"]["requests"]["req-1"]
    assert request_value["status"] == "approved"
    assert request_value["resolvedBy"] == "server_admin"


def test_admin_subscription_rejects_invalid_values(srv):
    headers = _admin_headers(srv)
    srv.add_user("member")

    invalid = [
        {"login": "../member", "tier": "pro", "action": "activate"},
        {"login": "member", "tier": "free", "action": "activate"},
        {"login": "member", "tier": "pro", "action": "add_days", "days": 0},
        {"login": "member", "tier": "pro", "action": "add_days", "days": 3651},
    ]
    for body in invalid:
        res = srv.client.post("/admin/subscriptions/update", json=body, headers=headers)
        assert res.status_code == 400, (body, res.status_code, res.get_json())
