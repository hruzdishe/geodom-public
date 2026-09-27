# GeoDom

Каталог квартир Красноярска, персональный подбор, карта инфраструктуры, личный кабинет и сравнение покупки с арендой.

## Структура

- `geodom-backend/` — FastAPI, PostgreSQL, cookie-сессии, объявления, фотографии в MinIO/S3 и локальный scoring package.
- `frontend-geodom-advanced/` — React + TypeScript + Vite.
- `geodom-backend/data/map/` — публичный набор объектов OpenStreetMap для карты.
- `geodom-backend/deploy/` — конфигурация nginx/systemd и инструкция развёртывания без Docker.

## Локальный запуск

Нужны Python 3.12, uv, Node.js 22, PostgreSQL и работающий MinIO/S3. Docker не требуется.

Backend:

```bash
cd geodom-backend
cp .env.example .env
# Укажите доступы к своей PostgreSQL и MinIO/S3 в .env.
uv sync --locked
uv run alembic upgrade head
uv run uvicorn geodom_backend.main:app --reload --host 127.0.0.1 --port 8000
```

База PostgreSQL и пользователь должны существовать до запуска миграций. Создание и заполнение данных описаны в документации импорта внутри backend. Если окружение задаёт `DEBUG=release`, запускайте backend-команды с префиксом `env -u DEBUG`.

Frontend — в другом терминале:

```bash
cd frontend-geodom-advanced
cp .env.example .env.local
npm ci
npm run dev
```

В `.env.local`: `VITE_API_URL=http://localhost:8000/api/v1`. Для карты укажите собственный `VITE_YANDEX_MAPS_API_KEY`.

Frontend: http://localhost:5173 · API: http://localhost:8000/api/v1 · OpenAPI: http://localhost:8000/docs

Авторизация использует HttpOnly cookie. Frontend не хранит токены авторизации.

## Сборка и проверки

```bash
cd frontend-geodom-advanced
npm test
npm run build
```

Для размещения frontend за nginx с API на том же хосте:

```bash
VITE_API_URL=/api/v1 npm run build
```

Значения `VITE_*` подставляются при сборке. После изменения ключа карты нужно собрать frontend заново.

```bash
cd geodom-backend
uv run pytest tests packages/scoring/tests/test_scoring.py
uv run python -m compileall src
```

## Данные и документация

Исходники опубликованы без локальных `.env`, паролей, зависимостей, сборок, фотографий и дампа пользовательской БД. Для переноса работающей установки PostgreSQL и MinIO сохраняются отдельно. Набор объектов карты включён; он не заменяет базу квартир.

- [Интеграция frontend и API](frontend-geodom-advanced/INTEGRATION.md)
- [Развёртывание](geodom-backend/deploy/README.md)
- [Импорт локальных фотографий](geodom-backend/scripts/LOCAL_MEDIA.md)
- [Scoring package](geodom-backend/packages/scoring/README.md)

Данные карты: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). Ссылки на исходные объекты сохранены в наборе данных.
