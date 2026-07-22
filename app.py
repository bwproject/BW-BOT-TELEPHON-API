import socket
import time

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import router

import bot


TELEGRAM_SERVERS = [
    ("149.154.167.51", 443),
    ("149.154.167.50", 443),
    ("149.154.167.91", 443),
    ("149.154.175.100", 443),
]


def check_telegram_network():
    print("=" * 40)
    print("Telegram network check")
    print("=" * 40)

    try:
        ip = socket.gethostbyname("telegram.org")
        print(f"DNS telegram.org OK: {ip}")
    except Exception as e:
        print(f"DNS ERROR: {e}")

    print("-" * 40)
    print("Testing Telegram DC servers")

    success = False

    for host, port in TELEGRAM_SERVERS:
        start = time.time()
        try:
            sock = socket.create_connection(
                (host, port), timeout=5
            )
            sock.close()
            delay = round(time.time() - start, 3)
            print(f"OK {host}:{port} ({delay}s)")
            success = True
        except Exception as e:
            print(f"FAIL {host}:{port} -> {e}")

    print("=" * 40)

    if success:
        print("Telegram TCP connection available")
    else:
        print("WARNING: Telegram TCP unavailable")

    print("=" * 40)
    return success


@asynccontextmanager
async def lifespan(app_instance):
    print("=" * 40)
    print("Telegram API starting")
    print("=" * 40)

    check_telegram_network()

    result = await bot.start_bot()

    if result:
        print("Telegram client started")
    else:
        print("Telegram client not connected")
        print("API will continue running")

    yield

    print("Stopping Telegram bot...")
    await bot.stop_bot()


app = FastAPI(
    title="Telegram API",
    version="1.0",
    lifespan=lifespan
)


app.include_router(router)
