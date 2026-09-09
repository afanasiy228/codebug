def test_training_stats_returns_private_progress_for_owner(srv):
    srv.add_user("student")
    srv.db.data["users"]["student"]["stats"] = {
        "cnt": 2,
        "exp": 24,
        "rating": 8,
        "solved": {"1": True, "2": True},
    }

    token = "token-student"
    response = srv.client.get(
        "/users/student/training-stats",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.get_json()["stats"] == {
        "cnt": 2,
        "exp": 24,
        "rating": 8,
        "solved": {"1": True, "2": True},
    }


def test_training_stats_cannot_read_another_user(srv):
    token = srv.add_user("student")
    srv.add_user("other")

    response = srv.client.get(
        "/users/other/training-stats",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
