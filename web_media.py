import mimetypes
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import bot
from api import require_web_token

router = APIRouter(prefix="/api/telegramweb", tags=["Telegram Web Media"])


def _peer(value):
    """Resolve browser peer values correctly for Telethon.

    Dialogs without a public username are sent by the web UI as their
    numeric Telegram ID. Telethon must receive that value as int, not as
    a numeric string (which it may try to resolve as a username).
    """
    value = str(value).strip()
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def _media_type(message):
    media = getattr(message, "media", None)
    if media is None:
        return None
    name = media.__class__.__name__.lower()
    if "photo" in name:
        return "photo"
    if "document" in name:
        mime = getattr(getattr(message, "file", None), "mime_type", None) or ""
        if mime.startswith("video/"):
            return "video"
        if mime.startswith("audio/"):
            return "audio"
        return "document"
    if "video" in name:
        return "video"
    if "audio" in name or "voice" in name:
        return "audio"
    return "media"


def _message_json(message):
    media = None
    kind = _media_type(message)
    if kind:
        file_obj = getattr(message, "file", None)
        media = {
            "type": kind,
            "message_id": message.id,
            "file_name": getattr(file_obj, "name", None),
            "mime_type": getattr(file_obj, "mime_type", None),
            "size": getattr(file_obj, "size", None),
        }

    return {
        "id": message.id,
        "text": message.text or "",
        "date": message.date.isoformat() if message.date else None,
        "sender_id": message.sender_id,
        "out": bool(message.out),
        "media": media,
    }


@router.get("/media-messages", dependencies=[Depends(require_web_token)])
async def media_messages(peer: str, limit: int = 50):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")

    try:
        entity = _peer(peer)
        messages = await bot.client.get_messages(entity, limit=limit)
        return [_message_json(m) for m in messages]
    except Exception as exc:
        bot.logger.exception("Web media messages error peer=%s", peer)
        raise HTTPException(400, str(exc)) from exc


@router.post("/send-text", dependencies=[Depends(require_web_token)])
async def send_text(data: dict):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")

    peer = data.get("peer")
    text = data.get("text")

    if peer is None or not str(peer).strip():
        raise HTTPException(400, "peer is required")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(400, "text is required")

    try:
        message = await bot.client.send_message(_peer(peer), text)
        return {
            "success": True,
            "id": message.id,
            "date": message.date.isoformat() if message.date else None,
        }
    except Exception as exc:
        bot.logger.exception("Web send text error peer=%s", peer)
        raise HTTPException(400, str(exc)) from exc


@router.get("/avatar/{peer}", dependencies=[Depends(require_web_token)])
async def avatar(peer: str):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")

    temp_dir = Path(tempfile.mkdtemp(prefix="tg-avatar-"))
    try:
        entity = await bot.client.get_entity(_peer(peer))
        path = await bot.client.download_profile_photo(
            entity,
            file=str(temp_dir / "avatar"),
        )
        if not path:
            raise HTTPException(404, "Avatar not found")
        mime = mimetypes.guess_type(path)[0] or "image/jpeg"
        return FileResponse(path, media_type=mime, filename=Path(path).name)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/media/{peer}/{message_id}", dependencies=[Depends(require_web_token)])
async def media(peer: str, message_id: int):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")

    temp_dir = Path(tempfile.mkdtemp(prefix="tg-media-"))
    try:
        entity = _peer(peer)
        message = await bot.client.get_messages(entity, ids=message_id)
        if not message or not message.media:
            raise HTTPException(404, "Media not found")

        path = await bot.client.download_media(
            message,
            file=str(temp_dir / "file"),
        )
        if not path:
            raise HTTPException(404, "Media download failed")

        mime = (
            getattr(getattr(message, "file", None), "mime_type", None)
            or mimetypes.guess_type(path)[0]
            or "application/octet-stream"
        )
        filename = (
            getattr(getattr(message, "file", None), "name", None)
            or Path(path).name
        )
        return FileResponse(path, media_type=mime, filename=filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
