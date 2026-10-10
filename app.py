import asyncio
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from api import router, web_router
from web_media import router as web_media_router, media_cache_worker
from presence_api import router as presence_router
import bot
import console_auth
import multi_accounts

TELEGRAM_SERVERS = [
    ("149.154.167.51", 443),
    ("149.154.167.50", 443),
    ("149.154.167.91", 443),
    ("149.154.175.100", 443),
]

BASE_DIR = Path(__file__).resolve().parent
WEB_HTML = BASE_DIR / "web" / "index.html"
WEB_MOBILE_JS = BASE_DIR / "web" / "mobile.js"
WEB_SETTINGS_JS = BASE_DIR / "web" / "settings.js"


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
    result = await multi_accounts.start_default()
    if result:
        print("Telegram client started")
    else:
        print("Telegram client not connected")
        print("API will continue running")
    console_task = asyncio.create_task(console_auth.console_loop())
    media_task = asyncio.create_task(media_cache_worker())
    try:
        yield
    finally:
        console_task.cancel()
        media_task.cancel()
        for task in (console_task, media_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        print("Stopping Telegram clients...")
        await bot.stop_bot()
        await multi_accounts.manager.close()


app = FastAPI(title="Telegram API", version="1.1", lifespan=lifespan)


@app.middleware("http")
async def select_telegram_account(request: Request, call_next):
    account_id = request.headers.get("X-Telegram-Account", multi_accounts.DEFAULT_ACCOUNT_ID)
    try:
        token = multi_accounts.set_active_account(account_id)
    except (KeyError, ValueError):
        return JSONResponse({"detail": "Telegram account not found"}, status_code=404)
    try:
        return await call_next(request)
    finally:
        multi_accounts.reset_active_account(token)


@app.get("/telegramweb", include_in_schema=False)
async def telegram_web():
    if not WEB_HTML.exists():
        return {"ok": False, "error": "web/index.html not found"}
    html = WEB_HTML.read_text(encoding="utf-8")
    scripts = []
    if WEB_MOBILE_JS.exists():
        scripts.append(WEB_MOBILE_JS.read_text(encoding="utf-8"))
    if WEB_SETTINGS_JS.exists():
        scripts.append(WEB_SETTINGS_JS.read_text(encoding="utf-8"))
    if scripts:
        tag = "<script>\n" + "\n".join(scripts) + "\n</script>"
        html = html.replace("</body>", tag + "\n</body>", 1) if "</body>" in html else html + tag
    return HTMLResponse(html, media_type="text/html; charset=utf-8")


@app.get("/telegramweb/", include_in_schema=False)
async def telegram_web_slash():
    return await telegram_web()


@app.get("/telegramweb/mobile.js", include_in_schema=False)
async def telegram_web_mobile_js():
    if not WEB_MOBILE_JS.exists():
        return {"ok": False, "error": "web/mobile.js not found"}
    return FileResponse(WEB_MOBILE_JS, media_type="application/javascript; charset=utf-8")


@app.get("/telegramweb/settings.js", include_in_schema=False)
async def telegram_web_settings_js():
    if not WEB_SETTINGS_JS.exists():
        return {"ok": False, "error": "web/settings.js not found"}
    return FileResponse(WEB_SETTINGS_JS, media_type="application/javascript; charset=utf-8")


app.include_router(router)
app.include_router(web_router)
app.include_router(web_media_router)
app.include_router(presence_router)
