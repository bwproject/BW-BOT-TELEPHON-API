import asyncio
from getpass import getpass

import bot


async def login_tg():
    """Interactive Telegram re-authorization from the server console."""
    print("\n" + "=" * 50)
    print("Telegram interactive authorization")
    print("This will re-authorize the session configured by SESSION_NAME.")
    print("=" * 50)

    try:
        await bot.connect()

        # Force a fresh authorization when an old session is already logged in.
        try:
            if await bot.client.is_user_authorized():
                print("Existing Telegram authorization found.")
                print("Logging out old session before re-authorization...")
                await bot.client.log_out()
                await bot.connect()
                print("Old authorization removed.")
        except Exception as e:
            print(f"Warning while resetting old authorization: {e}")

        while True:
            phone = (await asyncio.to_thread(input, "\nВведите номер телефона: ")).strip()
            if phone:
                break
            print("Номер телефона не может быть пустым.")

        result = await bot.send_code(phone)
        if not result.get("success"):
            print(f"❌ Не удалось отправить код: {result.get('error', result)}")
            return False

        while True:
            code = (await asyncio.to_thread(input, "Введите код из Telegram: ")).strip()
            if code:
                break
            print("Код не может быть пустым.")

        result = await bot.sign_in(code)

        if result.get("password_required"):
            while True:
                password = (await asyncio.to_thread(getpass, "Введите пароль 2FA: ")).strip()
                if password:
                    break
                print("Пароль 2FA не может быть пустым.")

            result = await bot.password(password)

        if not result.get("success"):
            print(f"❌ Авторизация не выполнена: {result.get('error', result)}")
            return False

        user = await bot.get_me()

        print("\n" + "=" * 50)
        print("✅ Telegram авторизация успешно завершена")
        print(f"Session: {bot.SESSION_NAME}.session")
        if user:
            name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
            username = user.get("username")
            phone = user.get("phone")
            print(f"Аккаунт: {name or 'Без имени'}")
            if username:
                print(f"Username: @{username}")
            if phone:
                print(f"Phone: +{phone}")
        print("Session сохранена и будет использоваться API.")
        print("=" * 50)
        return True

    except asyncio.CancelledError:
        raise
    except EOFError:
        print("\nConsole input unavailable; interactive authorization disabled.")
        return False
    except KeyboardInterrupt:
        print("\nAuthorization cancelled.")
        return False
    except Exception as e:
        print(f"❌ Ошибка авторизации: {e}")
        return False


async def console_loop():
    """Wait for console commands. Supported command: /logintg."""
    print("Console commands: /logintg")

    while True:
        try:
            command = (await asyncio.to_thread(input, "telegram-api> ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return

        if command == "/logintg":
            await login_tg()
        elif command:
            print("Unknown command. Available: /logintg")
