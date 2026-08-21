#!/usr/bin/env python3
import argparse
import json
import os
from typing import Dict, Any


def is_solved_submission(item: Dict[str, Any]) -> bool:
    item = item or {}
    verdict = str(item.get("verdict", "")).strip().upper()
    status_label = str(item.get("statusLabel", "")).strip().upper()
    status = str(item.get("status", "")).strip().upper()
    raw_verdict = str(item.get("rawVerdict", "")).strip().upper()

    if verdict == "OK" or status_label == "OK" or status == "OK" or raw_verdict == "OK":
        return True

    score = item.get("score")
    try:
        if score is not None and float(str(score).replace(",", ".")) >= 100.0:
            return True
    except Exception:
        pass

    for field in (verdict, status_label, status):
        try:
            if field and float(str(field).replace(",", ".")) >= 100.0:
                return True
        except Exception:
            continue
    return False


def xp_for_difficulty(difficulty: str) -> int:
    values = {
        "tutorial": 2,
        "easy": 4,
        "casual": 7,
        "normal": 12,
        "hard": 20,
        "insane": 30,
        "extreme": 45,
        "ultra": 60,
        "impossible": 80,
        "tourist": 110,
    }
    return values.get(str(difficulty or "").strip().lower(), 5)


def task_difficulty_for_xp(task_id: str, task_difficulties: Dict[str, str]) -> str:
    try:
        numeric_id = int(str(task_id))
    except (TypeError, ValueError):
        return task_difficulties.get(str(task_id), "")

    if 0 <= numeric_id <= 22:
        return "normal"
    if numeric_id in (23, 24):
        return "hard"
    if numeric_id in (25, 26):
        return "impossible"
    return task_difficulties.get(str(task_id), "")


def load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_task_difficulties(repo_dir: str) -> Dict[str, str]:
    difficulties: Dict[str, str] = {}
    if not repo_dir or not os.path.isdir(repo_dir):
        return difficulties
    for name in os.listdir(repo_dir):
        if not str(name).isdigit():
            continue
        problem = load_json(os.path.join(repo_dir, name, "problem.json")) or {}
        if problem:
            difficulties[str(name)] = str(problem.get("difficulty") or "")
            continue
        meta = load_json(os.path.join(repo_dir, name, "meta.json")) or {}
        difficulties[str(name)] = str(meta.get("difficulty") or "")
    return difficulties


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild users stats in Firebase backup from submissions.")
    parser.add_argument("--input", default="firebasebackup.json", help="Path to Firebase backup JSON")
    parser.add_argument("--tasks-dir", default=".tasks_repo", help="Tasks repo dir for difficulty lookup")
    args = parser.parse_args()

    path = args.input
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    users = data.get("users")
    submissions_root = data.get("submissions", {})
    submissions_global = submissions_root.get("global") if isinstance(submissions_root, dict) else {}
    if not isinstance(users, dict):
        raise SystemExit("users node is not an object")

    task_difficulties = load_task_difficulties(args.tasks_dir)
    if not task_difficulties:
        # Fallback to public tasks dir layout if present.
        task_difficulties = load_task_difficulties("tasks")

    solved_by_user: Dict[str, Dict[str, bool]] = {}
    if isinstance(submissions_global, dict):
        submissions_iter = submissions_global.values()
        submissions_scanned = len(submissions_global)
    elif isinstance(submissions_global, list):
        submissions_iter = submissions_global
        submissions_scanned = len(submissions_global)
    else:
        submissions_iter = []
        submissions_scanned = 0

    for sub in submissions_iter:
        if not isinstance(sub, dict):
            continue
        login = str(sub.get("login") or "").strip()
        if not login:
            continue
        task = str(sub.get("task") or "").strip()
        if not task or not task.isdigit():
            continue
        if not is_solved_submission(sub):
            continue
        solved_by_user.setdefault(login, {})[task] = True

    users_updated = 0
    users_with_solved = 0
    for login, udata in users.items():
        if not isinstance(udata, dict):
            continue
        solved_map = solved_by_user.get(str(login), {})
        if solved_map:
            users_with_solved += 1
        stats = udata.get("stats")
        if not isinstance(stats, dict):
            stats = {}
        stats["solved"] = solved_map
        stats["cnt"] = len(solved_map)
        try:
            contest_exp = max(0, int(stats.get("contestExp") or 0))
        except (TypeError, ValueError):
            contest_exp = 0
        stats["contestExp"] = contest_exp
        stats["exp"] = contest_exp + sum(
            xp_for_difficulty(task_difficulty_for_xp(task_id, task_difficulties))
            for task_id in solved_map
        )
        udata["stats"] = stats
        users_updated += 1

    data["users"] = users

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")

    print(f"updated={users_updated}")
    print(f"users_with_solved={users_with_solved}")
    print(f"submissions_scanned={submissions_scanned}")
    print(f"tasks_loaded={len(task_difficulties)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
