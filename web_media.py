import asyncio
import json
import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from fastapi.responses import FileResponse

import bot
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


def _cached_file(peer, message_id):
    folder = MEDIA_DIR / _safe(peer)
    if not folder.exists():
        return None
    matches = list(folder.glob(f"{int(message_id)}_*"))
    return matches[0] if matches else None


def _cache_path(peer, message):
    folder = MEDIA_DIR / _safe(peer)
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
async def media_messages(peer: str, limit: int = 50):
    if not await bot.is_authorized():
        raise HTTPException(401, "Telegram account is not authorized")
    try:
        messages = await bot.client.get_messages(_peer(peer), limit=limit)
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
        return FileResponse(path, media_type=mime, filename=filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
