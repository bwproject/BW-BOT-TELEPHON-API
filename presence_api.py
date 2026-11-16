import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from telethon.tl.types import (
    Channel,
    Chat,
    User,
    UserStatusEmpty,
    UserStatusLastMonth,
    UserStatusLastWeek,
    UserStatusOffline,
    UserStatusOnline,
    UserStatusRecently,
)

import bot
from api import require_web_token
from web_media import _media_type

router = APIRouter(prefix="/api/telegramweb", tags=["Telegram Web Presence"])


def _iso(value):
    if not value:
        return None
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _presence(entity):
    if not isinstance(entity, User):
        return {
            "kind": "unknown",
            "online": False,
            "last_seen": None,
            "label": None,
        }

    status = getattr(entity, "status", None)

    if isinstance(status, UserStatusOnline):
        return {
            "kind": "online",
            "online": True,
            "last_seen": None,
            "label": "онлайн",
        }

    if isinstance(status, UserStatusOffline):
        return {
            "kind": "offline",
            "online": False,
            "last_seen": _iso(status.was_online),
            "label": "был(а) в сети",
        }

    if isinstance(status, UserStatusRecently):
        return {
            "kind": "recently",
            "online": False,
            "last_seen": None,
            "label": "был(а) недавно",
        }

    if isinstance(status, UserStatusLastWeek):
        return {
            "kind": "last_week",
            "online": False,
            "last_seen": None,
            "label": "был(а) на этой неделе",
        }

    if isinstance(status, UserStatusLastMonth):
        return {
            "kind": "last_month",
            "online": False,
            "last_seen": None,
            "label": "был(а) в этом месяце",
        }

    if isinstance(status, UserStatusEmpty):
        return {
            "kind": "hidden",
            "online": False,
            "last_seen": None,
            "label": "статус скрыт",
        }

    return {
        "kind": "unknown",
        "online": False,
        "last_seen": None,
        "label": None,
    }


_MEDIA_LABELS = {
    "photo": "Фото",
    "video": "Видео",
    "round": "Видеосообщение",
    "gif": "GIF",
    "sticker": "Стикер",
    "voice": "Голосовое сообщение",
    "audio": "Аудио",
    "document": "Файл",
    "image": "Изображение",
    "geo": "Геопозиция",
    "poll": "Опрос",
    "contact": "Контакт",
}


def _last_message_preview(message):
    if message is None:
        return ""
    text = (getattr(message, "message", None) or "").strip()
    if text:
        return text
    media = getattr(message, "media", None)
    if media is not None:
        kind = _media_type(message)
        return _MEDIA_LABELS.get(kind or "", "Вложение")
    if getattr(message, "action", None) is not None:
        return "Сервисное сообщение"
    return ""


async def _dialog_presence(dialog):
    entity = dialog.entity
    last = getattr(dialog, "message", None)
    kind = "user"
    if isinstance(entity, Channel):
        kind = "channel"
    elif isinstance(entity, Chat):
        kind = "group"
    return {
        "id": dialog.id,
        "name": dialog.name,
        "username": getattr(entity, "username", None),
        "unread": dialog.unread_count,
        "type": entity.__class__.__name__,
        "kind": kind,
        "is_user": isinstance(entity, User),
        "is_bot": bool(getattr(entity, "bot", False)),
        "verified": bool(getattr(entity, "verified", False)),
        "pinned": bool(getattr(dialog, "pinned", False)),
        "muted": bool(getattr(dialog, "muted", False)),
        "last_text": _last_message_preview(last)[:180],
        "last_date": _iso(getattr(last, "date", None)),
        "last_out": bool(getattr(last, "out", False)),
        "presence": _presence(entity),
    }


@router.get("/dialogs-with-presence", dependencies=[Depends(require_web_token)])
async def dialogs_with_presence(limit: int = 100):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")

    result = []
    try:
        async for dialog in bot.client.iter_dialogs(limit=limit):
            result.append(await _dialog_presence(dialog))
        return result
    except Exception as exc:
        raise HTTPException(502, f"Failed to load Telegram dialogs: {exc}") from exc


@router.get("/presence", dependencies=[Depends(require_web_token)])
async def presence(peer: str):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")

    try:
        entity = await bot.client.get_entity(peer)
    except Exception as exc:
        raise HTTPException(404, f"Telegram peer not found: {exc}") from exc

    return {
        "peer": peer,
        "name": getattr(entity, "first_name", None) or getattr(entity, "title", None) or getattr(entity, "username", None),
        "username": getattr(entity, "username", None),
        "presence": _presence(entity),
    }
