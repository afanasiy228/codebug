def test_solved_task_updates_private_and_public_stats(srv, monkeypatch):
    srv.add_user("student")
    monkeypatch.setattr(srv.module, "_load_task_difficulties", lambda: {})
    srv.db.data["users"]["student"]["stats"] = {
        "cnt": 1,
        "exp": 12,
        "rating": 7,
        "solved": {"1": True},
    }

    trace = srv.module._mark_task_solved_for_user("student", "2")

    assert trace["ok"] is True
    assert srv.db.data["users"]["student"]["stats"]["cnt"] == 2
    assert srv.db.data["users"]["student"]["stats"]["exp"] == 24
    assert srv.db.data["publicProfiles"]["student"]["stats"] == {
        "cnt": 2,
        "exp": 24,
        "rating": 7,
    }
    assert srv.db.data["ratingLeaderboard"]["student"]["cnt"] == 2
    assert srv.db.data["ratingLeaderboard"]["student"]["exp"] == 24
    assert srv.db.data["ratingLeaderboard"]["student"]["rating"] == 7


def test_repeated_solution_keeps_public_stats_consistent(srv, monkeypatch):
    srv.add_user("student")
    monkeypatch.setattr(srv.module, "_load_task_difficulties", lambda: {})
    srv.db.data["users"]["student"]["stats"] = {
        "cnt": 1,
        "exp": 12,
        "solved": {"1": True},
    }

    trace = srv.module._mark_task_solved_for_user("student", "1")

    assert trace["alreadySolved"] is True
    assert srv.db.data["publicProfiles"]["student"]["stats"]["cnt"] == 1
    assert srv.db.data["ratingLeaderboard"]["student"]["exp"] == 12
