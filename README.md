📱 BW Telegram Telethon API

REST API сервис для управления Telegram аккаунтом через MTProto.

Проект построен на:

* 🐍 Python
* 📡 Telethon
* ⚡ FastAPI
* 🔐 Session авторизации Telegram

Сервис позволяет авторизовать обычный Telegram аккаунт и использовать его возможности через HTTP API из других Python-проектов.

⸻

🚀 Возможности

🔐 Авторизация Telegram

Поддерживается:

* отправка кода авторизации;
* вход по коду Telegram;
* поддержка двухфакторного пароля;
* сохранение session-файла;
* повторный запуск без повторного входа.

Авторизация доступна:

* через REST API;
* через Telegram команду /auth.

⸻

📂 Структура проекта

BW-BOT-TELEPHON-API/
├── main.py              # Запуск FastAPI сервера
├── api.py               # HTTP API маршруты
├── bot.py               # Telethon клиент
│
├── .env                 # Настройки
├── requirements.txt     # Зависимости
│
├── sessions/
│   └── account.session  # Telegram авторизация
│
└── downloads/           # Загруженные файлы

⸻

⚙️ Установка

1. Клонирование

git clone https://github.com/bwproject/BW-BOT-TELEPHON-API.git
cd BW-BOT-TELEPHON-API

⸻

2. Установка зависимостей

pip install -r requirements.txt

⸻

3. Настройка .env

Создать файл:

.env

Пример:

API_ID=12345678
API_HASH=xxxxxxxxxxxxxxxxxxxx
PHONE=+70000000000
SESSION_NAME=sessions/account
HOST=0.0.0.0
PORT=8000
API_TOKEN=

⸻

🔑 Получение API_ID и API_HASH

Перейдите:

https://my.telegram.org

Создайте приложение Telegram API.

Полученные данные:

API_ID
API_HASH

укажите в .env.

⸻

▶️ Запуск

python main.py

После запуска:

Telegram API starting
Server:
0.0.0.0:8000
Telegram:
❌ Need login

или:

Telegram:
✅ Authorized

⸻

🌐 Swagger документация

После запуска открыть:

http://SERVER_IP:8000/docs

FastAPI автоматически создаст интерактивную документацию API.

⸻

🔐 Авторизация через API

Отправить код

POST /auth/send_code

JSON:

{
    "phone":"+70000000000"
}

⸻

Ввести код

POST /auth/sign_in

JSON:

{
    "code":"12345"
}

⸻

Ввести пароль 2FA

POST /auth/password

JSON:

{
    "password":"password"
}

⸻

Проверка авторизации

GET /auth/status

Ответ:

{
    "authorized":true
}

⸻

👤 Информация об аккаунте

GET /me

Ответ:

{
    "id":123456,
    "first_name":"User",
    "username":"username"
}

⸻

💬 Сообщения

Получить сообщения

GET /messages?peer=@username&limit=20

⸻

Отправить сообщение

POST /send

JSON:

{
    "peer":"@username",
    "text":"Привет!"
}

⸻

Редактировать сообщение

POST /edit

JSON:

{
    "peer":"@username",
    "message_id":10,
    "text":"Новое сообщение"
}

⸻

Удалить сообщение

POST /delete

JSON:

{
    "peer":"@username",
    "message_id":10
}

⸻

📁 Работа с файлами

Отправить файл

POST /upload

JSON:

{
    "peer":"@username",
    "file_path":"photo.jpg",
    "caption":"Фото"
}

⸻

Скачать медиа

POST /download

JSON:

{
    "peer":"@username",
    "message_id":15
}

⸻

🔄 Пересылка сообщений

POST /forward

JSON:

{
    "from_peer":"@source",
    "message_id":15,
    "to_peer":"@target"
}

⸻

📢 Каналы и группы

Вступить

POST /join

JSON:

{
    "username":"@channel"
}

⸻

Покинуть

POST /leave

JSON:

{
    "username":"@channel"
}

⸻

🤖 Авторизация через Telegram

Отправьте аккаунту:

/auth

Дальше:

1. Введите номер телефона.
2. Получите код Telegram.
3. Введите код.
4. Если включена 2FA — введите пароль.

После успешного входа:

✅ Авторизация завершена

⸻

🐍 Использование из другого Python проекта

Пример:

import requests
requests.post(
    "http://127.0.0.1:8000/send",
    json={
        "peer":"@username",
        "text":"Сообщение отправлено через API"
    }
)

⸻

🛡️ Безопасность

Рекомендуется:

* не публиковать .env;
* не передавать session-файл третьим лицам;
* использовать API_TOKEN при открытии сервиса наружу;
* запускать API за Nginx/Caddy при использовании через интернет.

⸻

🛠️ Планы развития

Возможные улучшения:

* WebSocket события новых сообщений;
* несколько Telegram аккаунтов;
* очередь сообщений;
* обработка FloodWait;
* Docker Compose;
* Web UI управление аккаунтом;
* webhook события.

⸻

📜 License

MIT License
