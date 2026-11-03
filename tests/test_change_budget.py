"""A fix may touch no more lines than the reference fix does.

The counter is shared with the editor (line-diff.js), so these cases pin
down exactly what counts as a change.
"""
from line_diff import count_changed_chars, count_changed_lines


def test_one_line_replaced_counts_once():
    assert count_changed_lines("a\nb\nc", "a\nB\nc") == 1


def test_moving_a_line_counts_twice():
    assert count_changed_lines("a\nb\nc\nd", "a\nc\nb\nd") == 2


def test_whitespace_blank_lines_and_comments_are_free():
    assert count_changed_lines("int x = 1;\nreturn x;", "  int x=1;\n\n// why\n   return  x ;") == 0


def test_identical_code_is_zero():
    assert count_changed_lines("a\nb", "a\nb") == 0


def test_lines_still_count_like_before():
    assert count_changed_lines("a\nb\nc\nd\ne", "a\nX\nc\nY\nZ\ne") == 3


def test_one_character_fix_costs_one():
    assert count_changed_chars("int x = 0;\nreturn x;", "int x = 1;\nreturn x;") == 1


def test_characters_ignore_whitespace_and_comment_lines():
    assert count_changed_chars("if (a < b) f();", "  if(a<=b)   f();\n// fixed") == 1


def test_characters_are_counted_per_changed_block():
    before = "a = 0;\nkeep();\nb = 0;"
    after = "a = 10;\nkeep();\nb = 20;"
    assert count_changed_chars(before, after) == 2


def test_rewriting_costs_many_characters():
    assert count_changed_chars("x++;", "while (true) { x += 2; }") >= 14


def _post(srv, token, code):
    return srv.client.post(
        "/submit",
        json={"task": 1, "code": code, "language": "cpp"},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_submit_over_the_char_budget_is_rejected(srv, monkeypatch):
    monkeypatch.setattr(srv.module, "task_change_budget", lambda task_id, problem=None: 5)
    monkeypatch.setattr(srv.module, "task_char_budget", lambda task_id, problem=None: 3)
    monkeypatch.setattr(srv.module, "task_broken_code", lambda task_id, problem=None: "x = 0;")
    token = srv.add_user("student")
    srv.db.reset_writes()

    res = _post(srv, token, "x = 123456;")

    assert res.status_code == 400, res.get_json()
    body = res.get_json()
    assert body["code"] == "TOO_MANY_CHANGED_CHARS"
    assert body["changedChars"] == 6 and body["maxChangedChars"] == 3
    assert srv.db.writes_to("submissions") == []


def test_char_budget_adds_more_slack_to_easy_tasks(srv, monkeypatch, tmp_path):
    (tmp_path / "wa.cpp").write_text("int x = 0;\n")
    (tmp_path / "main.cpp").write_text("int x = pi[x - 1];\n")
    monkeypatch.setattr(srv.module, "task_dir", lambda task_id: str(tmp_path))
    files = {"code": "wa.cpp", "solution": "main.cpp"}
    srv.module._CHAR_BUDGET_CACHE.clear()
    easy = srv.module.task_char_budget(901, {"difficulty": "easy", "files": files})
    srv.module._CHAR_BUDGET_CACHE.clear()
    hard = srv.module.task_char_budget(901, {"difficulty": "hard", "files": files})
    assert easy == 7 + 10 and hard == 7 + 5
    assert srv.module.task_char_budget(901, {"maxChangedChars": 4, "files": files}) == 4


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
