import os
import asyncio
import uvicorn

from dotenv import load_dotenv

from app import app
import bot


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



async def startup():

    print("=" * 40)
    print("Telegram API starting")
    print(
        f"Server: {HOST}:{PORT}"
    )
    print("=" * 40)


    await bot.start_bot()



async def shutdown():

    await bot.stop_bot()



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
