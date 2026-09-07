"""Regression tests for the API hardening pass: H4, H6, M1, M2, M4, L3, L5."""
import pytest


# --- H6: /users/<login>/profile-lite ---------------------------------------

@pytest.mark.parametrize("bad_login", [
    "a/b",
    "../../admins/attacker",
    "publicProfiles/x",
    "x" * 200,
    "ab",              # shorter than the 3-char minimum
    "has space",
    "has.dot",
])
def test_profile_lite_rejects_invalid_logins(srv, bad_login):
    srv.db.reset_writes()
    res = srv.client.get(f"/users/{bad_login}/profile-lite")
    # 400 from the validator, or 404 because a login containing "/" no longer
    # matches the route at all (the converter is <login>, not <path:login>).
    assert res.status_code in (400, 404), (bad_login, res.status_code, res.get_json())
    assert srv.db.writes == [], f"unauthenticated GET wrote to the database: {srv.db.writes}"


def test_profile_lite_accepts_a_valid_login(srv):
    srv.add_user("student")
    srv.db.data["users"]["student"].update({
        "login": "student", "stats": {"cnt": 1, "exp": 2, "rating": 3},
    })
    res = srv.client.get("/users/student/profile-lite")
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["login"] == "student"


def test_profile_lite_does_not_write_on_an_unauthenticated_read(srv):
    """It used to call _normalize_subscription(write_back=True) on a public GET."""
    srv.add_user("student")
    srv.db.data["users"]["student"].update({
        "login": "student",
        "subscription": {"tier": "pro", "status": "active", "expiresAt": 1},  # expired
    })
    srv.db.reset_writes()

    res = srv.client.get("/users/student/profile-lite")
    assert res.status_code == 200
    assert srv.db.writes == [], f"public read triggered writes: {srv.db.writes}"


# --- M2: /profile/extended-stats/<login> -----------------------------------

def test_extended_stats_rejects_reading_another_user(srv):
    token = srv.add_user("nosy")
    srv.db.data["users"]["nosy"]["subscription"] = {
        "tier": "pro_plus", "status": "active",
        "expiresAt": 4102444800000, "source": "payment",
    }
    srv.add_user("victim")

    res = srv.client.get(
        "/profile/extended-stats/victim",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403, res.get_json()


def test_extended_stats_allows_reading_your_own(srv):
    token = srv.add_user("owner")
    srv.db.data["users"]["owner"]["subscription"] = {
        "tier": "pro_plus", "status": "active",
        "expiresAt": 4102444800000, "source": "payment",
    }
    res = srv.client.get(
        "/profile/extended-stats/owner",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.get_json()


# --- M1: proxy header handling ---------------------------------------------

def test_request_ip_ignores_a_spoofed_forwarded_for_entry(srv):
    """Only the hop the proxy appended is trustworthy; the client controls the rest."""
    with srv.module.app.test_request_context(
        "/", headers={"X-Forwarded-For": "1.2.3.4, 9.9.9.9, 203.0.113.7"}
    ):
        ip = srv.module._request_ip()
    assert ip == "203.0.113.7", ip
    assert ip != "1.2.3.4", "the client-supplied first entry is still trusted"


def test_request_ip_falls_back_to_remote_addr(srv):
    with srv.module.app.test_request_context("/"):
        assert srv.module._request_ip()


# --- H4: request size limits ------------------------------------------------

def test_max_content_length_is_configured(srv):
    limit = srv.module.app.config.get("MAX_CONTENT_LENGTH")
    assert limit, "MAX_CONTENT_LENGTH is unset - request bodies are unbounded"
    assert limit <= 32 * 1024 * 1024


def test_oversized_body_is_rejected_with_413(srv):
    token = srv.add_user("student")
    huge = "x" * (srv.module.app.config["MAX_CONTENT_LENGTH"] + 1024)
    res = srv.client.post(
        "/submit",
        json={"task": 1, "code": huge},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 413, res.status_code
    assert res.get_json()["code"] == "PAYLOAD_TOO_LARGE"


# --- L5: destructive admin endpoint needs a confirmation --------------------

def test_reset_foi_requires_a_confirmation_token(srv, monkeypatch):
    monkeypatch.setattr(srv.module, "ADMIN_API_KEY", "admin-key")
    res = srv.client.post(
        "/admin/contests/reset-foi",
        json={},
        headers={"X-Admin-Key": "admin-key"},
    )
    assert res.status_code == 400, res.get_json()
    assert res.get_json()["code"] == "CONFIRMATION_REQUIRED"


def test_reset_foi_proceeds_with_the_confirmation_token(srv, monkeypatch):
    monkeypatch.setattr(srv.module, "ADMIN_API_KEY", "admin-key")
    res = srv.client.post(
        "/admin/contests/reset-foi",
        json={"confirm": "RESET_ALL_CONTESTS"},
        headers={"X-Admin-Key": "admin-key"},
    )
    assert res.status_code == 200, res.get_json()


# --- M4: rate limiting ------------------------------------------------------

def test_captcha_endpoint_is_rate_limited(srv):
    codes = set()
    for _ in range(40):
        codes.add(srv.client.post("/auth/verify-captcha", json={"token": "x"}).status_code)
    assert 429 in codes, f"no rate limiting on /auth/verify-captcha (saw {codes})"


def test_contest_register_is_rate_limited(srv):
    token = srv.add_user("spammer")
    codes = set()
    for _ in range(60):
        codes.add(srv.client.post(
            "/contest/register", json={"contestId": "c1"},
            headers={"Authorization": f"Bearer {token}"},
        ).status_code)
    assert 429 in codes, f"no rate limiting on /contest/register (saw {codes})"


# --- L3: cover URL host allowlist ------------------------------------------

@pytest.mark.parametrize("bad_url", [
    "https://evil.example/x.png",
    "http://attacker.test/track.gif",
    "javascript:alert(1)",
])
def test_set_cover_rejects_untrusted_hosts(srv, bad_url):
    token = srv.add_user("student")
    # A custom cover is a PRO feature, so the PRO gate would otherwise answer first.
    srv.db.data["users"]["student"]["subscription"] = {
        "tier": "pro", "status": "active",
        "expiresAt": 4102444800000, "source": "payment",
    }
    res = srv.client.post(
        "/profile/set-cover",
        json={"coverUrl": bad_url},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400, (bad_url, res.get_json())


@pytest.mark.parametrize("good_url", [
    "https://res.cloudinary.com/dez5af9sr/image/upload/v1/cover.png",
    "https://codebug.online/assets/cover.png",
    "/logo.png",
])
def test_set_cover_accepts_allowed_hosts(srv, good_url):
    assert srv.module._is_allowed_cover_url(good_url) is True


@pytest.mark.parametrize("bad_url", [
    "https://evil.example/x.png",
    "http://res.cloudinary.com/x.png",      # plain http
    "//evil.example/x.png",                 # protocol-relative
    "javascript:alert(1)",
    "https://res.cloudinary.com.evil.com/x.png",
])
def test_cover_url_allowlist_rejects(srv, bad_url):
    assert srv.module._is_allowed_cover_url(bad_url) is False
