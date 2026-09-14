#!/usr/bin/env python3
"""Configure the CodeBug Telegram webhook and command menu."""

from pathlib import Path
import os
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from telegram_admin_bot import TelegramBotConfig, configure_telegram_webhook  # noqa: E402


def main():
    config = TelegramBotConfig.from_env()
    public_api = os.getenv("PUBLIC_API_BASE", "https://codebug.onrender.com").rstrip("/")
    try:
        result = configure_telegram_webhook(config, public_api)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print(f"Configured @{result['username']} webhook: {result['webhook_url']}")
    print("Token was read from the environment and was not printed.")


if __name__ == "__main__":
    main()
