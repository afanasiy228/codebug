from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTHENTICATED_PAGES = (
    "index.html",
    "auth.html",
    "profile.html",
    "train.html",
    "problem.html",
    "submissions.html",
    "friends.html",
    "rating.html",
    "contests.html",
    "contest.html",
    "donate.html",
    "faq.html",
)


def test_authenticated_pages_load_firebase_auth_before_auth_helpers():
    for filename in AUTHENTICATED_PAGES:
        html = (ROOT / filename).read_text(encoding="utf-8")
        auth_sdk = html.find("firebase-auth-compat.js")
        auth_helpers = html.find('src="auth.js')

        assert auth_sdk >= 0, f"{filename} does not load Firebase Auth"
        assert auth_helpers >= 0, f"{filename} does not load auth.js"
        assert auth_sdk < auth_helpers, f"{filename} loads Firebase Auth too late"
