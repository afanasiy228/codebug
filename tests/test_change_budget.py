"""A fix may touch no more lines than the reference fix does.

The counter is shared with the editor (line-diff.js), so these cases pin
down exactly what counts as a change.
"""
from line_diff import count_changed_lines


def test_one_line_replaced_counts_once():
    assert count_changed_lines("a\nb\nc", "a\nB\nc") == 1


def test_moving_a_line_counts_twice():
    assert count_changed_lines("a\nb\nc\nd", "a\nc\nb\nd") == 2


def test_whitespace_blank_lines_and_comments_are_free():
    assert count_changed_lines("int x = 1;\nreturn x;", "  int x=1;\n\n// why\n   return  x ;") == 0


def test_identical_code_is_zero():
    assert count_changed_lines("a\nb", "a\nb") == 0


def _post(srv, token, code):
    return srv.client.post(
        "/submit",
        json={"task": 1, "code": code, "language": "cpp"},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_submit_over_the_budget_is_rejected_and_not_queued(srv, monkeypatch):
    monkeypatch.setattr(srv.module, "task_change_budget", lambda task_id, problem=None: 1)
    monkeypatch.setattr(srv.module, "task_broken_code", lambda task_id, problem=None: "a\nb\nc")
    token = srv.add_user("student")
    srv.db.reset_writes()

    res = _post(srv, token, "x\ny\nz")

    assert res.status_code == 400, res.get_json()
    body = res.get_json()
    assert body["code"] == "TOO_MANY_CHANGES"
    assert body["changedLines"] == 3 and body["maxChangedLines"] == 1
    assert srv.db.writes_to("submissions") == []
    assert len(srv.module.SUBMIT_QUEUE) + len(srv.module.SUBMIT_QUEUE_PRO) == 0


def test_submit_within_the_budget_is_queued(srv, monkeypatch):
    monkeypatch.setattr(srv.module, "task_change_budget", lambda task_id, problem=None: 1)
    monkeypatch.setattr(srv.module, "task_broken_code", lambda task_id, problem=None: "a\nb\nc")
    token = srv.add_user("student")

    res = _post(srv, token, "a\nB\nc")

    assert res.status_code == 200, res.get_json()
    assert res.get_json()["status"] == "QUEUE"
