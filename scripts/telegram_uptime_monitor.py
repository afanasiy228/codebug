#!/usr/bin/env python3
"""External CodeBug uptime/SSL watcher that sends Telegram alerts.

Run this outside the main Render web service. In loop mode it reports an outage
only after consecutive failures and sends a single recovery notification.
"""

import argparse
import json
import os
from pathlib import Path
import socket
import ssl
import time
import urllib.parse
import urllib.request


def parse_ids(raw):
    result = []
    for item in str(raw or "").split(","):
        try:
            result.append(int(item.strip()))
        except ValueError:
            continue
    return result


def telegram_send(token, chat_ids, text, timeout):
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    for chat_id in chat_ids:
        payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response.read()
        except Exception as exc:
            raise RuntimeError(f"telegram_send_failed:{type(exc).__name__}") from None


def check_http(url, timeout):
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": "CodeBug-Uptime/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4096)
            ok = 200 <= response.status < 300
            if body:
                try:
                    ok = ok and json.loads(body.decode("utf-8")).get("status") == "ok"
                except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                    pass
            return ok, int((time.monotonic() - started) * 1000), f"HTTP {response.status}"
    except Exception as exc:
        return False, int((time.monotonic() - started) * 1000), type(exc).__name__


def ssl_days_left(url, timeout):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    context = ssl.create_default_context()
    with socket.create_connection((parsed.hostname, parsed.port or 443), timeout=timeout) as sock:
        with context.wrap_socket(sock, server_hostname=parsed.hostname) as wrapped:
            expires = ssl.cert_time_to_seconds(wrapped.getpeercert()["notAfter"])
    return int((expires - time.time()) / 86400)


def load_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"failures": 0, "down": False, "lastSslAlertDay": None}


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def run_check(config, state):
    ok, latency, detail = check_http(config["url"], config["timeout"])
    if ok:
        if state.get("down"):
            telegram_send(config["token"], config["chat_ids"], f"✅ CodeBug снова доступен. Ответ: {latency} мс.", config["timeout"])
        state.update({"failures": 0, "down": False})
    else:
        state["failures"] = int(state.get("failures", 0)) + 1
        if state["failures"] >= config["failure_threshold"] and not state.get("down"):
            telegram_send(config["token"], config["chat_ids"], f"🚨 CodeBug недоступен: {detail}. Ошибок подряд: {state['failures']}.", config["timeout"])
            state["down"] = True

    try:
        days = ssl_days_left(config["url"], config["timeout"])
    except Exception:
        days = None
    if days is not None and days <= config["ssl_warning_days"] and state.get("lastSslAlertDay") != days:
        telegram_send(config["token"], config["chat_ids"], f"⚠️ TLS-сертификат CodeBug истекает через {days} дн.", config["timeout"])
        state["lastSslAlertDay"] = days
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one check and exit")
    args = parser.parse_args()
    config = {
        "token": os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        "chat_ids": parse_ids(os.getenv("TELEGRAM_ALERT_CHAT_IDS")),
        "url": os.getenv("CODEBUG_HEALTH_URL", "https://codebug.onrender.com/ping").strip(),
        "timeout": max(2, int(os.getenv("UPTIME_TIMEOUT", "10"))),
        "failure_threshold": max(1, int(os.getenv("UPTIME_FAILURE_THRESHOLD", "2"))),
        "ssl_warning_days": max(1, int(os.getenv("SSL_WARNING_DAYS", "14"))),
        "interval": max(30, int(os.getenv("UPTIME_INTERVAL", "60"))),
    }
    if not config["token"] or not config["chat_ids"]:
        raise SystemExit("TELEGRAM_BOT_TOKEN and TELEGRAM_ALERT_CHAT_IDS are required")
    state_path = Path(os.getenv("UPTIME_STATE_FILE", "/tmp/codebug-uptime-state.json"))
    while True:
        state = run_check(config, load_state(state_path))
        save_state(state_path, state)
        if args.once:
            break
        time.sleep(config["interval"])


if __name__ == "__main__":
    main()
