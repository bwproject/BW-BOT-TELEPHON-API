import mimetypes
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

import bot
from api import require_web_token

router = APIRouter(prefix="/api/telegramweb", tags=["Telegram Web Media"])


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
        messages = await bot.client.get_messages(peer, limit=limit)
        return [_message_json(m) for m in messages]
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/avatar/{peer}", dependencies=[Depends(require_web_token)])
async def avatar(peer: str):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")
    temp_dir = Path(tempfile.mkdtemp(prefix="tg-avatar-"))
    try:
        entity = await bot.client.get_entity(peer)
        path = await bot.client.download_profile_photo(entity, file=str(temp_dir / "avatar"))
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
        message = await bot.client.get_messages(peer, ids=message_id)
        if not message or not message.media:
            raise HTTPException(404, "Media not found")
        path = await bot.client.download_media(message, file=str(temp_dir / "file"))
        if not path:
            raise HTTPException(404, "Media download failed")
        mime = getattr(getattr(message, "file", None), "mime_type", None) or mimetypes.guess_type(path)[0] or "application/octet-stream"
        filename = getattr(getattr(message, "file", None), "name", None) or Path(path).name
        return FileResponse(path, media_type=mime, filename=filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
