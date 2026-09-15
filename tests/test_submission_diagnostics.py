"""Private compiler-diagnostic storage and access regressions."""


def test_compilation_diagnostics_remove_host_paths_and_judge_footer(srv):
    details = srv.module._extract_compilation_diagnostics(
        "Compilation Error\n"
        "/tmp/codebug_submit_secret/sol.cpp:3:5: error: expected ';'\n"
        "Final verdict: CE\n"
    )

    assert details == "sol.cpp:3:5: error: expected ';'"
    assert "/tmp/" not in details
    assert "Final verdict" not in details


def test_submission_owner_can_read_compilation_diagnostics(srv):
    token = srv.add_user("student")
    srv.db.data.setdefault("submissions", {}).setdefault("global", {})["-ce1"] = {
        "login": "student",
        "task": 1,
        "verdict": "CE",
    }
    srv.db.data.setdefault("submissionDiagnostics", {})["-ce1"] = {
        "login": "student",
        "task": 1,
        "verdict": "CE",
        "details": "sol.cpp:2:1: error: expected declaration",
    }

    res = srv.client.get(
        "/submissions/-ce1/diagnostics",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert res.get_json() == {
        "submissionId": "-ce1",
        "verdict": "CE",
        "details": "sol.cpp:2:1: error: expected declaration",
    }
    assert res.headers["Cache-Control"] == "private, no-store"


def test_other_user_cannot_read_compilation_diagnostics(srv):
    srv.add_user("student")
    attacker_token = srv.add_user("attacker")
    srv.db.data.setdefault("submissions", {}).setdefault("global", {})["-ce1"] = {
        "login": "student",
        "task": 1,
        "verdict": "CE",
    }
    srv.db.data.setdefault("submissionDiagnostics", {})["-ce1"] = {
        "login": "student",
        "details": "private compiler output",
    }

    res = srv.client.get(
        "/submissions/-ce1/diagnostics",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )

    assert res.status_code == 403
    assert "details" not in res.get_json()


def test_admin_can_read_compilation_diagnostics(srv):
    srv.add_user("student")
    admin_token = srv.add_user("admin", admin=True)
    srv.db.data.setdefault("submissions", {}).setdefault("global", {})["-ce1"] = {
        "login": "student",
        "task": 1,
        "verdict": "CE",
    }
    srv.db.data.setdefault("submissionDiagnostics", {})["-ce1"] = {
        "login": "student",
        "details": "compiler output",
    }

    res = srv.client.get(
        "/submissions/-ce1/diagnostics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    assert res.get_json()["details"] == "compiler output"


def test_compilation_diagnostics_require_authentication(srv):
    res = srv.client.get("/submissions/-ce1/diagnostics")
    assert res.status_code == 401
