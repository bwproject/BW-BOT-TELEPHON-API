import asyncio
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from api import router, web_router
from web_media import router as web_media_router
import bot
import console_auth

TELEGRAM_SERVERS = [
    ("149.154.167.51", 443),
    ("149.154.167.50", 443),
    ("149.154.167.91", 443),
    ("149.154.175.100", 443),
]

BASE_DIR = Path(__file__).resolve().parent
WEB_HTML = BASE_DIR / "web" / "index.html"


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
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            delay = round(time.time() - start, 3)
            print(f"OK {host}:{port} ({delay}s)")
            success = True
        except Exception as e:
            print(f"FAIL {host}:{port} -> {e}")
    print("=" * 40)
    print("Telegram TCP connection available" if success else "WARNING: Telegram TCP unavailable")
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
    console_task = asyncio.create_task(console_auth.console_loop())
    try:
        yield
    finally:
        console_task.cancel()
        try:
            await console_task
        except asyncio.CancelledError:
            pass
        print("Stopping Telegram bot...")
        await bot.stop_bot()


app = FastAPI(
    title="Telegram API",
    version="1.0",
    lifespan=lifespan,
)


@app.get("/telegramweb", include_in_schema=False)
async def telegram_web():
    if not WEB_HTML.exists():
        return {"ok": False, "error": "web/index.html not found"}
    return FileResponse(WEB_HTML, media_type="text/html; charset=utf-8")


@app.get("/telegramweb/", include_in_schema=False)
async def telegram_web_slash():
    return await telegram_web()


app.include_router(router)
app.include_router(web_router)
app.include_router(web_media_router)
