import os
from pathlib import Path

from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
)


load_dotenv()


API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

SESSION_NAME = os.getenv(
    "SESSION_NAME",
    "sessions/account"
)


# создаем папку для session
Path(SESSION_NAME).parent.mkdir(
    parents=True,
    exist_ok=True
)


client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH
)


# временное хранение hash кода
login_data = {}



async def connect():

    if not client.is_connected():
        await client.connect()



async def disconnect():

    if client.is_connected():
        await client.disconnect()



async def is_authorized():

    await connect()

    return await client.is_user_authorized()



async def send_code(phone):

    await connect()

    result = await client.send_code_request(
        phone
    )

    login_data["phone"] = phone
    login_data["hash"] = result.phone_code_hash


    return {
        "status": "code_sent",
        "phone_code_hash": result.phone_code_hash
    }



async def sign_in(code):

    await connect()

    phone = login_data.get("phone")
    phone_hash = login_data.get("hash")


    if not phone:
        return {
            "error": "send code first"
        }


    try:

        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=phone_hash
        )


        return {
            "success": True
        }


    except SessionPasswordNeededError:

        return {
            "success": False,
            "password_required": True
        }


    except PhoneCodeInvalidError:

        return {
            "success": False,
            "error": "invalid_code"
        }


    except PhoneCodeExpiredError:

        return {
            "success": False,
            "error": "code_expired"
        }



async def password(password):

    await connect()

    await client.sign_in(
        password=password
    )


    return {
        "success": True
    }
# ==========================
# Account info
# ==========================


async def get_me():

    await connect()

    user = await client.get_me()

    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "phone": user.phone,
    }



# ==========================
# Dialogs
# ==========================


async def get_dialogs(limit=50):

    await connect()

    result = []


    async for dialog in client.iter_dialogs(
        limit=limit
    ):

        entity = dialog.entity


        result.append({

            "id": dialog.id,

            "name": dialog.name,

            "username": getattr(
                entity,
                "username",
                None
            ),

            "unread": dialog.unread_count,

            "type": entity.__class__.__name__

        })


    return result



# ==========================
# Messages
# ==========================


async def get_messages(
        peer,
        limit=20
):

    await connect()


    messages = []


    async for message in client.iter_messages(
        peer,
        limit=limit
    ):


        messages.append({

            "id": message.id,

            "text": message.text,

            "date": str(
                message.date
            ),

            "sender_id": message.sender_id,

            "out": message.out

        })


    return messages



# ==========================
# Send message
# ==========================


async def send_message(
        peer,
        text
):

    await connect()


    message = await client.send_message(
        peer,
        text
    )


    return {

        "success": True,

        "id": message.id,

        "date": str(
            message.date
        )

    }



# ==========================
# Edit message
# ==========================


async def edit_message(
        peer,
        message_id,
        text
):

    await connect()


    message = await client.edit_message(
        peer,
        message_id,
        text
    )


    return {

        "success": True,

        "id": message.id

    }



# ==========================
# Delete message
# ==========================


async def delete_message(
        peer,
        message_id
):

    await connect()


    await client.delete_messages(
        peer,
        message_id
    )


    return {

        "success": True

    }
# ==========================
# Upload file
# ==========================


async def send_file(
        peer,
        file_path,
        caption=None
):

    await connect()


    message = await client.send_file(
        peer,
        file_path,
        caption=caption
    )


    return {

        "success": True,

        "id": message.id

    }



# ==========================
# Download media
# ==========================


async def download_media(
        peer,
        message_id,
        folder="downloads"
):

    await connect()


    Path(folder).mkdir(
        parents=True,
        exist_ok=True
    )


    message = await client.get_messages(
        peer,
        ids=message_id
    )


    if not message:
        return {
            "success": False,
            "error": "message_not_found"
        }


    if not message.media:

        return {
            "success": False,
            "error": "no_media"
        }



    file = await client.download_media(
        message,
        file=folder
    )


    return {

        "success": True,

        "file": file

    }



# ==========================
# Forward message
# ==========================


async def forward_message(
        from_peer,
        message_id,
        to_peer
):

    await connect()


    result = await client.forward_messages(

        to_peer,

        message_id,

        from_peer

    )


    return {

        "success": True,

        "id": result.id

    }



# ==========================
# Search dialogs
# ==========================


async def search_dialogs(
        query,
        limit=20
):

    await connect()


    result = []


    async for dialog in client.iter_dialogs():

        name = dialog.name or ""


        if query.lower() in name.lower():

            result.append({

                "id": dialog.id,

                "name": dialog.name,

                "username": getattr(
                    dialog.entity,
                    "username",
                    None
                )

            })


        if len(result) >= limit:
            break


    return result



# ==========================
# Join channel/group
# ==========================


async def join_channel(
        username
):

    await connect()


    entity = await client.get_entity(
        username
    )


    await client.join_channel(
        entity
    )


    return {

        "success": True

    }



# ==========================
# Leave channel/group
# ==========================


async def leave_channel(
        username
):

    await connect()


    entity = await client.get_entity(
        username
    )


    await client.delete_dialog(
        entity
    )


    return {

        "success": True

    }
# ==========================
# Telegram auth command
# ==========================

from telethon import events



auth_state = {}



@client.on(
    events.NewMessage(
        pattern="/auth"
    )
)
async def auth_command(event):

    if await client.is_user_authorized():

        await event.reply(
            "✅ Telegram уже авторизован"
        )

        return


    auth_state["chat_id"] = event.chat_id


    await event.reply(
        "Введите номер телефона:\n"
        "Пример: +79999999999"
    )


    auth_state["step"] = "phone"




@client.on(
    events.NewMessage
)
async def auth_messages(event):


    # пропускаем команды
    if event.text.startswith("/"):

        return



    if "step" not in auth_state:

        return



    step = auth_state["step"]



    # ----------------------
    # Phone
    # ----------------------

    if step == "phone":


        phone = event.text.strip()


        result = await send_code(
            phone
        )


        auth_state["step"] = "code"


        await event.reply(
            "📩 Код отправлен.\n"
            "Введите код из Telegram"
        )


        return



    # ----------------------
    # Code
    # ----------------------

    if step == "code":


        result = await sign_in(
            event.text.strip()
        )


        if result.get(
            "password_required"
        ):


            auth_state["step"] = "password"


            await event.reply(
                "🔐 Введите пароль 2FA"
            )


            return



        if result.get(
            "success"
        ):


            auth_state.clear()


            await event.reply(
                "✅ Авторизация успешна"
            )


        else:

            await event.reply(
                f"❌ Ошибка: {result}"
            )


        return



    # ----------------------
    # Password
    # ----------------------

    if step == "password":


        await password(
            event.text.strip()
        )


        auth_state.clear()


        await event.reply(
            "✅ Авторизация завершена"
        )




# ==========================
# Startup
# ==========================


async def start_bot():

    await connect()


    if await client.is_user_authorized():

        print(
            "Telegram: authorized"
        )

    else:

        print(
            "Telegram: need login"
        )




async def stop_bot():

    await disconnect()
