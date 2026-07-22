from fastapi import FastAPI

from api import router

app = FastAPI(
    title="Telegram API",
    version="1.0"
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
