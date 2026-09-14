#!/usr/bin/env python3
"""Configure the CodeBug Telegram webhook and command menu."""

from pathlib import Path
import os
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from telegram_admin_bot import TelegramAPI, TelegramBotConfig  # noqa: E402


COMMANDS = [
    {"command": "status", "description": "Состояние CodeBug"},
    {"command": "queue", "description": "Очередь judge"},
    {"command": "errors", "description": "Последние ошибки"},
    {"command": "submissions", "description": "Статистика решений"},
    {"command": "users", "description": "Пользователи"},
    {"command": "payments", "description": "Платежи"},
    {"command": "tasks", "description": "Задачи на проверке"},
    {"command": "task", "description": "Информация о задаче"},
    {"command": "deploy", "description": "Текущий deploy"},
    {"command": "mute", "description": "Отключить некритичные алерты"},
    {"command": "unmute", "description": "Включить алерты"},
    {"command": "settings", "description": "Настройки чата"},
    {"command": "help", "description": "Справка"},
]


def main():
    config = TelegramBotConfig.from_env()
    if not config.token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")
    if not config.admin_ids:
        raise SystemExit("TELEGRAM_ADMIN_IDS is required")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", config.webhook_secret):
        raise SystemExit("TELEGRAM_WEBHOOK_SECRET must contain 16-256 safe characters")
    public_api = os.getenv("PUBLIC_API_BASE", "https://codebug.onrender.com").rstrip("/")
    if not public_api.startswith("https://"):
        raise SystemExit("PUBLIC_API_BASE must use HTTPS")

    api = TelegramAPI(config.token)
    bot = api.call("getMe") or {}
    webhook_url = f"{public_api}/telegram/webhook"
    api.call("setWebhook", {
        "url": webhook_url,
        "secret_token": config.webhook_secret,
        "allowed_updates": ["message", "edited_message", "callback_query"],
        "drop_pending_updates": False,
        "max_connections": 10,
    })
    api.call("setMyCommands", {"commands": COMMANDS})
    print(f"Configured @{bot.get('username', 'bot')} webhook: {webhook_url}")
    print("Token was read from the environment and was not printed.")


if __name__ == "__main__":
    main()
