# BW Telegram Telethon API

REST API сервис для управления Telegram аккаунтом через MTProto.

## Технологии

- **Python** -- основной язык
- **Telethon** -- MTProto клиент для Telegram
- **FastAPI** -- HTTP API сервер
- **Uvicorn** -- ASGI сервер

## Возможности

### Авторизация Telegram

- Отправка кода авторизации
- Вход по коду
- Поддержка двухфакторной аутентификации (2FA)
- Сохранение session-файла (повторный запуск без повторного входа)
- Авторизация через REST API или Telegram команду `/auth`

### Управление сообщениями

- Получение диалогов и сообщений
- Отправка, редактирование, удаление сообщений
- Пересылка сообщений
- Поиск диалогов

### Файлы и медиа

- Отправка файлов
- Скачивание медиа из сообщений

### Каналы и группы

- Вступление в каналы/группы
- Выход из каналов/групп

### Прокси

- Поддержка SOCKS4/SOCKS5 прокси
- Поддержка HTTP прокси
- Поддержка MTProto прокси
- Настройка через переменную окружения `PROXY`

## Структура проекта

```
BW-BOT-TELEPHON-API/
  main.py              # Точка входа
  app.py               # FastAPI приложение + lifespan
  api.py               # HTTP API маршруты
  bot.py               # Telethon клиент и логика
  .env.rename          # Пример файла .env
  requirements.txt     # Зависимости
  sessions/            # Telegram session файлы (создаётся автоматически)
  downloads/           # Скачанные файлы (создаётся автоматически)
  logs/                # Логи (создаётся автоматически)
```

## Установка

### 1. Клонирование

```bash
git clone https://github.com/bwproject/BW-BOT-TELEPHON-API.git
cd BW-BOT-TELEPHON-API
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Получение API_ID и API_HASH

1. Перейдите на [my.telegram.org](https://my.telegram.org)
2. Войдите через номер телефона
3. Создайте приложение в разделе **API development tools**
4. Скопируйте `API_ID` и `API_HASH`

### 4. Настройка окружения

Скопируйте `.env.rename` в `.env` и заполните:

```env
API_ID=12345678
API_HASH=your_api_hash_here
PHONE=+70000000000
PROXY=socks5://127.0.0.1:1080
SESSION_NAME=sessions/account
HOST=0.0.0.0
PORT=8000
API_TOKEN=
```

| Переменная | Описание | По умолчанию |
|---|---|---|
| `API_ID` | ID приложения Telegram | -- |
| `API_HASH` | Хеш приложения Telegram | -- |
| `PROXY` | Прокси для подключения к Telegram | -- |
| `SESSION_NAME` | Путь к session-файлу | `sessions/account` |
| `HOST` | Адрес сервера | `0.0.0.0` |
| `PORT` | Порт сервера | `8000` |
| `API_TOKEN` | Токен для защиты API | -- |

### Прокси

Если Telegram заблокирован в вашей сети, настройте прокси в `.env`:

```env
# SOCKS5 без аутентификации
PROXY=socks5://127.0.0.1:1080

# SOCKS5 с логином и паролем
PROXY=socks5://user:pass@127.0.0.1:1080

# HTTP прокси
PROXY=http://127.0.0.1:8080

# MTProto прокси (через Proxy бот в Telegram)
PROXY=mtproto-proxy://149.154.167.50:443#ee12d3253c0e43b29c23a43e1e1e487e
```

## Запуск

```bash
python main.py
```

После запуска будет проведена проверка сети Telegram, затем запущен Telethon клиент и FastAPI сервер.

Swagger документация доступна по адресу: `http://localhost:8000/docs`

## API эндпоинты

### Авторизация

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/auth/send_code` | Отправить код авторизации |
| `POST` | `/auth/sign_in` | Войти по коду |
| `POST` | `/auth/password` | Ввести пароль 2FA |
| `GET` | `/auth/status` | Проверить статус авторизации |

### Аккаунт

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/me` | Информация об аккаунте |

### Диалоги и сообщения

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/dialogs?limit=50` | Список диалогов |
| `GET` | `/messages?peer=@username&limit=20` | Сообщения диалога |
| `GET` | `/search?query=text&limit=20` | Поиск диалогов |
| `POST` | `/send` | Отправить сообщение |
| `POST` | `/edit` | Редактировать сообщение |
| `POST` | `/delete` | Удалить сообщение |
| `POST` | `/forward` | Переслать сообщение |

### Файлы

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/upload` | Отправить файл |
| `POST` | `/download` | Скачать медиа |

### Каналы

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/join` | Вступить в канал/группу |
| `POST` | `/leave` | Покинуть канал/группу |

## Примеры запросов

### Отправка кода

```bash
curl -X POST http://localhost:8000/auth/send_code \
  -H "Content-Type: application/json" \
  -d '{"phone": "+79999999999"}'
```

### Вход по коду

```bash
curl -X POST http://localhost:8000/auth/sign_in \
  -H "Content-Type: application/json" \
  -d '{"code": "12345"}'
```

### Отправка сообщения

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"peer": "@username", "text": "Привет!"}'
```

### Получение диалогов

```bash
curl http://localhost:8000/dialogs?limit=10
```

### Использование из Python

```python
import requests

requests.post(
    "http://127.0.0.1:8000/send",
    json={
        "peer": "@username",
        "text": "Сообщение через API"
    }
)
```

## Авторизация через Telegram

Отправьте команду `/auth` аккаунту в Telegram:

1. Введите номер телефона
2. Получите код в Telegram
3. Введите код
4. Если включена 2FA -- введите пароль

После успешного входа session сохраняется в `sessions/`.

## Безопасность

- Не публикуйте `.env` файл
- Не передавайте `session` файл третьим лицам
- Используйте `API_TOKEN` при открытии сервиса наружу
- Запускайте за Nginx/Caddy при использовании через интернет

## Лицензия

MIT License
