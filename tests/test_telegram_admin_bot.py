from dataclasses import replace

import telegram_admin_bot as bot_module
from telegram_admin_bot import (
    TELEGRAM_COMMANDS,
    TelegramAdminBot,
    TelegramBotConfig,
    TelegramMonitor,
    configure_telegram_webhook,
)


class FakeAPI:
    def __init__(self):
        self.messages = []
        self.callbacks = []

    def send_message(self, chat_id, text, reply_markup=None, message_thread_id=None):
        self.messages.append({
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
            "thread_id": message_thread_id,
        })

    def answer_callback(self, callback_id, text="", show_alert=False):
        self.callbacks.append((callback_id, text, show_alert))


class FailOnceAPI(FakeAPI):
    def __init__(self):
        super().__init__()
        self.failed = False

    def send_message(self, chat_id, text, reply_markup=None, message_thread_id=None):
        if not self.failed:
            self.failed = True
            raise RuntimeError("temporary_failure")
        return super().send_message(chat_id, text, reply_markup, message_thread_id)


class SetupAPI:
    def __init__(self):
        self.calls = []

    def call(self, method, payload=None):
        self.calls.append((method, payload or {}))
        return {"username": "CodeBugAdminBot"} if method == "getMe" else True


def config(**overrides):
    base = TelegramBotConfig(
        token="test-token",
        webhook_secret="safe_webhook_secret_123456",
        admin_ids=frozenset({101}),
        allowed_chat_ids=frozenset({-500}),
        alert_chat_ids=frozenset({-500}),
        alert_cooldown=60,
    )
    return replace(base, **overrides)


def snapshot(section, **kwargs):
    values = {
        "status": {
            "backend": True,
            "firebase": True,
            "judgeWorker": True,
            "queue": {"total": 2, "pro": 1, "free": 1},
            "tasks": {"approved": 3, "pending": 4},
            "diskFreePercent": 50.0,
            "uptimeSeconds": 3600,
        },
        "queue": {"total": 2, "pro": 1, "free": 1, "workerStarted": True, "limit": 300},
        "errors": {"errors": []},
        "submissions": {"hours": kwargs.get("hours", 24), "total": 2, "verdicts": {"OK": 2}, "averageTimeMs": 25},
        "payments": {"total": 0, "statuses": {}, "problems": 0},
    }
    return values.get(section, {})


def make_bot(api=None, cfg=None, moderator=None):
    return TelegramAdminBot(
        cfg or config(),
        snapshot,
        lambda task_id: {
            "id": task_id,
            "title": "Test task",
            "verificationStatus": "pending",
            "language": "cpp",
            "difficulty": "normal",
        },
        moderator or (lambda task_id, status, actor: {"id": task_id, "verificationStatus": status}),
        api=api or FakeAPI(),
    )


def message_update(text, user_id=101, chat_id=-500, chat_type="supergroup", update_id=1):
    return {
        "update_id": update_id,
        "message": {
            "text": text,
            "from": {"id": user_id},
            "chat": {"id": chat_id, "type": chat_type},
            "message_thread_id": 7,
        },
    }


def test_help_works_in_group_with_bot_username_suffix():
    api = FakeAPI()
    bot = make_bot(api=api)

    bot.handle_update(message_update("/help@CodeBugAdminBot"))

    assert "CodeBug Admin Bot" in api.messages[0]["text"]
    assert api.messages[0]["chat_id"] == -500
    assert api.messages[0]["thread_id"] == 7


def test_configure_webhook_is_idempotent_and_sets_command_menu():
    api = SetupAPI()

    result = configure_telegram_webhook(config(), "https://codebug.onrender.com/", api=api)

    assert result == {
        "username": "CodeBugAdminBot",
        "webhook_url": "https://codebug.onrender.com/telegram/webhook",
    }
    assert [method for method, _ in api.calls] == ["getMe", "setWebhook", "setMyCommands"]
    assert api.calls[1][1]["secret_token"] == "safe_webhook_secret_123456"
    assert api.calls[2][1]["commands"] == TELEGRAM_COMMANDS


def test_configure_webhook_rejects_non_https_public_url():
    try:
        configure_telegram_webhook(config(), "http://localhost:7777", api=SetupAPI())
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("insecure webhook URL was accepted")


def test_status_is_restricted_by_user_and_group():
    api = FakeAPI()
    bot = make_bot(api=api)

    bot.handle_update(message_update("/status", user_id=999, update_id=1))
    bot.handle_update(message_update("/status", chat_id=-999, update_id=2))

    assert all("только администраторам" in item["text"] for item in api.messages)


def test_duplicate_telegram_update_is_ignored():
    api = FakeAPI()
    bot = make_bot(api=api)
    update = message_update("/queue", update_id=77)

    bot.handle_update(update)
    bot.handle_update(update)

    assert len(api.messages) == 1


def test_failed_update_can_be_retried_by_telegram():
    api = FailOnceAPI()
    bot = make_bot(api=api)
    update = message_update("/status", update_id=88)

    try:
        bot.handle_update(update)
    except RuntimeError:
        pass
    bot.handle_update(update)

    assert len(api.messages) == 1


def test_task_callback_requires_admin_and_records_actor():
    api = FakeAPI()
    calls = []
    bot = make_bot(
        api=api,
        moderator=lambda task_id, status, actor: calls.append((task_id, status, actor)) or {
            "verificationStatus": status
        },
    )
    callback = {
        "update_id": 2,
        "callback_query": {
            "id": "cb-1",
            "data": "task:approved:27",
            "from": {"id": 101},
            "message": {"chat": {"id": -500, "type": "supergroup"}},
        },
    }

    bot.handle_update(callback)

    assert calls == [(27, "approved", 101)]
    assert api.callbacks == [("cb-1", "Готово", False)]


def test_monitor_sends_critical_health_alerts():
    api = FakeAPI()
    cfg = config(queue_warning=3)

    def unhealthy(section, **kwargs):
        if section == "status":
            return {
                "firebase": False,
                "judgeWorker": False,
                "queue": {"total": 5},
                "tasks": {"pending": 2},
                "diskFreePercent": 5,
                "backup": {"configured": True, "fresh": False},
            }
        if section == "errors":
            return {"errors": [{"id": "1", "severity": "critical", "code": "BROKEN", "message": "failed"}]}
        if section == "submissions":
            return {"total": 0, "verdicts": {}}
        if section == "payments":
            return {"problems": 0}
        return {}

    bot = make_bot(api=api, cfg=cfg)
    monitor = TelegramMonitor(bot, unhealthy)

    monitor.check_once()

    rendered = "\n".join(item["text"] for item in api.messages)
    assert "Firebase" in rendered
    assert "judge" in rendered
    assert "диске" in rendered
    assert "Резервная копия" in rendered
    assert "BROKEN" in rendered


def test_webhook_rejects_wrong_secret_and_accepts_valid_one(srv, monkeypatch):
    handled = []
    fake_bot = type("Bot", (), {"handle_update": lambda self, update: handled.append(update)})()
    monkeypatch.setattr(srv.module, "TELEGRAM_ADMIN_BOT", fake_bot)
    monkeypatch.setattr(srv.module, "TELEGRAM_BOT_CONFIG", config())

    rejected = srv.client.post(
        "/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    accepted = srv.client.post(
        "/telegram/webhook",
        json={"update_id": 2},
        headers={"X-Telegram-Bot-Api-Secret-Token": "safe_webhook_secret_123456"},
    )

    assert rejected.status_code == 403
    assert accepted.status_code == 200
    assert handled == [{"update_id": 2}]
