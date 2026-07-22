#main.py

import os
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





# ==========================
# Telegram DC servers
# ==========================

TELEGRAM_SERVERS = [

    ("149.154.167.51", 443),  # DC4

    ("149.154.167.50", 443),  # DC2

    ("149.154.167.91", 443),  # DC1

    ("149.154.175.100", 443), # DC5

]





# ==========================
# Network check
# ==========================


def check_telegram_network():


    print("=" * 40)

    print(
        "Telegram network check"
    )

    print("=" * 40)



    # DNS check

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



    print("-" * 40)


    print(
        "Testing Telegram DC servers"
    )



    success = False



    for host, port in TELEGRAM_SERVERS:


        start = time.time()



        try:


            sock = socket.create_connection(

                (
                    host,
                    port
                ),

                timeout=5

            )


            sock.close()



            delay = round(

                time.time() - start,

                3

            )



            print(

                f"✅ OK {host}:{port} ({delay}s)"

            )


            success = True



        except Exception as e:


            print(

                f"❌ FAIL {host}:{port} -> {e}"

            )



    print("=" * 40)



    if success:


        print(
            "Telegram TCP connection available"
        )


    else:


        print(
            "WARNING: Telegram TCP unavailable"
        )



    print("=" * 40)



    return success







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



    network_ok = check_telegram_network()



    if not network_ok:


        print(
            "⚠️ Telegram network check failed"
        )


        print(
            "Continue startup anyway"
        )



    print("=" * 40)


    print(
        "Starting Telethon..."
    )


    print("=" * 40)



    result = await bot.start_bot()



    if result:


        print(
            "✅ Telegram client started"
        )


    else:


        print(
            "⚠️ Telegram client not connected"
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