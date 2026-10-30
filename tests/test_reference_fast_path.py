import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from reference_match import matches_reference


@pytest.mark.parametrize(
    "candidate,reference,language,expected",
    [
        ("print( 1)\n", "print(1)\n", "python", True),
        ("print(1 )\n", "print(1)\n", "python", True),
        ("int main( ){ return 0; }\n", "int main(){return 0;}\n", "cpp", True),
        ("print('a b')\n", "print('ab')\n", "python", False),
        ("if True:\n  print(1)\n", "if True:\n    print(1)\n", "python", False),
        ("#define F (x) x\n", "#define F(x) x\n", "cpp", False),
        ("int x = a + +b;\n", "int x = a++b;\n", "cpp", False),
        ("/* ( x ) */\nint main(){}\n", "/* (x) */\nint main(){}\n", "cpp", False),
    ],
)
def test_reference_layout_comparison_is_conservative(candidate, reference, language, expected):
    assert matches_reference(candidate, reference, language) is expected


def test_reference_key_requires_clean_committed_task(srv, monkeypatch, tmp_path):
    repo = tmp_path / "tasks"
    task = repo / "1"
    (task / "solutions").mkdir(parents=True)
    (task / "tests").mkdir()
    (task / "solutions" / "main.cpp").write_text("int main(){return 0;}\n")
    (task / "tests" / "001").write_text("\n")
    (task / "problem.json").write_text(json.dumps({
        "id": 1, "language": "cpp", "taskType": "standard",
        "checker": {"type": "standard"},
        "files": {"solution": "solutions/main.cpp"},
    }))
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.test"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "1"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "task"], check=True)
    monkeypatch.setattr(srv.module, "TASKS_REPO_DIR", str(repo))

    candidate = "int main( ){return 0;}\n"
    assert srv.module._reference_match_key("1", candidate, "cpp") is not None
    (task / "tests" / "001").write_text("changed\n")
    assert srv.module._reference_match_key("1", candidate, "cpp") is None


def test_only_previously_judged_reference_skips_judge(srv, monkeypatch):
    srv.add_user("student")
    module = srv.module
    module._VERIFIED_REFERENCE_CACHE.clear()
    current_key = ["task-revision-1"]
    monkeypatch.setattr(module, "_reference_match_key", lambda task, code, lang: tuple(current_key))
    monkeypatch.setattr(module, "read_problem_config", lambda task: {
        "groups": [{"id": 1, "points": 100}], "scoringMode": "ioi"
    })
    monkeypatch.setattr(module, "invalidate_submissions", lambda *args: None)
    monkeypatch.setattr(module, "_append_activity", lambda *args: None)
    monkeypatch.setattr(module, "_mark_task_solved_for_user", lambda *args: {"ok": True})

    calls = []

    def fake_judge(command, **kwargs):
        calls.append(command)
        (Path(kwargs["cwd"]) / "log.txt").write_text(
            "Group 1 verdict: OK\nScore: 100\nFinal verdict: OK\n"
        )
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_judge)
    for submission_id in ("first", "second"):
        module._run_submission_job({
            "task": "1", "code": "int main( ){return 0;}",
            "login": "student", "submission_id": submission_id,
        })
        record = srv.db.data["submissions"]["global"][submission_id]
        assert record["verdict"] == "OK"
        assert record["score"] == 100
    assert len(calls) == 1

    current_key[0] = "task-revision-2"
    module._run_submission_job({
        "task": "1", "code": "int main( ){return 0;}",
        "login": "student", "submission_id": "after-edit",
    })
    assert len(calls) == 2
