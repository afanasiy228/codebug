"""Regression tests for C1: /submit must derive identity from the verified ID token only.

Before the fix, server.py took `login` straight from the request body and treated the
Authorization header as optional, so anyone could submit as anyone (or as nobody).
"""


def _payload(user="victim", task=1, code="int main(){}"):
    return {"task": task, "code": code, "user": user, "language": "cpp"}


def test_submit_without_token_is_rejected(srv):
    """No Authorization header must be 401 - not an accepted submission."""
    srv.add_user("victim")
    srv.db.reset_writes()

    res = srv.client.post("/submit", json=_payload(user="victim"))

    assert res.status_code == 401, res.get_json()
    assert res.get_json()["code"] == "AUTH_REQUIRED"
    # Nothing may be persisted for an unauthenticated caller.
    assert srv.db.writes_to("submissions") == []
    assert len(srv.module.SUBMIT_QUEUE) == 0
    assert len(srv.module.SUBMIT_QUEUE_PRO) == 0


def test_submit_cannot_impersonate_another_user(srv):
    """A valid token for A plus "user": "B" must be attributed to A, never to B."""
    token_a = srv.add_user("attacker")
    srv.add_user("victim")
    srv.db.reset_writes()

    res = srv.client.post(
        "/submit",
        json=_payload(user="victim"),
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert res.status_code == 200, res.get_json()
    queued = list(srv.module.SUBMIT_QUEUE) + list(srv.module.SUBMIT_QUEUE_PRO)
    assert len(queued) == 1
    assert queued[0]["login"] == "attacker"

    submission_writes = srv.db.writes_to("submissions")
    assert submission_writes, "submission should have been recorded"
    assert all(w[2].get("login") == "attacker" for w in submission_writes if isinstance(w[2], dict))


def test_submit_with_forged_token_is_rejected(srv):
    """An unverifiable token must 401, never silently fall back to the payload login."""
    srv.add_user("victim")
    srv.db.reset_writes()

    res = srv.client.post(
        "/submit",
        json=_payload(user="victim"),
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert res.status_code == 401, res.get_json()
    assert res.get_json()["code"] == "INVALID_TOKEN"
    assert srv.db.writes_to("submissions") == []
    assert len(srv.module.SUBMIT_QUEUE) == 0


def test_submit_succeeds_for_authenticated_owner(srv):
    """The normal path keeps working: valid token, own login, queued under that login."""
    token = srv.add_user("student")
    srv.db.reset_writes()

    res = srv.client.post(
        "/submit",
        json=_payload(user="student"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["status"] == "QUEUE"
    assert body["submissionId"]
    queued = list(srv.module.SUBMIT_QUEUE) + list(srv.module.SUBMIT_QUEUE_PRO)
    assert queued[0]["login"] == "student"


def test_submit_works_without_user_field_in_body(srv):
    """The body `user` field is ignored for identity, so omitting it must still work."""
    token = srv.add_user("student")

    res = srv.client.post(
        "/submit",
        json={"task": 1, "code": "int main(){}", "language": "cpp"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200, res.get_json()
    queued = list(srv.module.SUBMIT_QUEUE) + list(srv.module.SUBMIT_QUEUE_PRO)
    assert queued[0]["login"] == "student"
