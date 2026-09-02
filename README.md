# 👻 GhostHub

Анонимные комнаты для быстрого обмена текстом и файлами между устройствами.

Нужно быстро перекинуть что-то с компьютера на телефон? Создайте комнату, откройте
ссылку или отсканируйте QR-код на другом устройстве — и обменивайтесь сообщениями
и файлами в реальном времени.

## Возможности

- 🚀 Комната по ссылке, срок жизни задаётся через `ROOM_TTL_SECONDS`
- 📱 QR-код ссылки — вход со смартфона по сканированию
- 💬 Текстовые сообщения и файлы в реальном времени (SSE + htmx)
- 📦 Мультизагрузка: drag&drop нескольких файлов, прогресс-бары
- 🖼 Превью картинок/видео/аудио прямо в ленте
- ✍️ Markdown и подсветка кода в сообщениях
- 🔒 Опциональный пароль комнаты (pbkdf2)
- 🎭 Каждому устройству своя иконка и цвет
- 🧹 Комната и все файлы удаляются автоматически после истечения срока
- 🛡 Rate-limit создания комнат и попыток входа по IP
- ⚖️ Лимит объёма файлов в комнате — `ROOM_MAX_BYTES` (по умолчанию 150 МБ)

## Стек

Python 3.12 · Litestar 2.x · Granian · SQLAlchemy 2 (async) · Alembic · PostgreSQL 17
· Jinja2 · htmx 2 (SSE) · qrcode

## Локальный запуск

Нужен работающий PostgreSQL (например, Postgres.app или Docker).

```bash
uv sync
cp .env.example .env   # укажите свои значения
createdb ghosthub       # если БД ещё нет
alembic upgrade head
granian --interface asgi app.main:app --host 0.0.0.0 --port 8000
```

Приложение будет доступно по адресу `http://localhost:8000`.

## Деплой (Docker + Caddy)

`docker-compose.yml` поднимает два сервиса: само приложение и PostgreSQL 17
(данные БД — в volume `postgres_data`, файлы комнат — в `ghosthub_data`).
Миграции выполняются автоматически при старте контейнера.

```bash
cp .env.example .env
# DATABASE_URL=postgresql+asyncpg://ghosthub:ghosthub@postgres:5432/ghosthub
docker compose up -d --build
```

При размещении за обратным прокси под префиксом пути (например, Caddy
`handle_path /ghost*`) задайте:

```
BASE_PATH=/ghost
PUBLIC_BASE_URL=https://example.com/ghost
```

`BASE_PATH` добавляется ко всем ссылкам приложения (страницы, статика, QR, SSE),
а префикс срезается прокси перед бэкендом.

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | — | URL базы данных (SQLAlchemy async, asyncpg), например `postgresql+asyncpg://ghosthub:ghosthub@postgres:5432/ghosthub` |
| `SECRET_KEY` | `dev-secret-change-me` | Секрет для подписи cookie доступа к комнатам — **смените на свой!** |
| `STORAGE_PATH` | `storage` | Каталог для хранения файлов комнат |
| `BASE_PATH` | (пусто) | Префикс пути за обратным прокси (например `/ghost`) |
| `PUBLIC_BASE_URL` | (пусто) | Абсолютный базовый URL для ссылок и QR-кодов |
| `ROOM_TTL_SECONDS` | `3600` | Время жизни комнаты в секундах |
| `ROOM_MAX_BYTES` | `157286400` | Максимальный суммарный объём файлов в комнате (150 МБ) |
| `ROOM_CLEANUP_INTERVAL_SECONDS` | `60` | Как часто фоновая задача удаляет истёкшие комнаты и осиротевшие файлы |
| `RATE_LIMIT_CREATE_ROOMS` | `20` | Лимит создания комнат с одного IP за час |
| `RATE_LIMIT_JOIN_ATTEMPTS` | `10` | Лимит неудачных входов по паролю с одного IP за 15 минут |
| `DEBUG` | `false` | Режим отладки |

## Тесты

Тесты работают с PostgreSQL. Создайте тестовую БД и запустите:

```bash
createdb ghubhub_test
uv run pytest
```

Тесты используют отдельную базу данных (`ghubhub_test` или свой `DATABASE_URL`)
и временный каталог хранилища, не затрагивая рабочее окружение.

## Структура

```
app/
  common/        # утилиты: время, безопасность, устройства, хранилище, шаблоны
  core/          # конфиг, sse-хаб, фоновая очистка
  database/      # engine, сессии
  modules/
    room/        # комнаты: страницы, QR, SSE, вход по паролю
    buffer/      # сообщения и файлы
  templates/     # jinja2-шаблоны
  static/        # css/js (htmx и библиотеки — локально, без CDN)
migrations/      # alembic
tests/           # pytest
```
