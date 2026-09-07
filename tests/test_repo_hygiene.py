"""Regression tests for C3/M12: no secrets or database dumps may be tracked in git.

The repository root is the GitHub Pages document root for codebug.online, so every
tracked file at the root is published on the live site. A production database dump
was committed here once (cleanup_report.json) and a second one lived in history
(firebasebackup.json); these tests make that class of mistake fail loudly.
"""
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
        "These files must not be tracked - the repo root is the published web root: "
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
        if b"-----BEGIN" in blob and b"PRIVATE KEY-----" in blob:
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
