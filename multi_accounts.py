"""Isolated Telethon sessions for the Telegram Web multi-account UI.

The original SESSION_NAME session remains the default account, so existing
installations keep their current Telegram authorization.
"""
import contextvars
import json
import re
import uuid
from pathlib import Path

from telethon import TelegramClient

import bot

DEFAULT_ACCOUNT_ID = "default"
SESSIONS_DIR = Path(bot.SESSION_NAME).resolve().parent
ACCOUNTS_DIR = SESSIONS_DIR / "accounts"
REGISTRY_FILE = SESSIONS_DIR / "accounts.json"
ACTIVE_ACCOUNT = contextvars.ContextVar("telegram_web_account", default=DEFAULT_ACCOUNT_ID)
_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def _read_registry():
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_registry(data):
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = REGISTRY_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(REGISTRY_FILE)


def _new_client(session_path):
    return TelegramClient(
        str(session_path),
        bot.API_ID,
        bot.API_HASH,
        timeout=30,
        **bot.client_kwargs,
    )


class AccountManager:
    def __init__(self):
        self.clients = {DEFAULT_ACCOUNT_ID: bot.client}
        self.pending = set()
        self.registry = _read_registry()
        self.registry.setdefault(DEFAULT_ACCOUNT_ID, {
            "id": DEFAULT_ACCOUNT_ID,
            "label": "Основной аккаунт",
            "legacy": True,
        })
        self._write()
        ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
        for account_id in list(self.registry):
            if account_id == DEFAULT_ACCOUNT_ID or _ID_RE.fullmatch(account_id):
                self._client(account_id)

    def _write(self):
        _write_registry(self.registry)

    def _client(self, account_id):
        if account_id not in self.clients:
            if account_id == DEFAULT_ACCOUNT_ID:
                self.clients[account_id] = bot.client_original
            elif _ID_RE.fullmatch(account_id):
                self.clients[account_id] = _new_client(ACCOUNTS_DIR / account_id)
            else:
                raise ValueError("Некорректный идентификатор аккаунта")
        return self.clients[account_id]

    def validate_id(self, account_id):
        account_id = account_id or DEFAULT_ACCOUNT_ID
        if account_id != DEFAULT_ACCOUNT_ID and account_id not in self.registry and account_id not in self.pending:
            raise KeyError("Аккаунт не найден")
        if account_id != DEFAULT_ACCOUNT_ID and not _ID_RE.fullmatch(account_id):
            raise KeyError("Некорректный идентификатор аккаунта")
        return account_id

    def get_client(self, account_id=None):
        return self._client(self.validate_id(account_id or ACTIVE_ACCOUNT.get()))

    def create_pending(self):
        account_id = uuid.uuid4().hex
        self.pending.add(account_id)
        self._client(account_id)
        return account_id

    def finish_login(self, account_id, user):
        if account_id not in self.pending and account_id not in self.registry:
            raise KeyError("Сессия авторизации не найдена")
        if not user:
            raise ValueError("Telegram не вернул профиль пользователя")
        label = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or user.get("username") or user.get("phone") or "Telegram"
        self.registry[account_id] = {
            "id": account_id,
            "label": label,
            "user_id": user.get("id"),
            "username": user.get("username"),
            "phone": user.get("phone"),
            "legacy": False,
        }
        self.pending.discard(account_id)
        self._write()
        return dict(self.registry[account_id])

    async def public_account(self, account_id, user=None):
        meta = self.registry.get(account_id, {})
        if user is None:
            try:
                token = ACTIVE_ACCOUNT.set(account_id)
                try:
                    client = self.get_client(account_id)
                    if not client.is_connected():
                        await client.connect()
                    if await client.is_user_authorized():
                        user = await self.get_client(account_id).get_me()
                        user = {
                            "id": user.id,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "username": user.username,
                            "phone": user.phone,
                        } if user else None
                finally:
                    ACTIVE_ACCOUNT.reset(token)
            except Exception:
                user = None
        if user:
            label = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or user.get("username") or user.get("phone") or meta.get("label") or "Telegram"
            meta.update({
                "label": label,
                "user_id": user.get("id"),
                "username": user.get("username"),
                "phone": user.get("phone"),
            })
            self.registry[account_id] = meta
            self._write()
        return {
            "id": account_id,
            "label": meta.get("label") or "Telegram",
            "username": (user or {}).get("username") or meta.get("username"),
            "phone": (user or {}).get("phone") or meta.get("phone"),
            "user": user,
            "authorized": bool(user),
            "selected": account_id == ACTIVE_ACCOUNT.get(),
        }

    async def list_accounts(self):
        result = []
        for account_id in list(self.registry):
            result.append(await self.public_account(account_id))
        return result

    async def close(self):
        for account_id, client in list(self.clients.items()):
            try:
                if client.is_connected():
                    await client.disconnect()
            except Exception:
                bot.logger.exception("Failed to disconnect Telegram account %s", account_id)


class ClientProxy:
    def __getattr__(self, name):
        return getattr(manager.get_client(), name)


class LoginDataProxy:
    def _data(self):
        account_id = manager.validate_id(ACTIVE_ACCOUNT.get())
        if account_id not in login_data_by_account:
            login_data_by_account[account_id] = {}
        return login_data_by_account[account_id]

    def __getitem__(self, key):
        return self._data()[key]

    def __setitem__(self, key, value):
        self._data()[key] = value

    def get(self, key, default=None):
        return self._data().get(key, default)

    def pop(self, key, default=None):
        return self._data().pop(key, default)


# Preserve the original Telethon client and session path before replacing the
# module-level client with a transparent account-aware proxy.
bot.client_original = bot.client
manager = AccountManager()
login_data_by_account = {}
bot.client = ClientProxy()
bot.login_data = LoginDataProxy()


def set_active_account(account_id):
    return ACTIVE_ACCOUNT.set(manager.validate_id(account_id))


def reset_active_account(token):
    ACTIVE_ACCOUNT.reset(token)


def active_account_id():
    return ACTIVE_ACCOUNT.get()


async def begin_add_account(phone):
    account_id = manager.create_pending()
    token = set_active_account(account_id)
    try:
        result = await bot.send_code(phone)
    finally:
        reset_active_account(token)
    if not result.get("success"):
        try:
            client = manager.get_client(account_id)
            if client.is_connected():
                await client.disconnect()
        except Exception:
            pass
        manager.pending.discard(account_id)
        manager.clients.pop(account_id, None)
        return result
    result["account_id"] = account_id
    return result


async def complete_add_account(account_id, operation, value):
    if account_id not in manager.pending:
        raise KeyError("Сессия добавления аккаунта не найдена")
    token = set_active_account(account_id)
    try:
        result = await operation(value)
        if result.get("success"):
            user = await bot.get_me()
            manager.finish_login(account_id, user)
            result["account"] = await manager.public_account(account_id, user)
        return result
    finally:
        reset_active_account(token)


async def start_default():
    token = set_active_account(DEFAULT_ACCOUNT_ID)
    try:
        return await bot.connect()
    finally:
        reset_active_account(token)
