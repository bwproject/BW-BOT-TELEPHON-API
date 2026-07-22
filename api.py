from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import bot


router = APIRouter(
    prefix="",
    tags=["Telegram"]
)



# ==========================
# Models
# ==========================


class SendCodeRequest(BaseModel):

    phone: str



class SignInRequest(BaseModel):

    code: str



class PasswordRequest(BaseModel):

    password: str



class SendMessageRequest(BaseModel):

    peer: str

    text: str



class EditMessageRequest(BaseModel):

    peer: str

    message_id: int

    text: str



class DeleteMessageRequest(BaseModel):

    peer: str

    message_id: int



class MessagesRequest(BaseModel):

    peer: str

    limit: int = 20



class UploadRequest(BaseModel):

    peer: str

    file_path: str

    caption: str | None = None



class DownloadRequest(BaseModel):

    peer: str

    message_id: int

    folder: str = "downloads"





# ==========================
# Authorization
# ==========================


@router.post(
    "/auth/send_code"
)
async def auth_send_code(
        data: SendCodeRequest
):

    return await bot.send_code(
        data.phone
    )



@router.post(
    "/auth/sign_in"
)
async def auth_sign_in(
        data: SignInRequest
):

    return await bot.sign_in(
        data.code
    )



@router.post(
    "/auth/password"
)
async def auth_password(
        data: PasswordRequest
):

    return await bot.password(
        data.password
    )



@router.get(
    "/auth/status"
)
async def auth_status():

    return {

        "authorized":
            await bot.is_authorized()

    }



# ==========================
# Account
# ==========================


@router.get(
    "/me"
)
async def me():

    return await bot.get_me()



# ==========================
# Dialogs
# ==========================


@router.get(
    "/dialogs"
)
async def dialogs(
        limit: int = 50
):

    return await bot.get_dialogs(
        limit
    )
# ==========================
# Messages
# ==========================


@router.get(
    "/messages"
)
async def messages(
        peer: str,
        limit: int = 20
):

    return await bot.get_messages(
        peer,
        limit
    )



# ==========================
# Send message
# ==========================


@router.post(
    "/send"
)
async def send_message(
        data: SendMessageRequest
):

    return await bot.send_message(
        data.peer,
        data.text
    )



# ==========================
# Edit message
# ==========================


@router.post(
    "/edit"
)
async def edit_message(
        data: EditMessageRequest
):

    return await bot.edit_message(
        data.peer,
        data.message_id,
        data.text
    )



# ==========================
# Delete message
# ==========================


@router.post(
    "/delete"
)
async def delete_message(
        data: DeleteMessageRequest
):

    return await bot.delete_message(
        data.peer,
        data.message_id
    )



# ==========================
# Upload file
# ==========================


@router.post(
    "/upload"
)
async def upload(
        data: UploadRequest
):

    return await bot.send_file(
        data.peer,
        data.file_path,
        data.caption
    )



# ==========================
# Download media
# ==========================


@router.post(
    "/download"
)
async def download(
        data: DownloadRequest
):

    return await bot.download_media(
        data.peer,
        data.message_id,
        data.folder
    )



# ==========================
# Forward
# ==========================


class ForwardRequest(BaseModel):

    from_peer: str

    message_id: int

    to_peer: str




@router.post(
    "/forward"
)
async def forward(
        data: ForwardRequest
):

    return await bot.forward_message(
        data.from_peer,
        data.message_id,
        data.to_peer
    )



# ==========================
# Search
# ==========================


@router.get(
    "/search"
)
async def search(
        query: str,
        limit: int = 20
):

    return await bot.search_dialogs(
        query,
        limit
    )



# ==========================
# Channels
# ==========================


class ChannelRequest(BaseModel):

    username: str



@router.post(
    "/join"
)
async def join(
        data: ChannelRequest
):

    return await bot.join_channel(
        data.username
    )



@router.post(
    "/leave"
)
async def leave(
        data: ChannelRequest
):

    return await bot.leave_channel(
        data.username
    )
