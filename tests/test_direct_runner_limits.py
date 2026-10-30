def test_run_single_has_per_user_rate_limit(srv, monkeypatch):
    token = srv.add_user("student")
    monkeypatch.setattr(srv.module, "RUN_SINGLE_RATE_FREE", 2)
    monkeypatch.setattr(
        srv.module, "_run_cpp_single",
        lambda code, input_data, timeout: {"status": "OK", "output": "ready"},
    )
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(2):
        assert srv.client.post("/run-single", json={"code": "int main() {}"}, headers=headers).status_code == 200
    blocked = srv.client.post("/run-single", json={"code": "int main() {}"}, headers=headers)
    assert blocked.status_code == 429
    assert blocked.get_json()["code"] == "RATE_LIMIT_EXCEEDED"


def test_direct_exec_endpoints_reject_when_runner_is_busy(srv, monkeypatch):
    token = srv.add_user("student")

    class BusySlot:
        def acquire(self, blocking=False):
            return False

        def release(self):
            raise AssertionError("A slot that was not acquired must not be released")

    monkeypatch.setattr(srv.module, "DIRECT_EXEC_SEMAPHORE", BusySlot())
    headers = {"Authorization": f"Bearer {token}"}
    for path, payload in (
        ("/run-single", {"code": "int main() {}"}),
        ("/editor/diagnostics", {"code": "int main() {}"}),
        ("/editor/format", {"code": "int main() {}"}),
    ):
        response = srv.client.post(path, json=payload, headers=headers)
        assert response.status_code == 503
        assert response.get_json()["code"] == "RUNNER_BUSY"


def test_direct_exec_has_shared_global_rate_limit(srv, monkeypatch):
    token = srv.add_user("student")
    monkeypatch.setattr(srv.module, "DIRECT_EXEC_GLOBAL_RATE_LIMIT", 1)
    monkeypatch.setattr(
        srv.module, "_run_cpp_single",
        lambda code, input_data, timeout: {"status": "OK", "output": "ready"},
    )
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"code": "int main() {}"}
    assert srv.client.post("/run-single", json=payload, headers=headers).status_code == 200
    blocked = srv.client.post("/run-single", json=payload, headers=headers)
    assert blocked.status_code == 429
    assert blocked.get_json()["code"] == "GLOBAL_RATE_LIMIT_EXCEEDED"


def test_submit_does_not_log_user_source(srv, capsys):
    token = srv.add_user("student")
    marker = "SENSITIVE_SOURCE_MARKER"
    response = srv.client.post(
        "/submit",
        json={"task": 1, "code": f"// {marker}\nint main() {{}}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert marker not in capsys.readouterr().out
