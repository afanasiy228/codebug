"""Small, dependency-free Telegram admin bot for CodeBug.

The bot deliberately knows nothing about Flask or Firebase. The application
injects read-only diagnostics and the one allowed mutation (task moderation),
which keeps command parsing and authorization easy to test.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


MAX_TELEGRAM_MESSAGE = 3900
COMMAND_RE = re.compile(r"^/([a-z0-9_]{1,32})(?:@[A-Za-z0-9_]{3,64})?(?:\s+(.*))?$", re.I)
TELEGRAM_COMMANDS = [
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


def _parse_int_set(raw):
    values = set()
    for item in str(raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.add(int(item))
        except ValueError:
            continue
    return values


def _format_duration(seconds):
    seconds = max(0, int(seconds or 0))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    if days:
        return f"{days} д {hours} ч"
    if hours:
        return f"{hours} ч {minutes} мин"
    return f"{minutes} мин"


def _status_icon(ok):
    return "✅" if ok else "❌"


@dataclass(frozen=True)
class TelegramBotConfig:
    token: str
    webhook_secret: str
    admin_ids: frozenset[int]
    allowed_chat_ids: frozenset[int]
    alert_chat_ids: frozenset[int]
    monitor_interval: int = 60
    queue_warning: int = 25
    disk_free_warning_percent: float = 10.0
    alert_cooldown: int = 900

    @classmethod
    def from_env(cls):
        allowed = _parse_int_set(os.getenv("TELEGRAM_ALLOWED_CHAT_IDS"))
        alerts = _parse_int_set(os.getenv("TELEGRAM_ALERT_CHAT_IDS")) or allowed
        return cls(
            token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip(),
            admin_ids=frozenset(_parse_int_set(os.getenv("TELEGRAM_ADMIN_IDS"))),
            allowed_chat_ids=frozenset(allowed),
            alert_chat_ids=frozenset(alerts),
            monitor_interval=max(30, int(os.getenv("TELEGRAM_MONITOR_INTERVAL", "60"))),
            queue_warning=max(1, int(os.getenv("TELEGRAM_QUEUE_WARNING", "25"))),
            disk_free_warning_percent=max(1.0, float(os.getenv("TELEGRAM_DISK_FREE_WARNING_PERCENT", "10"))),
            alert_cooldown=max(60, int(os.getenv("TELEGRAM_ALERT_COOLDOWN", "900"))),
        )

    @property
    def enabled(self):
        return bool(self.token and self.webhook_secret and self.admin_ids)


class TelegramAPI:
    def __init__(self, token, timeout=10):
        self._base = f"https://api.telegram.org/bot{token}"
        self._timeout = timeout

    def call(self, method, payload=None):
        body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base}/{method}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"telegram_{method}_http_{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            raise RuntimeError(f"telegram_{method}_request_failed") from None
        if not result.get("ok"):
            raise RuntimeError(f"telegram_{method}_failed")
        return result.get("result")

    def send_message(self, chat_id, text, reply_markup=None, message_thread_id=None):
        payload = {
            "chat_id": chat_id,
            "text": str(text)[:MAX_TELEGRAM_MESSAGE],
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        return self.call("sendMessage", payload)

    def answer_callback(self, callback_id, text="", show_alert=False):
        return self.call("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": str(text)[:180],
            "show_alert": bool(show_alert),
        })


def configure_telegram_webhook(config, public_api, api=None):
    """Idempotently configure Telegram without exposing the bot token."""
    if not config.token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    if not config.admin_ids:
        raise ValueError("TELEGRAM_ADMIN_IDS is required")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", config.webhook_secret):
        raise ValueError("TELEGRAM_WEBHOOK_SECRET must contain 16-256 safe characters")

    public_api = str(public_api or "").rstrip("/")
    parsed = urllib.parse.urlparse(public_api)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("PUBLIC_API_BASE must use HTTPS")

    telegram = api or TelegramAPI(config.token)
    bot = telegram.call("getMe") or {}
    webhook_url = f"{public_api}/telegram/webhook"
    telegram.call("setWebhook", {
        "url": webhook_url,
        "secret_token": config.webhook_secret,
        "allowed_updates": ["message", "edited_message", "callback_query"],
        "drop_pending_updates": False,
        "max_connections": 10,
    })
    telegram.call("setMyCommands", {"commands": TELEGRAM_COMMANDS})
    return {"username": str(bot.get("username") or "bot"), "webhook_url": webhook_url}


class TelegramAdminBot:
    def __init__(self, config, snapshot_provider, task_provider, task_moderator, api=None):
        self.config = config
        self.api = api or TelegramAPI(config.token)
        self.snapshot_provider = snapshot_provider
        self.task_provider = task_provider
        self.task_moderator = task_moderator
        self._processed = deque(maxlen=1000)
        self._processed_set = set()
        self._processing_set = set()
        self._lock = threading.Lock()
        self._muted_until = 0.0

    def _claim_update(self, update_id):
        if update_id is None:
            return True
        with self._lock:
            if update_id in self._processed_set or update_id in self._processing_set:
                return False
            self._processing_set.add(update_id)
        return True

    def _finish_update(self, update_id, success):
        if update_id is None:
            return
        with self._lock:
            self._processing_set.discard(update_id)
            if not success:
                return
            if len(self._processed) == self._processed.maxlen:
                self._processed_set.discard(self._processed[0])
            self._processed.append(update_id)
            self._processed_set.add(update_id)

    def _authorized(self, user_id, chat_id, chat_type):
        if user_id not in self.config.admin_ids:
            return False
        if chat_type in {"group", "supergroup"} and self.config.allowed_chat_ids:
            return chat_id in self.config.allowed_chat_ids
        return True

    def _send(self, chat_id, text, reply_markup=None, thread_id=None):
        return self.api.send_message(chat_id, text, reply_markup, thread_id)

    def handle_update(self, update):
        if not isinstance(update, dict):
            return
        update_id = update.get("update_id")
        if not self._claim_update(update_id):
            return
        success = False
        try:
            callback = update.get("callback_query")
            if isinstance(callback, dict):
                self._handle_callback(callback)
                success = True
                return
            message = update.get("message") or update.get("edited_message")
            if not isinstance(message, dict):
                success = True
                return
            text = str(message.get("text") or "").strip()
            match = COMMAND_RE.match(text)
            if not match:
                success = True
                return
            sender = message.get("from") or {}
            chat = message.get("chat") or {}
            user_id = sender.get("id")
            chat_id = chat.get("id")
            chat_type = str(chat.get("type") or "private")
            thread_id = message.get("message_thread_id")
            if not self._authorized(user_id, chat_id, chat_type):
                self._send(chat_id, "⛔ Команда доступна только администраторам CodeBug.", thread_id=thread_id)
                success = True
                return
            command = match.group(1).lower()
            args = (match.group(2) or "").strip()
            self._dispatch(command, args, chat_id, user_id, thread_id)
            success = True
        finally:
            self._finish_update(update_id, success)

    def _dispatch(self, command, args, chat_id, user_id, thread_id):
        if command in {"start", "help"}:
            self._send(chat_id, self.help_text(), thread_id=thread_id)
        elif command in {"status", "health"}:
            self._send(chat_id, self._format_status(self.snapshot_provider("status")), thread_id=thread_id)
        elif command == "queue":
            self._send(chat_id, self._format_queue(self.snapshot_provider("queue")), thread_id=thread_id)
        elif command == "errors":
            self._send(chat_id, self._format_errors(self.snapshot_provider("errors")), thread_id=thread_id)
        elif command == "submissions":
            hours = self._hours_arg(args)
            self._send(chat_id, self._format_submissions(self.snapshot_provider("submissions", hours=hours)), thread_id=thread_id)
        elif command == "users":
            self._send(chat_id, self._format_users(self.snapshot_provider("users")), thread_id=thread_id)
        elif command == "payments":
            self._send(chat_id, self._format_payments(self.snapshot_provider("payments")), thread_id=thread_id)
        elif command == "tasks":
            self._send(chat_id, self._format_tasks(self.snapshot_provider("tasks")), thread_id=thread_id)
        elif command == "task":
            self._send_task(chat_id, args, thread_id)
        elif command == "deploy":
            self._send(chat_id, self._format_deploy(self.snapshot_provider("deploy")), thread_id=thread_id)
        elif command == "mute":
            seconds = self._mute_seconds(args)
            self._muted_until = time.time() + seconds
            self._send(chat_id, f"🔕 Некритичные уведомления выключены на {_format_duration(seconds)}.", thread_id=thread_id)
        elif command == "unmute":
            self._muted_until = 0
            self._send(chat_id, "🔔 Уведомления включены.", thread_id=thread_id)
        elif command == "settings":
            mute = _format_duration(self._muted_until - time.time()) if self._muted_until > time.time() else "выключен"
            self._send(chat_id, f"⚙️ Настройки\nChat ID: {chat_id}\nMute: {mute}\nИнтервал проверки: {self.config.monitor_interval} сек.", thread_id=thread_id)
        else:
            self._send(chat_id, "Неизвестная команда. Используй /help.", thread_id=thread_id)

    @staticmethod
    def _hours_arg(raw):
        try:
            return min(168, max(1, int(raw or 24)))
        except ValueError:
            return 24

    @staticmethod
    def _mute_seconds(raw):
        match = re.fullmatch(r"\s*(\d{1,4})\s*([mh]?)\s*", raw or "30m", re.I)
        if not match:
            return 1800
        amount = int(match.group(1))
        seconds = amount * (3600 if match.group(2).lower() == "h" else 60)
        return min(86400, max(60, seconds))

    def _send_task(self, chat_id, raw_id, thread_id=None):
        try:
            task_id = int(raw_id)
        except (TypeError, ValueError):
            self._send(chat_id, "Использование: /task ID", thread_id=thread_id)
            return
        task = self.task_provider(task_id)
        if not task:
            self._send(chat_id, f"Задача {task_id} не найдена.", thread_id=thread_id)
            return
        status = task.get("verificationStatus", "pending")
        action = "pending" if status == "approved" else "approved"
        label = "Убрать подтверждение" if status == "approved" else "Подтвердить"
        keyboard = {"inline_keyboard": [[{
            "text": label,
            "callback_data": f"task:{action}:{task_id}",
        }]]}
        self._send(
            chat_id,
            f"🧩 Задача {task_id}\n{task.get('title', 'Без названия')}\nСтатус: {status}\nЯзык: {task.get('language', '—')}\nСложность: {task.get('difficulty', '—')}",
            reply_markup=keyboard,
            thread_id=thread_id,
        )

    def _handle_callback(self, callback):
        sender = callback.get("from") or {}
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        user_id = sender.get("id")
        chat_id = chat.get("id")
        chat_type = str(chat.get("type") or "private")
        callback_id = callback.get("id")
        if not self._authorized(user_id, chat_id, chat_type):
            self.api.answer_callback(callback_id, "Нет доступа", show_alert=True)
            return
        match = re.fullmatch(r"task:(approved|pending):(\d+)", str(callback.get("data") or ""))
        if not match:
            self.api.answer_callback(callback_id, "Неизвестное действие", show_alert=True)
            return
        status, raw_id = match.groups()
        try:
            result = self.task_moderator(int(raw_id), status, user_id)
        except Exception:
            self.api.answer_callback(callback_id, "Ошибка изменения задачи", show_alert=True)
            return
        self.api.answer_callback(callback_id, "Готово")
        self._send(chat_id, f"✅ Задача {raw_id}: статус изменён на {result.get('verificationStatus', status)}.")

    @property
    def alerts_muted(self):
        return self._muted_until > time.time()

    def broadcast_alert(self, text, critical=False):
        if self.alerts_muted and not critical:
            return
        for chat_id in self.config.alert_chat_ids:
            try:
                self._send(chat_id, text)
            except Exception:
                continue

    @staticmethod
    def help_text():
        return (
            "🐞 CodeBug Admin Bot\n\n"
            "/status — общее состояние системы\n"
            "/health — расширенная проверка компонентов\n"
            "/queue — очередь и worker judge\n"
            "/errors — последние ошибки backend\n"
            "/submissions [часы] — вердикты за период\n"
            "/users — пользователи и регистрации\n"
            "/payments — платежи и проблемные статусы\n"
            "/tasks — подтверждённые и ожидающие задачи\n"
            "/task ID — задача и кнопка модерации\n"
            "/deploy — commit и время работы процесса\n"
            "/mute 30m — отключить некритичные алерты\n"
            "/unmute — включить алерты\n"
            "/settings — настройки текущего чата\n\n"
            "В группе можно писать /status или /status@имя_бота. "
            "Команды выполняются только для разрешённых администраторов."
        )

    @staticmethod
    def _format_status(data):
        queue = data.get("queue") or {}
        tasks = data.get("tasks") or {}
        return (
            "🐞 CodeBug — состояние\n\n"
            f"{_status_icon(data.get('backend'))} Backend\n"
            f"{_status_icon(data.get('firebase'))} Firebase\n"
            f"{_status_icon(data.get('judgeWorker'))} Judge worker\n"
            f"Очередь: {queue.get('total', 0)} (PRO {queue.get('pro', 0)}, FREE {queue.get('free', 0)})\n"
            f"Активных запусков: {queue.get('active', 0)}\n"
            f"Задачи: {tasks.get('approved', 0)} подтверждено, {tasks.get('pending', 0)} ожидает\n"
            f"Свободно на диске: {data.get('diskFreePercent', 0):.1f}%\n"
            f"Uptime: {_format_duration(data.get('uptimeSeconds', 0))}"
        )

    @staticmethod
    def _format_queue(data):
        return (
            "⚙️ Очередь judge\n\n"
            f"Всего: {data.get('total', 0)}\n"
            f"PRO: {data.get('pro', 0)}\n"
            f"FREE: {data.get('free', 0)}\n"
            f"Активно: {data.get('active', 0)}\n"
            f"Среднее ожидание: {data.get('averageWaitSeconds', 0):.1f} сек.\n"
            f"Worker: {'работает' if data.get('workerStarted') else 'не запущен'}\n"
            f"Лимит очереди: {data.get('limit', 0)}"
        )

    @staticmethod
    def _format_errors(data):
        errors = data.get("errors") or []
        if not errors:
            return "✅ После запуска процесса ошибок не зарегистрировано."
        lines = ["🚨 Последние ошибки backend"]
        for item in errors[-10:]:
            lines.append(f"• {item.get('time', '—')} · {item.get('code', 'error')} · {item.get('message', '')}")
        return "\n".join(lines)

    @staticmethod
    def _format_submissions(data):
        verdicts = data.get("verdicts") or {}
        rendered = ", ".join(f"{key}: {value}" for key, value in sorted(verdicts.items())) or "нет"
        return f"📨 Решения за {data.get('hours', 24)} ч\nВсего: {data.get('total', 0)}\nВердикты: {rendered}\nСреднее время: {data.get('averageTimeMs', 0):.0f} мс"

    @staticmethod
    def _format_users(data):
        return f"👥 Пользователи\nВсего: {data.get('total', 0)}\nНовых за 24 часа: {data.get('new24h', 0)}"

    @staticmethod
    def _format_payments(data):
        statuses = data.get("statuses") or {}
        rendered = ", ".join(f"{key}: {value}" for key, value in sorted(statuses.items())) or "нет"
        return f"💳 Платежи за 24 часа\nВсего: {data.get('total', 0)}\nСтатусы: {rendered}\nПроблемных: {data.get('problems', 0)}"

    @staticmethod
    def _format_tasks(data):
        pending = data.get("pendingItems") or []
        suffix = "\n" + "\n".join(f"• {item['id']}: {item['title']}" for item in pending[:10]) if pending else ""
        return f"🧩 Задачи\nПодтверждено: {data.get('approved', 0)}\nОжидает: {data.get('pending', 0)}{suffix}"

    @staticmethod
    def _format_deploy(data):
        return f"🚀 Деплой\nCommit: {data.get('commit', 'unknown')}\nВетка: {data.get('branch', 'unknown')}\nUptime: {_format_duration(data.get('uptimeSeconds', 0))}"


class TelegramMonitor:
    def __init__(self, bot, snapshot_provider):
        self.bot = bot
        self.snapshot_provider = snapshot_provider
        self._started = False
        self._lock = threading.Lock()
        self._last_sent = {}
        self._previous = {}

    def start(self):
        with self._lock:
            if self._started:
                return
            self._started = True
        thread = threading.Thread(target=self._run, daemon=True, name="telegram-monitor")
        thread.start()

    def _emit(self, key, message, critical=False):
        now = time.time()
        if now - self._last_sent.get(key, 0) < self.bot.config.alert_cooldown:
            return
        self._last_sent[key] = now
        self.bot.broadcast_alert(message, critical=critical)

    def check_once(self):
        data = self.snapshot_provider("status")
        queue = data.get("queue") or {}
        tasks = data.get("tasks") or {}
        if not data.get("firebase"):
            self._emit("firebase", "🚨 Firebase недоступна для backend.", critical=True)
        if queue.get("total", 0) >= self.bot.config.queue_warning:
            self._emit("queue", f"⚠️ Очередь judge выросла до {queue.get('total', 0)}.")
        if queue.get("total", 0) and not data.get("judgeWorker"):
            self._emit("worker", "🚨 В очереди есть решения, но judge worker не запущен.", critical=True)
        if queue.get("active", 0) and queue.get("oldestActiveSeconds", 0) > 180:
            self._emit("stuck_job", f"🚨 Запуск judge выполняется уже {queue.get('oldestActiveSeconds', 0):.0f} сек.", critical=True)
        if data.get("diskFreePercent", 100) <= self.bot.config.disk_free_warning_percent:
            self._emit("disk", f"🚨 На диске осталось {data.get('diskFreePercent', 0):.1f}%.", critical=True)
        backup = data.get("backup") or {}
        if backup.get("configured") and not backup.get("fresh"):
            self._emit("backup", "🚨 Резервная копия не обновлялась дольше допустимого срока.", critical=True)
        previous_pending = self._previous.get("pending")
        current_pending = tasks.get("pending", 0)
        if previous_pending is not None and current_pending > previous_pending:
            self._emit("new_task", f"🧩 Новых задач на проверке: {current_pending - previous_pending}. Всего ожидает: {current_pending}.")
        self._previous["pending"] = current_pending

        errors = (self.snapshot_provider("errors") or {}).get("errors") or []
        last_error_id = self._previous.get("last_error_id")
        if errors:
            newest = errors[-1]
            if newest.get("id") != last_error_id and newest.get("severity") == "critical":
                self._emit(
                    f"error:{newest.get('code')}",
                    f"🚨 Backend: {newest.get('code', 'ERROR')} · {newest.get('message', '')}",
                    critical=True,
                )
            self._previous["last_error_id"] = newest.get("id")

        submissions = self.snapshot_provider("submissions", hours=1) or {}
        verdicts = submissions.get("verdicts") or {}
        total = submissions.get("total", 0)
        unhealthy = sum(verdicts.get(code, 0) for code in ("SE", "TL", "RE", "ERROR"))
        if total >= 10 and unhealthy / total >= 0.6:
            self._emit("verdict_spike", f"⚠️ За час {unhealthy} из {total} решений завершились TL/RE/SE.")

        payments = self.snapshot_provider("payments") or {}
        prior_payment_problems = self._previous.get("payment_problems", 0)
        payment_problems = payments.get("problems", 0)
        if payment_problems > prior_payment_problems:
            self._emit("payments", f"🚨 Проблемных платежей за 24 часа: {payment_problems}.", critical=True)
        self._previous["payment_problems"] = payment_problems

    def _run(self):
        while True:
            try:
                self.check_once()
            except Exception:
                pass
            time.sleep(self.bot.config.monitor_interval)
