"""Keep secrets out of Git and backend files out of the Pages build."""
import json
import os
import re
import subprocess

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Filenames that must never be tracked, whatever their content.
FORBIDDEN_NAME = re.compile(
    r"(^|/)\.env(\..+)?$"
    r"|\.pem$"
    r"|\.key$"
    r"|(^|/)id_rsa"
    r"|serviceAccountKey\.json$"
    r"|service-account.*\.json$"
    r"|firebasebackup.*\.json$"
    r"|cleanup_report\.json$"
    r"|(^|/)\.DS_Store$",
    re.IGNORECASE,
)

# Top-level keys that identify a Realtime Database export of real user data.
DUMP_KEYS = {"emailToLogin", "userAuthMap", "admins", "users"}


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def test_no_secret_or_dump_filenames_are_tracked():
    offenders = [p for p in tracked_files() if FORBIDDEN_NAME.search(p)]
    assert offenders == [], (
        "These files must not be tracked in the public repository: "
        f"{offenders}"
    )


def test_no_tracked_json_is_a_user_database_dump():
    """Catch a dump committed under an unexpected name."""
    offenders = []
    for rel in tracked_files():
        if not rel.endswith(".json"):
            continue
        full = os.path.join(REPO_ROOT, rel)
        try:
            if os.path.getsize(full) > 20 * 1024 * 1024:
                continue
            with open(full, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if isinstance(data, dict) and len(DUMP_KEYS & set(data)) >= 2:
            offenders.append(rel)
    assert offenders == [], f"Tracked file(s) look like a user database export: {offenders}"


def test_no_tracked_file_contains_a_private_key_header():
    # Assembled at runtime so this file does not match its own detector.
    begin = b"-----" + b"BEGIN"
    key_tail = b"PRIVATE" + b" KEY" + b"-----"
    offenders = []
    for rel in tracked_files():
        full = os.path.join(REPO_ROOT, rel)
        try:
            if os.path.getsize(full) > 5 * 1024 * 1024:
                continue
            with open(full, "rb") as fh:
                blob = fh.read()
        except OSError:
            continue
        if begin in blob and key_tail in blob:
            offenders.append(rel)
    assert offenders == [], f"Private key material is tracked in: {offenders}"


@pytest.mark.parametrize(
    "pattern",
    [".env", "*.pem", "*.key", "serviceAccountKey.json", "firebasebackup*.json", "cleanup_report.json"],
)
def test_gitignore_covers_secret_patterns(pattern):
    with open(os.path.join(REPO_ROOT, ".gitignore"), encoding="utf-8") as fh:
        lines = {line.strip() for line in fh}
    assert pattern in lines, f".gitignore is missing the {pattern!r} pattern"


def test_pages_excludes_backend_and_operational_files():
    with open(os.path.join(REPO_ROOT, "_config.yml"), encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    excluded = {line.strip()[2:].strip() for line in lines[lines.index("exclude:") + 1:] if line.startswith("  - ")}
    required = {
        "server.py", "judge.py", "read_api.py", "sandbox", "runner", "docker",
        "scripts", "tests", "e2e", "firebase.database.rules.json", "output",
    }
    assert required <= excluded
