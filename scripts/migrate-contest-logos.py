"""Move legacy inline logos to Cloudinary. Dry-run by default; backup before writes.

Uses the existing public upload preset and the Firebase CLI's signed-in project
account. Only /contests/<id>/logo is updated; the rest of each contest is untouched.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request


def read_json(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--project", default="codebug-47347")
    args = parser.parse_args()
    config = read_json("https://codebug.onrender.com/public-config")
    database = config["firebase"]["databaseURL"].rstrip("/")
    contests = read_json(database + "/contests.json") or {}
    legacy = {key: item["logo"] for key, item in contests.items() if isinstance(item, dict) and str(item.get("logo", "")).startswith("data:image/")}
    print(json.dumps({"mode": "apply" if args.apply else "dry-run", "logos": len(legacy), "inlineBytes": sum(len(value.encode()) for value in legacy.values())}), flush=True)
    if not args.apply or not legacy:
        return
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = root / "backups" / ("contest-logos-" + stamp + ".json")
    backup.parent.mkdir(exist_ok=True)
    backup.write_text(json.dumps(legacy))
    cloudinary = config["cloudinary"]
    for identifier, original in legacy.items():
        encoded = urllib.parse.urlencode({"file": original, "upload_preset": cloudinary["uploadPreset"], "folder": "codebug/competitionLogo"}).encode()
        endpoint = "https://api.cloudinary.com/v1_1/" + cloudinary["cloudName"] + "/image/upload"
        with urllib.request.urlopen(urllib.request.Request(endpoint, data=encoded), timeout=60) as response:
            uploaded = json.load(response)
        url = uploaded.get("secure_url")
        if not url or not url.startswith("https://res.cloudinary.com/"):
            raise RuntimeError("Cloudinary did not return a delivery URL")
        # Do not overwrite a logo edited while this migration was uploading.
        current = read_json(database + "/contests/" + urllib.parse.quote(identifier, safe="") + "/logo.json")
        if current != original:
            print("Skipped a concurrently edited logo:", identifier, flush=True)
            continue
        subprocess.run(["firebase", "database:set", "/contests/" + identifier + "/logo", "--data", json.dumps(url), "--project", args.project, "--force", "--non-interactive"], check=False)
        if read_json(database + "/contests/" + urllib.parse.quote(identifier, safe="") + "/logo.json") != url:
            raise RuntimeError("Logo migration verification failed")
        print("Migrated:", identifier, flush=True)
    print("Backup:", backup, flush=True)


if __name__ == "__main__":
    main()
