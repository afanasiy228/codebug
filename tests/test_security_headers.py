"""Regression tests for H5: the API must send security headers."""
import pytest


def _headers(srv, path="/ping", **kw):
    return srv.client.get(path, **kw).headers


def test_nosniff_is_set(srv):
    assert _headers(srv)["X-Content-Type-Options"] == "nosniff"


def test_referrer_policy_is_set(srv):
    assert _headers(srv)["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_framing_is_denied(srv):
    h = _headers(srv)
    assert h["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"]


def test_permissions_policy_is_set(srv):
    value = _headers(srv)["Permissions-Policy"]
    for feature in ("camera=()", "microphone=()", "geolocation=()"):
        assert feature in value


def test_hsts_is_sent_only_over_https(srv):
    assert "Strict-Transport-Security" not in _headers(srv)
    over_tls = _headers(srv, headers={"X-Forwarded-Proto": "https"})
    assert "max-age=31536000" in over_tls["Strict-Transport-Security"]


def test_authenticated_responses_are_not_cacheable(srv):
    token = srv.add_user("student")
    res = srv.client.get(
        "/payments/subscription-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.headers["Cache-Control"] == "private, no-store"


def test_error_responses_are_not_cacheable(srv):
    res = srv.client.get("/payments/subscription-status")
    assert res.status_code == 401
    assert res.headers["Cache-Control"] == "private, no-store"


def test_public_endpoints_keep_their_own_caching(srv):
    """profile-lite is public and deliberately cacheable; do not clobber it."""
    srv.add_user("student")
    srv.db.data["users"]["student"].update({"login": "student", "stats": {}})
    res = srv.client.get("/users/student/profile-lite")
    assert res.status_code == 200
    assert "no-store" not in res.headers.get("Cache-Control", "")


def test_no_stack_trace_leaks_in_an_error_response(srv, monkeypatch):
    """Production must return an opaque 500, never the exception text."""
    def boom(*a, **k):
        raise RuntimeError("internal detail that must not leak")

    monkeypatch.setattr(srv.module, "_get_user_subscription", boom)
    # Reproduce production error handling: TESTING re-raises, real deployments do not.
    monkeypatch.setitem(srv.module.app.config, "TESTING", False)
    monkeypatch.setitem(srv.module.app.config, "PROPAGATE_EXCEPTIONS", False)
    monkeypatch.setattr(srv.module.app, "debug", False, raising=False)

    token = srv.add_user("student")
    res = srv.client.get(
        "/payments/subscription-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = res.get_data(as_text=True)
    assert res.status_code == 500
    assert "Traceback" not in body
    assert "internal detail" not in body
    assert "RuntimeError" not in body


def test_debug_mode_is_off(srv):
    assert srv.module.app.debug is False
    assert srv.module.app.config.get("DEBUG") is not True
