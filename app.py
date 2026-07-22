from fastapi import FastAPI

from api import router


app = FastAPI(
    title="Telegram API",
    version="1.0"
)


app.include_router(router)
