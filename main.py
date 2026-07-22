#main.py

import os
import sys
import asyncio
import socket
import time
import uvicorn


from dotenv import load_dotenv


from app import app
import bot



# ==========================
# ENV
# ==========================

load_dotenv()



HOST = os.getenv(
    "HOST",
    "0.0.0.0"
)


PORT = int(
    os.getenv(
        "PORT",
        "8000"
    )
)



# Telegram DC
TELEGRAM_HOST = "149.154.167.51"
TELEGRAM_PORT = 443





# ==========================
# Network check
# ==========================


def check_telegram_network():


    print("=" * 40)
    print("Telegram network check")
    print("=" * 40)



    # DNS

    try:

        ip = socket.gethostbyname(
            "telegram.org"
        )


        print(
            f"DNS telegram.org OK: {ip}"
        )


    except Exception as e:


        print(
            f"DNS ERROR: {e}"
        )



    # TCP Telegram DC

    print(
        f"Testing {TELEGRAM_HOST}:{TELEGRAM_PORT}"
    )


    start = time.time()



    try:


        sock = socket.create_connection(

            (
                TELEGRAM_HOST,
                TELEGRAM_PORT
            ),

            timeout=5

        )


        sock.close()



        delay = round(
            time.time() - start,
            3
        )


        print(
            f"TCP Telegram OK ({delay}s)"
        )



    except Exception as e:


        print(
            f"TCP Telegram FAILED: {e}"
        )





# ==========================
# Startup
# ==========================


async def startup():


    print("=" * 40)

    print(
        "Telegram API starting"
    )

    print(
        f"Server: {HOST}:{PORT}"
    )

    print("=" * 40)



    check_telegram_network()



    print("=" * 40)
    print(
        "Starting Telethon..."
    )
    print("=" * 40)



    result = await bot.start_bot()



    if result:


        print(
            "Telegram client started"
        )


    else:


        print(
            "Telegram client not connected"
        )


        print(
            "API will continue running"
        )





# ==========================
# Shutdown
# ==========================


async def shutdown():


    await bot.stop_bot()





# ==========================
# Main
# ==========================


if __name__ == "__main__":


    asyncio.run(
        startup()
    )



    try:


        uvicorn.run(

            app,

            host=HOST,

            port=PORT

        )



    finally:


        asyncio.run(
            shutdown()
        )