import pytest


@pytest.mark.parametrize("logo", [
    "https://res.cloudinary.com/dez5af9sr/image/upload/v1/codebug/competitionLogo/avatar.jpg",
    "data:image/png;base64,aGVsbG8=",
    "",
])
def test_create_contest_accepts_uploaded_and_legacy_logos(srv, monkeypatch, logo):
    monkeypatch.setattr(srv.module, "PUBLIC_CLOUDINARY_CLOUD_NAME", "dez5af9sr")
    token = srv.add_user("organizer", admin=True)
    response = srv.client.post("/contests/create", headers={"Authorization": f"Bearer {token}"}, json={
        "title": "CodeBug Weekly #1", "logo": logo, "tasks": [35],
        "start": 1793400000000, "end": 1793407200000, "visibility": "public",
    })
    assert response.status_code == 200
    saved = srv.db.data["contests"][response.json["id"]]
    assert saved["logo"] == logo


@pytest.mark.parametrize("logo", [
    "https://evil.example/image.jpg",
    "https://res.cloudinary.com.evil.example/dez5af9sr/image/upload/a.jpg",
    "https://res.cloudinary.com@evil.example/dez5af9sr/image/upload/a.jpg",
    "http://res.cloudinary.com/dez5af9sr/image/upload/a.jpg",
    "https://res.cloudinary.com/other-cloud/image/upload/a.jpg",
    "https://res.cloudinary.com/dez5af9sr/raw/upload/a.html",
    "https://res.cloudinary.com/dez5af9sr/image/upload/",
    "javascript:alert(1)",
    "data:image/svg+xml;base64,aGVsbG8=",
])
def test_create_contest_rejects_untrusted_logos_without_writing(srv, monkeypatch, logo):
    monkeypatch.setattr(srv.module, "PUBLIC_CLOUDINARY_CLOUD_NAME", "dez5af9sr")
    token = srv.add_user("organizer", admin=True)
    response = srv.client.post("/contests/create", headers={"Authorization": f"Bearer {token}"}, json={
        "title": "CodeBug Weekly #1", "logo": logo, "tasks": [35],
        "start": 1793400000000, "end": 1793407200000, "visibility": "public",
    })
    assert response.status_code == 400
    assert response.json["error"] == "invalid_logo"
    assert not srv.db.data.get("contests")
