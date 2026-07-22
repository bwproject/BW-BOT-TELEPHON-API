#bot.py

import os
import sys
import logging
from pathlib import Path


from dotenv import load_dotenv


from telethon import TelegramClient, events
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
)



# ==========================
# ENV
# ==========================

load_dotenv()



API_ID = int(
    os.getenv(
        "API_ID",
        "0"
    )
)


API_HASH = os.getenv(
    "API_HASH",
    ""
)


SESSION_NAME = os.getenv(
    "SESSION_NAME",
    "sessions/account"
)



# ==========================
# Logging
# ==========================


Path("logs").mkdir(
    exist_ok=True
)



logging.basicConfig(

    level=logging.INFO,

    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),

    handlers=[

        logging.StreamHandler(
            sys.stdout
        ),

        logging.FileHandler(
            "logs/telegram.log",
            encoding="utf-8"
        )

    ]

)



logger = logging.getLogger(
    "telegram_api"
)



# ==========================
# Session
# ==========================


Path(
    SESSION_NAME
).parent.mkdir(
    parents=True,
    exist_ok=True
)



logger.info(
    "Loading Telegram client"
)

logger.info(
    "API_ID=%s",
    API_ID
)

logger.info(
    "API_HASH length=%s",
    len(API_HASH)
)

logger.info(
    "SESSION=%s",
    SESSION_NAME
)



# ==========================
# Telethon Client
# ==========================


client = TelegramClient(

    SESSION_NAME,

    API_ID,

    API_HASH,

    timeout=20,

    request_retries=5,

    connection_retries=5

)



# ==========================
# Login storage
# ==========================


login_data = {}



# ==========================
# Connection
# ==========================


async def connect():


    logger.info(
        "Telegram connect requested"
    )


    if client.is_connected():

        logger.info(
            "Already connected"
        )

        return



    try:


        logger.info(
            "Connecting to Telegram MTProto..."
        )


        await client.connect()



        logger.info(
            "Connected=%s",
            client.is_connected()
        )



    except Exception as e:


        logger.exception(
            "Telegram connection failed"
        )


        raise e





async def disconnect():


    logger.info(
        "Disconnect Telegram"
    )


    if client.is_connected():

        await client.disconnect()


        logger.info(
            "Disconnected"
        )



async def is_authorized():


    await connect()


    result = await client.is_user_authorized()


    logger.info(
        "Authorization status=%s",
        result
    )


    return result




# ==========================
# Send login code
# ==========================


async def send_code(phone):


    logger.info(
        "Send auth code to %s",
        phone
    )


    await connect()



    result = await client.send_code_request(
        phone
    )



    login_data["phone"] = phone

    login_data["hash"] = (
        result.phone_code_hash
    )



    logger.info(
        "Auth code sent"
    )



    return {

        "status": "code_sent",

        "phone_code_hash":
            result.phone_code_hash

    }
# ==========================
# Sign in
# ==========================


async def sign_in(code):

    logger.info(
        "Trying sign in with code"
    )


    await connect()


    phone = login_data.get(
        "phone"
    )


    phone_hash = login_data.get(
        "hash"
    )


    if not phone:

        logger.warning(
            "Phone not found. Send code first"
        )

        return {

            "error":
                "send code first"

        }



    try:


        await client.sign_in(

            phone=phone,

            code=code,

            phone_code_hash=phone_hash

        )


        logger.info(
            "Authorization successful"
        )


        return {

            "success":
                True

        }



    except SessionPasswordNeededError:


        logger.warning(
            "Two-factor password required"
        )


        return {

            "success":
                False,

            "password_required":
                True

        }



    except PhoneCodeInvalidError:


        logger.warning(
            "Invalid Telegram code"
        )


        return {

            "success":
                False,

            "error":
                "invalid_code"

        }



    except PhoneCodeExpiredError:


        logger.warning(
            "Telegram code expired"
        )


        return {

            "success":
                False,

            "error":
                "code_expired"

        }



    except Exception as e:


        logger.exception(
            "Sign in error"
        )


        return {

            "success":
                False,

            "error":
                str(e)

        }





# ==========================
# 2FA Password
# ==========================


async def password(password):


    logger.info(
        "Trying 2FA password login"
    )


    await connect()


    try:


        await client.sign_in(
            password=password
        )


        logger.info(
            "2FA authorization successful"
        )


        return {

            "success":
                True

        }



    except Exception as e:


        logger.exception(
            "2FA login error"
        )


        return {

            "success":
                False,

            "error":
                str(e)

        }




# ==========================
# Account info
# ==========================


async def get_me():


    logger.info(
        "Getting account information"
    )


    await connect()


    user = await client.get_me()



    if not user:

        logger.warning(
            "No user returned"
        )


        return None



    result = {


        "id":
            user.id,


        "first_name":
            user.first_name,


        "last_name":
            user.last_name,


        "username":
            user.username,


        "phone":
            user.phone


    }



    logger.info(
        "Current user: %s",
        result
    )


    return result




# ==========================
# Dialogs
# ==========================


async def get_dialogs(limit=50):


    logger.info(
        "Loading dialogs limit=%s",
        limit
    )


    await connect()


    result = []



    async for dialog in client.iter_dialogs(

        limit=limit

    ):


        entity = dialog.entity



        result.append({


            "id":
                dialog.id,


            "name":
                dialog.name,


            "username":
                getattr(

                    entity,

                    "username",

                    None

                ),


            "unread":
                dialog.unread_count,


            "type":
                entity.__class__.__name__


        })



    logger.info(

        "Dialogs loaded: %s",

        len(result)

    )



    return result
# ==========================
# Messages
# ==========================


async def get_messages(
        peer,
        limit=20
):

    logger.info(
        "Loading messages peer=%s limit=%s",
        peer,
        limit
    )


    await connect()



    messages = []



    try:


        async for message in client.iter_messages(

            peer,

            limit=limit

        ):


            messages.append({


                "id":
                    message.id,


                "text":
                    message.text,


                "date":
                    str(
                        message.date
                    ),


                "sender_id":
                    message.sender_id,


                "out":
                    message.out


            })



        logger.info(

            "Messages loaded: %s",

            len(messages)

        )



        return messages



    except Exception as e:


        logger.exception(
            "Get messages error"
        )


        return {

            "error":
                str(e)

        }





# ==========================
# Send message
# ==========================


async def send_message(
        peer,
        text
):


    logger.info(
        "Sending message to %s",
        peer
    )


    await connect()



    try:


        message = await client.send_message(

            peer,

            text

        )



        logger.info(

            "Message sent id=%s",

            message.id

        )



        return {


            "success":
                True,


            "id":
                message.id,


            "date":
                str(
                    message.date
                )


        }



    except Exception as e:


        logger.exception(
            "Send message error"
        )


        return {


            "success":
                False,


            "error":
                str(e)

        }





# ==========================
# Edit message
# ==========================


async def edit_message(
        peer,
        message_id,
        text
):


    logger.info(

        "Edit message peer=%s id=%s",

        peer,

        message_id

    )



    await connect()



    try:


        message = await client.edit_message(

            peer,

            message_id,

            text

        )



        logger.info(

            "Message edited id=%s",

            message.id

        )



        return {


            "success":
                True,


            "id":
                message.id


        }



    except Exception as e:


        logger.exception(
            "Edit message error"
        )


        return {


            "success":
                False,


            "error":
                str(e)

        }





# ==========================
# Delete message
# ==========================


async def delete_message(
        peer,
        message_id
):


    logger.info(

        "Delete message peer=%s id=%s",

        peer,

        message_id

    )



    await connect()



    try:


        await client.delete_messages(

            peer,

            message_id

        )



        logger.info(
            "Message deleted"
        )



        return {


            "success":
                True


        }



    except Exception as e:


        logger.exception(
            "Delete message error"
        )


        return {


            "success":
                False,


            "error":
                str(e)

        }
# ==========================
# Upload file
# ==========================


async def send_file(
        peer,
        file_path,
        caption=None
):

    logger.info(
        "Sending file=%s to=%s",
        file_path,
        peer
    )


    await connect()



    try:


        message = await client.send_file(

            peer,

            file_path,

            caption=caption

        )


        logger.info(

            "File sent id=%s",

            message.id

        )


        return {


            "success":
                True,


            "id":
                message.id


        }



    except Exception as e:


        logger.exception(
            "Send file error"
        )


        return {


            "success":
                False,


            "error":
                str(e)

        }





# ==========================
# Download media
# ==========================


async def download_media(
        peer,
        message_id,
        folder="downloads"
):


    logger.info(

        "Download media peer=%s id=%s",

        peer,

        message_id

    )


    await connect()



    try:


        Path(folder).mkdir(

            parents=True,

            exist_ok=True

        )



        message = await client.get_messages(

            peer,

            ids=message_id

        )



        if not message:


            logger.warning(

                "Message not found"

            )


            return {


                "success":
                    False,


                "error":
                    "message_not_found"


            }



        if not message.media:


            logger.warning(

                "Message has no media"

            )


            return {


                "success":
                    False,


                "error":
                    "no_media"


            }



        file = await client.download_media(

            message,

            file=folder

        )



        logger.info(

            "Media downloaded: %s",

            file

        )



        return {


            "success":
                True,


            "file":
                file


        }



    except Exception as e:


        logger.exception(
            "Download media error"
        )


        return {


            "success":
                False,


            "error":
                str(e)

        }





# ==========================
# Forward message
# ==========================


async def forward_message(
        from_peer,
        message_id,
        to_peer
):


    logger.info(

        "Forward message %s -> %s",

        from_peer,

        to_peer

    )



    await connect()



    try:


        result = await client.forward_messages(

            to_peer,

            message_id,

            from_peer

        )



        logger.info(

            "Message forwarded id=%s",

            result.id

        )



        return {


            "success":
                True,


            "id":
                result.id


        }



    except Exception as e:


        logger.exception(

            "Forward error"

        )


        return {


            "success":
                False,


            "error":
                str(e)

        }





# ==========================
# Search dialogs
# ==========================


async def search_dialogs(
        query,
        limit=20
):


    logger.info(

        "Search dialogs query=%s",

        query

    )



    await connect()



    result = []



    async for dialog in client.iter_dialogs():


        name = dialog.name or ""



        if query.lower() in name.lower():


            result.append({


                "id":
                    dialog.id,


                "name":
                    dialog.name,


                "username":
                    getattr(

                        dialog.entity,

                        "username",

                        None

                    )


            })



        if len(result) >= limit:

            break



    logger.info(

        "Search result count=%s",

        len(result)

    )


    return result





# ==========================
# Join channel
# ==========================


async def join_channel(
        username
):


    logger.info(

        "Join channel %s",

        username

    )



    await connect()



    entity = await client.get_entity(

        username

    )


    await client.join_channel(

        entity

    )


    logger.info(

        "Joined channel %s",

        username

    )



    return {


        "success":
            True

    }





# ==========================
# Leave channel
# ==========================


async def leave_channel(
        username
):


    logger.info(

        "Leave channel %s",

        username

    )



    await connect()



    entity = await client.get_entity(

        username

    )



    await client.delete_dialog(

        entity

    )


    logger.info(

        "Left channel %s",

        username

    )



    return {


        "success":
            True

    }
# ==========================
# Telegram auth command
# ==========================


auth_state = {}



@client.on(
    events.NewMessage(
        pattern="/auth"
    )
)
async def auth_command(event):


    logger.info(
        "Auth command from %s",
        event.sender_id
    )



    if await client.is_user_authorized():


        await event.reply(
            "✅ Telegram уже авторизован"
        )


        return



    auth_state.clear()


    auth_state["chat_id"] = (
        event.chat_id
    )


    auth_state["step"] = (
        "phone"
    )



    await event.reply(
        "Введите номер телефона:\n"
        "Пример: +79999999999"
    )





@client.on(
    events.NewMessage
)
async def auth_messages(event):


    text = event.text


    if not text:

        return



    # команды пропускаем

    if text.startswith("/"):

        return



    if "step" not in auth_state:

        return



    step = auth_state["step"]



    # ======================
    # Phone
    # ======================


    if step == "phone":


        phone = text.strip()



        try:


            await send_code(
                phone
            )


            auth_state["step"] = (
                "code"
            )


            await event.reply(
                "📩 Код отправлен.\n"
                "Введите код из Telegram"
            )


        except Exception as e:


            logger.exception(
                "Send auth code error"
            )


            await event.reply(
                f"❌ Ошибка: {e}"
            )


        return





    # ======================
    # Code
    # ======================


    if step == "code":



        result = await sign_in(

            text.strip()

        )



        if result.get(
            "password_required"
        ):


            auth_state["step"] = (
                "password"
            )


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






    # ======================
    # Password
    # ======================


    if step == "password":



        result = await password(

            text.strip()

        )



        if result.get(
            "success"
        ):


            auth_state.clear()



            await event.reply(
                "✅ Авторизация завершена"
            )


        else:


            await event.reply(
                f"❌ Ошибка: {result}"
            )



        return







# ==========================
# Startup
# ==========================


async def start_bot():


    logger.info(
        "========== START BOT =========="
    )



    try:


        await connect()



        authorized = (
            await client.is_user_authorized()
        )



        if authorized:


            logger.info(
                "Telegram account authorized"
            )


        else:


            logger.warning(
                "Telegram account NOT authorized"
            )



    except Exception as e:


        logger.exception(
            "Bot startup failed"
        )


        # Не падаем полностью
        # API продолжит работать


        return False



    return True






# ==========================
# Shutdown
# ==========================


async def stop_bot():


    logger.info(
        "Stopping Telegram bot"
    )


    try:


        await disconnect()


    except Exception as e:


        logger.exception(
            "Shutdown error"
        )
