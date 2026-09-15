import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_training_rank_progress_uses_the_real_rank_thresholds():
    training_page = (REPO_ROOT / "train.html").read_text(encoding="utf-8")
    rating_page = (REPO_ROOT / "rating.html").read_text(encoding="utf-8")
    match = re.search(r"const LEVEL_STEPS = \[([^]]+)]", training_page)

    assert match is not None
    training_steps = [int(value.strip()) for value in match.group(1).split(",")]
    rating_steps = [int(value) for value in re.findall(r"minExp:\s*(\d+)", rating_page)]
    assert training_steps == rating_steps[1:]
    assert "До следующего ранга" in training_page
    assert 'id="levelValue">0 / 10 опыта' in training_page
    assert re.search(r"\.level-head\s*\{[^}]*white-space:\s*nowrap", training_page, re.S)


def test_rating_guide_only_keeps_the_rank_scale_heading():
    rating_page = (REPO_ROOT / "rating.html").read_text(encoding="utf-8")

    assert "РАНГИ И ЦВЕТ НИКА" in rating_page
    assert "Как получить опыт" not in rating_page
    assert "Решай задачи и занимай призовые места" not in rating_page
    assert "grid-template-columns: repeat(10, minmax(112px, 1fr))" in rating_page


def test_rating_refreshes_only_possibly_stale_subscription_mirrors():
    rating_page = (REPO_ROOT / "rating.html").read_text(encoding="utf-8")

    assert "subscriptionMirrorMayBeStale" in rating_page
    assert "/profile-lite" in rating_page
    assert "await Promise.all(arr.map(refreshStaleSubscriptionMirror))" in rating_page


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
