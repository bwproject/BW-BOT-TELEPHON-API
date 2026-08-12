import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

import bot

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN", "").strip()

router = APIRouter(tags=["Telegram"])


async def require_api_token(authorization: str | None = Header(default=None)):
    if not API_TOKEN:
        raise HTTPException(500, "API_TOKEN is not configured on Telegram API server")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or token.strip() != API_TOKEN:
        raise HTTPException(401, "Invalid API token")
    return True


class SendCodeRequest(BaseModel):
    phone: str

class SignInRequest(BaseModel):
    code: str

class PasswordRequest(BaseModel):
    password: str

class SendMessageRequest(BaseModel):
    peer: str | int
    text: str

class EditMessageRequest(BaseModel):
    peer: str | int
    message_id: int
    text: str

class DeleteMessageRequest(BaseModel):
    peer: str | int
    message_id: int

class DownloadRequest(BaseModel):
    peer: str | int
    message_id: int
    folder: str = "downloads"

class ForwardRequest(BaseModel):
    from_peer: str | int
    message_id: int
    to_peer: str | int

class ChannelRequest(BaseModel):
    username: str


async def account_state():
    connected = await bot.connect()
    authorized = False
    user = None
    if connected:
        authorized = await bot.is_authorized()
        if authorized:
            user = await bot.get_me()
    return connected, authorized, user


@router.get("/status", dependencies=[Depends(require_api_token)])
async def status():
    connected, authorized, user = await account_state()
    return {"ok": True, "connected": connected, "authorized": authorized, "user": user}


@router.post("/start", dependencies=[Depends(require_api_token)])
async def start():
    connected, authorized, user = await account_state()
    return {
        "ok": connected,
        "connected": connected,
        "authorized": authorized,
        "user": user,
        "error": None if connected else "telegram_connection_failed",
    }


@router.post("/logout", dependencies=[Depends(require_api_token)])
async def logout():
    await bot.disconnect()
    return {"ok": True}


@router.get("/auth/status", dependencies=[Depends(require_api_token)])
async def auth_status():
    _, authorized, user = await account_state()
    return {"ok": True, "authorized": authorized, "user": user}


@router.post("/auth/send_code", dependencies=[Depends(require_api_token)])
@router.post("/send_code", dependencies=[Depends(require_api_token)])
async def auth_send_code(data: SendCodeRequest):
    return await bot.send_code(data.phone)


@router.post("/auth/sign_in", dependencies=[Depends(require_api_token)])
@router.post("/sign_in", dependencies=[Depends(require_api_token)])
async def auth_sign_in(data: SignInRequest):
    return await bot.sign_in(data.code)


@router.post("/auth/password", dependencies=[Depends(require_api_token)])
async def auth_password(data: PasswordRequest):
    return await bot.password(data.password)


@router.get("/me", dependencies=[Depends(require_api_token)])
async def me():
    _, authorized, user = await account_state()
    if not authorized or not user:
        raise HTTPException(401, "Telegram account is not authorized")
    return user


@router.get("/dialogs", dependencies=[Depends(require_api_token)])
async def dialogs(limit: int = 100):
    _, authorized, _ = await account_state()
    if not authorized:
        raise HTTPException(401, "Telegram account is not authorized")
    return await bot.get_dialogs(limit)


@router.get("/messages", dependencies=[Depends(require_api_token)])
async def messages(peer: str, limit: int = 50, offset_id: int = 0):
    _, authorized, _ = await account_state()
    if not authorized:
        raise HTTPException(401, "Telegram account is not authorized")
    return await bot.get_messages(peer, limit)


@router.get("/messages/{dialog_id}", dependencies=[Depends(require_api_token)])
async def messages_by_dialog(dialog_id: int, limit: int = 50, offset_id: int = 0):
    _, authorized, _ = await account_state()
    if not authorized:
        raise HTTPException(401, "Telegram account is not authorized")
    return await bot.get_messages(str(dialog_id), limit)


@router.post("/send", dependencies=[Depends(require_api_token)])
async def send_message(data: SendMessageRequest):
    _, authorized, _ = await account_state()
    if not authorized:
        raise HTTPException(401, "Telegram account is not authorized")
    return await bot.send_message(str(data.peer), data.text)


@router.post("/edit", dependencies=[Depends(require_api_token)])
async def edit_message(data: EditMessageRequest):
    return await bot.edit_message(str(data.peer), data.message_id, data.text)


@router.post("/delete", dependencies=[Depends(require_api_token)])
async def delete_message(data: DeleteMessageRequest):
    return await bot.delete_message(str(data.peer), data.message_id)


@router.post("/send_file", dependencies=[Depends(require_api_token)])
@router.post("/upload", dependencies=[Depends(require_api_token)])
async def upload_file(
    dialog_id: str = Form(...),
    file: UploadFile = File(...),
    caption: str | None = Form(default=None),
):
    _, authorized, _ = await account_state()
    if not authorized:
        raise HTTPException(401, "Telegram account is not authorized")

    suffix = Path(file.filename or "file").suffix
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)
        return await bot.send_file(str(dialog_id), temp_path, caption)
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


@router.get("/download/{dialog_id}/{message_id}", dependencies=[Depends(require_api_token)])
async def download_media(dialog_id: int, message_id: int):
    _, authorized, _ = await account_state()
    if not authorized:
        raise HTTPException(401, "Telegram account is not authorized")
    return await bot.download_media(str(dialog_id), message_id, "downloads")


@router.post("/download", dependencies=[Depends(require_api_token)])
async def download(data: DownloadRequest):
    _, authorized, _ = await account_state()
    if not authorized:
        raise HTTPException(401, "Telegram account is not authorized")
    return await bot.download_media(str(data.peer), data.message_id, data.folder)


@router.post("/forward", dependencies=[Depends(require_api_token)])
async def forward(data: ForwardRequest):
    return await bot.forward_message(str(data.from_peer), data.message_id, str(data.to_peer))


@router.get("/search", dependencies=[Depends(require_api_token)])
async def search(query: str, limit: int = 20):
    return await bot.search_dialogs(query, limit)


@router.post("/join", dependencies=[Depends(require_api_token)])
async def join(data: ChannelRequest):
    return await bot.join_channel(data.username)


@router.post("/leave", dependencies=[Depends(require_api_token)])
async def leave(data: ChannelRequest):
    return await bot.leave_channel(data.username)
