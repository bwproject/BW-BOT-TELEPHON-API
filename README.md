# 🚀 BW Telegram Telethon API

**BW Telegram Telethon API** — FastAPI + Telethon сервис для управления авторизованным Telegram-аккаунтом через MTProto и браузерный интерфейс.

Проект рассчитан на работу с **одним авторизованным Telegram session-файлом**. После первичной авторизации аккаунт сохраняется в `sessions/`, поэтому при следующих запусках повторный ввод номера и кода не требуется.

---

## ✨ Возможности

### 👤 Telegram-аккаунт

- Проверка подключения к Telegram.
- Проверка фактического статуса авторизации session-файла.
- Получение информации о текущем аккаунте через `/me`.
- Авторизация по номеру телефона, коду Telegram и 2FA.
- Сохранение авторизации в Telethon `.session`.
- Консольная авторизация через `/logintg` с последовательным вводом номера, кода и пароля 2FA.

### 💬 Диалоги

- Получение списка диалогов.
- Поиск чатов в браузере.
- Личные сообщения.
- Группы.
- Каналы.
- Непрочитанные сообщения.
- Открытие выбранного диалога.
- Автоматическое обновление сообщений.

### 🖼️ Аватарки

В веб-интерфейсе отображаются:

- аватар текущего Telegram-аккаунта;
- аватарки пользователей;
- аватарки групп и каналов.

Аватар загружается через API непосредственно из Telegram.

### 📎 Вложения и медиа

В веб-интерфейсе поддерживаются:

- фотографии;
- видео;
- документы и файлы;
- просмотр изображений прямо в чате;
- воспроизведение видео;
- скачивание вложений;
- отправка файлов из браузера;
- подпись к отправляемому файлу.

### 📨 Сообщения

- получение истории сообщений;
- отправка сообщений;
- отправка файлов;
- автоматическое обновление открытого чата;
- отображение времени сообщений;
- разделение входящих и исходящих сообщений.

### 🌐 Telegram Web

В проект добавлен полноценный браузерный интерфейс.

Открыть его можно напрямую:

```text
http://SERVER_IP:PORT/telegramweb
```

Например, если API работает на порту `1046`:

```text
http://SERVER_IP:1046/telegramweb
```

Интерфейс расположен отдельно от Python-кода:

```text
web/index.html
```

Это позволяет независимо улучшать дизайн и JavaScript интерфейса, не смешивая HTML с FastAPI-логикой.

---

## 🖥️ Telegram Web

После открытия `/telegramweb` пользователь видит страницу входа.

### 1. Вход в Web UI

Используются значения из `.env`:

```env
WEB_USERNAME=admin
WEB_PASSWORD=CHANGE_ME_TO_A_STRONG_PASSWORD
```

После успешного входа браузер получает серверный `API_TOKEN` и использует его для последующих запросов.

### 2. Проверка Telegram

После Web-входа интерфейс автоматически обращается к:

```text
GET /api/telegramweb/tg/status
```

Проверяется:

- доступность Telegram;
- наличие session;
- авторизован ли Telegram-аккаунт;
- информация о текущем пользователе.

Если session не авторизован, интерфейс показывает ошибку вместо ложного сообщения об успешном подключении.

### 3. Работа с чатами

После успешной проверки открывается список диалогов.

Для выбранного чата интерфейс получает историю через:

```text
GET /api/telegramweb/media-messages?peer=...&limit=80
```

Вложения загружаются отдельными запросами, поэтому тяжёлые файлы не передаются вместе со списком сообщений.

---

## 🔐 Авторизация Telegram

### Вариант 1 — консольная авторизация

При запущенном сервисе можно использовать команду:

```text
/logintg
```

Далее консоль последовательно запрашивает:

```text
Номер телефона → код из Telegram → пароль 2FA
```

После успешной авторизации session перезаписывается и сохраняется по пути из `SESSION_NAME`.

Например:

```env
SESSION_NAME=sessions/MesBw
```

создаёт файл:

```text
sessions/MesBw.session
```

### Вариант 2 — REST API

Доступны endpoints для авторизации:

```text
POST /auth/send_code
POST /auth/sign_in
POST /auth/password
GET  /auth/status
```

> Если session уже авторизован, повторная авторизация не требуется.

---

## 📁 Структура проекта

```text
BW-BOT-TELEPHON-API/
│
├── main.py                 # Точка входа
├── app.py                  # FastAPI приложение и lifespan
├── api.py                  # REST API + Telegram Web API
├── bot.py                  # Telethon клиент и Telegram-логика
├── console_auth.py         # Консольная авторизация /logintg
├── web_media.py            # Медиа и аватарки для Web UI
│
├── web/
│   └── index.html          # Современный Telegram Web интерфейс
│
├── sessions/               # Telethon session-файлы
├── downloads/              # Загруженные Telegram-файлы
├── logs/                   # Логи
│
├── .env.rename             # Пример конфигурации
├── .gitignore
└── requirements.txt
```

⚠️ **Никогда не публикуйте содержимое `sessions/` в GitHub.** Session-файл фактически содержит авторизацию Telegram-аккаунта.

---

## ⚙️ Установка

### 1. Клонирование

```bash
git clone https://github.com/bwproject/BW-BOT-TELEPHON-API.git
cd BW-BOT-TELEPHON-API
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Создание `.env`

```bash
cp .env.rename .env
```

Минимальная конфигурация:

```env
API_ID=12345678
API_HASH=your_api_hash_here

PHONE=+70000000000

PROXY=

SESSION_NAME=sessions/MesBw

HOST=0.0.0.0
PORT=1046

API_TOKEN=CHANGE_ME_TO_A_LONG_RANDOM_TOKEN

WEB_USERNAME=admin
WEB_PASSWORD=CHANGE_ME_TO_A_STRONG_PASSWORD
```

---

## 🔧 Переменные окружения

| Переменная | Назначение |
|---|---|
| `API_ID` | Telegram API ID |
| `API_HASH` | Telegram API Hash |
| `PHONE` | Номер телефона для первичной авторизации |
| `PROXY` | Прокси для Telegram MTProto-соединения |
| `SESSION_NAME` | Путь к Telethon session |
| `HOST` | Адрес FastAPI-сервера |
| `PORT` | Порт FastAPI-сервера |
| `API_TOKEN` | Токен защиты REST API |
| `WEB_USERNAME` | Логин Telegram Web |
| `WEB_PASSWORD` | Пароль Telegram Web |

---

## 🌐 Прокси

Если сервер напрямую не может подключиться к Telegram, можно указать прокси в `PROXY`.

Пример SOCKS5:

```env
PROXY=socks5://127.0.0.1:1080
```

SOCKS5 с авторизацией:

```env
PROXY=socks5://user:password@127.0.0.1:1080
```

HTTP:

```env
PROXY=http://127.0.0.1:8080
```

MTProto:

```env
PROXY=mtproto-proxy://149.154.167.50:443#SECRET
```

Если Telegram доступен напрямую, оставьте:

```env
PROXY=
```

---

## ▶️ Запуск

```bash
python main.py
```

При старте сервис:

1. проверяет сетевое соединение с Telegram;
2. запускает Telethon;
3. проверяет session;
4. запускает FastAPI;
5. запускает консольный цикл авторизации.

После запуска:

```text
http://SERVER_IP:1046/telegramweb
```

Swagger:

```text
http://SERVER_IP:1046/docs
```

---

# 🔌 API

## 🔑 Telegram Web API

Все Web endpoints находятся под:

```text
/api/telegramweb
```

### Web Login

```text
POST /api/telegramweb/auth/login
```

Пример:

```json
{
  "username": "admin",
  "password": "your_password"
}
```

Ответ:

```json
{
  "ok": true,
  "token": "..."
}
```

### Проверка Telegram

```text
GET /api/telegramweb/tg/status
```

### Текущий аккаунт

```text
GET /api/telegramweb/me
```

### Диалоги

```text
GET /api/telegramweb/dialogs?limit=100
```

### Сообщения

```text
GET /api/telegramweb/messages?peer=@username&limit=50
```

### Медиа-сообщения

```text
GET /api/telegramweb/media-messages?peer=@username&limit=80
```

### Аватар

```text
GET /api/telegramweb/avatar/{peer}
```

### Медиа

```text
GET /api/telegramweb/media/{peer}/{message_id}
```

### Отправка сообщения

```text
POST /api/telegramweb/send
```

```json
{
  "peer": "@username",
  "text": "Привет!"
}
```

### Отправка файла

```text
POST /api/telegramweb/send_file
```

Используется `multipart/form-data`:

```text
dialog_id=@username
file=<файл>
caption=Описание файла
```

---

# 📡 Основной REST API

Все основные Telegram endpoints также доступны напрямую.

| Метод | Endpoint | Назначение |
|---|---|---|
| `GET` | `/status` | Состояние клиента |
| `POST` | `/start` | Подключение |
| `POST` | `/logout` | Отключение |
| `GET` | `/auth/status` | Статус авторизации |
| `POST` | `/auth/send_code` | Отправить код |
| `POST` | `/auth/sign_in` | Войти по коду |
| `POST` | `/auth/password` | Ввести 2FA |
| `GET` | `/me` | Текущий аккаунт |
| `GET` | `/dialogs` | Диалоги |
| `GET` | `/messages` | Сообщения |
| `POST` | `/send` | Отправить сообщение |
| `POST` | `/send_file` | Отправить файл |
| `GET` | `/download/{dialog_id}/{message_id}` | Скачать медиа |
| `POST` | `/upload` | Загрузить файл |
| `POST` | `/edit` | Редактировать сообщение |
| `POST` | `/delete` | Удалить сообщение |
| `POST` | `/forward` | Переслать сообщение |
| `GET` | `/search` | Поиск диалогов |
| `POST` | `/join` | Вступить в канал/группу |
| `POST` | `/leave` | Покинуть канал/группу |

---

## 🔐 Защита API

Если задан:

```env
API_TOKEN=...
```

API ожидает:

```http
Authorization: Bearer YOUR_API_TOKEN
```

Telegram Web получает этот токен только после успешной проверки:

```env
WEB_USERNAME
WEB_PASSWORD
```

Поэтому `.env` не должен публиковаться в репозитории.

---

## 🐳 Docker

Проект можно запускать в контейнере, если `sessions/` и другие необходимые данные подключены как постоянные volumes.

Главное правило — **не терять каталог `sessions/` при пересоздании контейнера**.

Пример:

```text
./sessions:/app/sessions
./downloads:/app/downloads
./logs:/app/logs
```

---

## 🛡️ Безопасность

Telegram session-файл содержит действующую авторизацию аккаунта.

Никогда не передавайте посторонним:

- `sessions/*.session`;
- `API_HASH`;
- `API_TOKEN`;
- `WEB_PASSWORD`;
- пароль Telegram 2FA.

Рекомендуется:

- использовать длинный случайный `API_TOKEN`;
- использовать сложный `WEB_PASSWORD`;
- не открывать Swagger/API без необходимости;
- ставить сервис за Nginx/Caddy при доступе из интернета;
- ограничивать доступ к порту firewall;
- делать резервную копию session только в защищённом месте.

---

## 🧩 Архитектура

```text
                    ┌─────────────────────┐
                    │     Web Browser      │
                    │  /telegramweb        │
                    └──────────┬──────────┘
                               │
                         Bearer API_TOKEN
                               │
                    ┌──────────▼──────────┐
                    │       FastAPI        │
                    │  /api/telegramweb/* │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │       Telethon      │
                    │       MTProto       │
                    └──────────┬──────────┘
                               │
                         Telegram Servers

                    sessions/MesBw.session
                         ▲
                         │
                  persistent authorization
```

---

## 📝 Примечания

### Session-файл не авторизован

Наличие файла:

```text
sessions/MesBw.session
```

само по себе не гарантирует, что Telegram считает session авторизованной.

Проверка выполняется через Telethon:

```python
await client.is_user_authorized()
```

Если session была создана для другого `API_ID/API_HASH`, повреждена, отозвана или авторизация была завершена в Telegram, потребуется повторный вход через `/logintg`.

### Изменение session

Для повторной авторизации:

```text
/logintg
```

После успешного входа новая session сохраняется в `SESSION_NAME`.

---

## 📄 Лицензия

MIT License.

---

## 🔗 Репозиторий

https://github.com/bwproject/BW-BOT-TELEPHON-API
