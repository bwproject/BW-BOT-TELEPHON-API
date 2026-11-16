import asyncio
import json
import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from fastapi.responses import FileResponse

import bot
import multi_accounts
from api import require_web_token

router = APIRouter(prefix="/api/telegramweb", tags=["Telegram Web Media"])

BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "telegram_media"
SETTINGS_FILE = MEDIA_DIR / "settings.json"
DEFAULT_SETTINGS = {
    "download_mode": "open",
    "auto_download": True,
    "excluded_peers": [],
    "ttl_hours": 24,
    "auto_cleanup": True,
}
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def _load_settings():
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        result = {**DEFAULT_SETTINGS, **data}
        result["excluded_peers"] = [str(x) for x in result.get("excluded_peers", [])]
        return result
    except Exception:
        return dict(DEFAULT_SETTINGS)


def _save_settings(data):
    settings = {**DEFAULT_SETTINGS, **data}
    settings["excluded_peers"] = [str(x).strip() for x in settings.get("excluded_peers", []) if str(x).strip()]
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings


def _peer(value):
    value = str(value).strip()
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def _safe(value):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value))[:120] or "peer"


def _document_attributes(document):
    return list(getattr(document, "attributes", None) or [])


def _find_attribute(attributes, name):
    for attribute in attributes:
        if attribute.__class__.__name__ == name:
            return attribute
    return None


def _media_type(message):
    """Classify a Telegram message attachment.

    The web UI needs a precise kind because it renders photos, videos,
    stickers, voice notes and plain documents very differently.
    """
    media = getattr(message, "media", None)
    if media is None:
        return None

    media_name = media.__class__.__name__
    file_obj = getattr(message, "file", None)
    mime = (getattr(file_obj, "mime_type", None) or "").lower()

    if media_name == "MessageMediaPhoto":
        return "photo"

    if media_name == "MessageMediaDocument":
        document = getattr(media, "document", None)
        mime = mime or (getattr(document, "mime_type", "") or "").lower()
        attributes = _document_attributes(document)
        attribute_names = {a.__class__.__name__ for a in attributes}

        video = _find_attribute(attributes, "DocumentAttributeVideo")
        audio = _find_attribute(attributes, "DocumentAttributeAudio")

        if video is not None:
            if getattr(video, "round_message", False):
                return "round"
            if "DocumentAttributeAnimated" in attribute_names:
                return "gif"
            return "video"
        if "DocumentAttributeSticker" in attribute_names:
            return "sticker"
        if audio is not None:
            return "voice" if getattr(audio, "voice", False) else "audio"
        if mime.startswith("image/"):
            return "image"
        if mime.startswith("video/"):
            return "video"
        if mime.startswith("audio/"):
            return "audio"
        return "document"

    if media_name == "MessageMediaWebPage":
        return None
    if media_name == "MessageMediaPoll":
        return "poll"
    if media_name in ("MessageMediaGeo", "MessageMediaGeoLive", "MessageMediaVenue"):
        return "geo"
    if media_name == "MessageMediaContact":
        return "contact"
    return "media"


def _media_size(message):
    """Best-effort pixel size of an attachment, used to reserve layout space."""
    file_obj = getattr(message, "file", None)
    width = getattr(file_obj, "width", None)
    height = getattr(file_obj, "height", None)
    if width and height:
        return width, height

    photo = getattr(message, "photo", None)
    best = None
    for size in getattr(photo, "sizes", None) or []:
        w = getattr(size, "w", None)
        h = getattr(size, "h", None)
        if w and h and (best is None or w * h > best[0] * best[1]):
            best = (w, h)
    if best:
        return best

    document = getattr(getattr(message, "media", None), "document", None)
    for attribute in _document_attributes(document):
        if attribute.__class__.__name__ in (
            "DocumentAttributeImageSize",
            "DocumentAttributeVideo",
        ):
            w = getattr(attribute, "w", None)
            h = getattr(attribute, "h", None)
            if w and h:
                return w, h
    return None, None


def _media_json(message, kind):
    file_obj = getattr(message, "file", None)
    width, height = _media_size(message)
    media = {
        "type": kind,
        "message_id": message.id,
        "file_name": getattr(file_obj, "name", None),
        "mime_type": getattr(file_obj, "mime_type", None),
        "size": getattr(file_obj, "size", None),
        # width/height let the browser reserve the exact space for a photo
        # before it is downloaded. Without them the chat "jumps" when media
        # suddenly appears above the current scroll position.
        "width": width,
        "height": height,
        "duration": getattr(file_obj, "duration", None),
    }
    return media


def _sender_name(message):
    sender = getattr(message, "sender", None)
    if sender is None:
        return None
    title = getattr(sender, "title", None)
    if title:
        return title
    name = " ".join(
        part
        for part in (
            getattr(sender, "first_name", None),
            getattr(sender, "last_name", None),
        )
        if part
    )
    return name or getattr(sender, "username", None)


def _service_text(message, sender_name):
    action = getattr(message, "action", None)
    if action is None:
        return None
    action_name = action.__class__.__name__
    who = sender_name or "Пользователь"
    if action_name == "MessageActionPinMessage":
        return "Закреплённое сообщение"
    if action_name == "MessageActionChatEditTitle":
        return f'{who} изменил(а) название на «{getattr(action, "title", "")}»'
    if action_name in ("MessageActionChatAddUser", "MessageActionChatJoinedByLink"):
        return f"{who} присоединился(ась) к чату"
    if action_name == "MessageActionChatDeleteUser":
        return f"{who} покинул(а) чат"
    if action_name in ("MessageActionChatEditPhoto", "MessageActionChatDeletePhoto"):
        return f"{who} обновил(а) фото чата"
    if action_name == "MessageActionChannelCreate":
        return "Канал создан"
    return "Сервисное сообщение"


def _message_json(message):
    kind = _media_type(message)
    return {
        "id": message.id,
        "text": message.text or "",
        "date": message.date.isoformat() if message.date else None,
        "sender_id": message.sender_id,
        "sender_name": _sender_name(message),
        "out": bool(message.out),
        "read": bool(getattr(message, "read_out", False)),
        "edited": bool(getattr(message, "edit_date", None)),
        "service": _service_text(message, _sender_name(message))
        if getattr(message, "action", None) is not None
        else None,
        "media": _media_json(message, kind) if kind else None,
    }


def _account_peer_key(peer):
    return _safe(str(multi_accounts.active_account_id()) + '_' + str(peer))


def _cached_file(peer, message_id):
    folder = MEDIA_DIR / _account_peer_key(peer)
    if not folder.exists():
        return None
    # Thumbnails share the "{id}_thumb*" prefix: never return them as media.
    matches = [
        path
        for path in folder.glob(f"{int(message_id)}_*")
        if "_thumb" not in path.name
    ]
    return matches[0] if matches else None


def _cache_path(peer, message):
    folder = MEDIA_DIR / _account_peer_key(peer)
    folder.mkdir(parents=True, exist_ok=True)
    file_obj = getattr(message, "file", None)
    filename = getattr(file_obj, "name", None) or f"media_{message.id}"
    filename = Path(filename).name
    return folder / f"{message.id}_{_safe(filename)}"


async def _download_to_cache(peer, message):
    cached = _cached_file(peer, message.id)
    if cached and cached.exists() and cached.stat().st_size > 0:
        return cached
    target = _cache_path(peer, message)
    try:
        path = await bot.client.download_media(message, file=str(target))
        if not path:
            return None
        return Path(path)
    except Exception:
        bot.logger.exception("Media cache download failed peer=%s message=%s", peer, message.id)
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def _excluded(peer, settings):
    value = str(peer).strip()
    return value in set(settings.get("excluded_peers", []))


@router.get("/media-settings", dependencies=[Depends(require_web_token)])
async def media_settings():
    settings = _load_settings()
    settings["storage_path"] = str(MEDIA_DIR)
    settings["storage_bytes"] = sum(p.stat().st_size for p in MEDIA_DIR.rglob("*") if p.is_file())
    settings["storage_files"] = sum(1 for p in MEDIA_DIR.rglob("*") if p.is_file() and p.name != SETTINGS_FILE.name)
    return settings


@router.put("/media-settings", dependencies=[Depends(require_web_token)])
async def update_media_settings(data: dict):
    current = _load_settings()
    mode = data.get("download_mode", current["download_mode"])
    if mode not in ("open", "all"):
        raise HTTPException(400, "download_mode must be open or all")
    ttl = int(data.get("ttl_hours", current["ttl_hours"]))
    if ttl < 1 or ttl > 720:
        raise HTTPException(400, "ttl_hours must be between 1 and 720")
    excluded = data.get("excluded_peers", current["excluded_peers"])
    if not isinstance(excluded, list):
        raise HTTPException(400, "excluded_peers must be a list")
    return _save_settings({
        "download_mode": mode,
        "auto_download": bool(data.get("auto_download", current["auto_download"])),
        "excluded_peers": excluded,
        "ttl_hours": ttl,
        "auto_cleanup": bool(data.get("auto_cleanup", current["auto_cleanup"])),
    })


@router.delete("/media-cache", dependencies=[Depends(require_web_token)])
async def delete_media_cache():
    removed = 0
    for path in list(MEDIA_DIR.rglob("*")):
        if path.is_file() and path != SETTINGS_FILE:
            try:
                path.unlink()
                removed += 1
            except Exception:
                pass
    for path in sorted(MEDIA_DIR.rglob("*"), reverse=True):
        if path.is_dir() and path != MEDIA_DIR:
            try:
                path.rmdir()
            except OSError:
                pass
    return {"success": True, "removed_files": removed}


async def cleanup_media_cache():
    settings = _load_settings()
    if not settings.get("auto_cleanup", True):
        return
    cutoff = asyncio.get_running_loop().time() - int(settings.get("ttl_hours", 24)) * 3600
    # pathlib timestamps use epoch seconds; loop.time() does not, so use time.time().
    import time
    cutoff = time.time() - int(settings.get("ttl_hours", 24)) * 3600
    for path in list(MEDIA_DIR.rglob("*")):
        if not path.is_file() or path == SETTINGS_FILE:
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except Exception:
            pass


async def _download_all_recent():
    settings = _load_settings()
    if not settings.get("auto_download") or settings.get("download_mode") != "all":
        return
    if not await bot.is_authorized():
        return
    try:
        dialogs = await bot.client.get_dialogs(limit=100)
        excluded = set(settings.get("excluded_peers", []))
        for dialog in dialogs:
            peer = getattr(dialog, "entity", None)
            peer_key = str(getattr(peer, "username", None) or getattr(peer, "id", ""))
            if not peer_key or peer_key in excluded:
                continue
            try:
                messages = await bot.client.get_messages(peer, limit=30)
                for message in messages:
                    if message.media:
                        await _download_to_cache(peer_key, message)
            except Exception:
                bot.logger.exception("Background media download failed peer=%s", peer_key)
    except Exception:
        bot.logger.exception("Background media download failed")


async def media_cache_worker():
    while True:
        try:
            await cleanup_media_cache()
            await _download_all_recent()
        except asyncio.CancelledError:
            raise
        except Exception:
            bot.logger.exception("Media cache worker error")
        await asyncio.sleep(300)


@router.get("/media-messages", dependencies=[Depends(require_web_token)])
async def media_messages(peer: str, limit: int = 50, offset_id: int = 0):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")
    try:
        kwargs = {"limit": max(1, min(int(limit), 200))}
        if offset_id:
            kwargs["offset_id"] = int(offset_id)
        messages = await bot.client.get_messages(_peer(peer), **kwargs)
        return [_message_json(m) for m in messages]
    except Exception as exc:
        bot.logger.exception("Web media messages error peer=%s", peer)
        raise HTTPException(400, str(exc)) from exc


@router.post("/read", dependencies=[Depends(require_web_token)])
async def mark_read(data: dict):
    """Mark a dialog as read, like opening it in a real Telegram client."""
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")
    peer = data.get("peer")
    if peer is None or not str(peer).strip():
        raise HTTPException(400, "peer is required")
    try:
        entity = await bot.client.get_entity(_peer(peer))
        kwargs = {}
        max_id = data.get("max_id")
        if max_id:
            kwargs["max_id"] = int(max_id)
        await bot.client.send_read_acknowledge(entity, **kwargs)
        return {"success": True}
    except Exception as exc:
        bot.logger.exception("Web read ack error peer=%s", peer)
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
        return {"success": True, "id": message.id, "date": message.date.isoformat() if message.date else None}
    except Exception as exc:
        bot.logger.exception("Web send text error peer=%s", peer)
        raise HTTPException(400, str(exc)) from exc


@router.post("/send_file", dependencies=[Depends(require_web_token)])
async def send_file(dialog_id: str = Form(...), file: UploadFile = File(...), caption: str = Form(default="")):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")
    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="tg-upload-"))
    filename = Path(file.filename or "attachment").name
    target = temp_dir / filename
    try:
        with target.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        if target.stat().st_size <= 0:
            raise HTTPException(400, "Uploaded file is empty")
        message = await bot.client.send_file(_peer(dialog_id), str(target), caption=caption.strip() or None)
        return {"success": True, "id": message.id, "date": message.date.isoformat() if message.date else None, "filename": filename}
    except HTTPException:
        raise
    except Exception as exc:
        bot.logger.exception("Web send file error peer=%s file=%s", dialog_id, filename)
        raise HTTPException(400, str(exc)) from exc
    finally:
        try:
            for child in temp_dir.iterdir():
                child.unlink(missing_ok=True)
            temp_dir.rmdir()
        except Exception:
            pass


@router.get("/avatar/{peer}", dependencies=[Depends(require_web_token)])
async def avatar(peer: str):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")
    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="tg-avatar-"))
    try:
        entity = await bot.client.get_me() if peer == "me" else await bot.client.get_entity(_peer(peer))
        path = await bot.client.download_profile_photo(entity, file=str(temp_dir / "avatar"))
        if not path:
            raise HTTPException(404, "Avatar not found")
        mime = mimetypes.guess_type(path)[0] or "image/jpeg"
        return FileResponse(path, media_type=mime, filename=Path(path).name)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/thumb/{peer}/{message_id}", dependencies=[Depends(require_web_token)])
async def thumb(peer: str, message_id: int):
    """Small preview image for videos/documents (Telegram already stores it)."""
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")
    settings = _load_settings()
    if _excluded(peer, settings):
        raise HTTPException(403, "Этот чат исключён из скачивания вложений")
    try:
        entity = _peer(peer)
        message = await bot.client.get_messages(entity, ids=message_id)
        if not message or not message.media:
            raise HTTPException(404, "Media not found")
        folder = MEDIA_DIR / _account_peer_key(peer)
        folder.mkdir(parents=True, exist_ok=True)
        cached = next(iter(folder.glob(f"{int(message_id)}_thumb*")), None)
        if cached and cached.exists() and cached.stat().st_size > 0:
            return FileResponse(
                cached,
                media_type=mimetypes.guess_type(cached.name)[0] or "image/jpeg",
                headers={"Cache-Control": "private, max-age=86400"},
            )
        target = folder / f"{int(message_id)}_thumb"
        path = await bot.client.download_media(message, file=str(target), thumb=-1)
        if not path or not Path(path).exists():
            raise HTTPException(404, "Thumbnail not found")
        return FileResponse(
            path,
            media_type=mimetypes.guess_type(str(path))[0] or "image/jpeg",
            filename=Path(path).name,
            headers={"Cache-Control": "private, max-age=86400"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/media/{peer}/{message_id}", dependencies=[Depends(require_web_token)])
async def media(peer: str, message_id: int):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")
    settings = _load_settings()
    if _excluded(peer, settings):
        raise HTTPException(403, "Этот чат исключён из скачивания вложений")
    try:
        entity = _peer(peer)
        message = await bot.client.get_messages(entity, ids=message_id)
        if not message or not message.media:
            raise HTTPException(404, "Media not found")
        path = await _download_to_cache(peer, message)
        if not path or not path.exists():
            raise HTTPException(404, "Media download failed")
        mime = getattr(getattr(message, "file", None), "mime_type", None) or mimetypes.guess_type(path)[0] or "application/octet-stream"
        filename = getattr(getattr(message, "file", None), "name", None) or path.name
        return FileResponse(
            path,
            media_type=mime,
            filename=filename,
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
