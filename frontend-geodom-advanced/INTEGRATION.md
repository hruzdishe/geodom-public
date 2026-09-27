# GeoDom: локальное end-to-end MVP

Frontend: http://localhost:5173 · FastAPI: http://localhost:8000/api/v1

## Запуск без Docker

Backend (PostgreSQL должен работать; существующий `.env` сохранён):

```bash
cd /home/naw/hakaton/geodom-backend
env -u DEBUG uv run uvicorn geodom_backend.main:app --reload --host 127.0.0.1 --port 8000
```

`env -u DEBUG` нужен на этой машине: системный `DEBUG=release` несовместим с boolean-настройкой FastAPI.

MinIO, если ещё не запущен (используется существующий binary и каталог):

```bash
/home/naw/minio/minio server /home/naw/minio/data --address :9000 --console-address :9001
```

При нестандартных credentials задайте `MINIO_ROOT_USER` и `MINIO_ROOT_PASSWORD`, совпадающие с backend `STORAGE_ACCESS_KEY`/`STORAGE_SECRET_KEY`. Не включайте credentials в git.

Frontend:

```bash
cd /home/naw/hakaton/frontend-geodom-advanced
npm install
npm run dev -- --port 5173 --strictPort
```

Для тестов требуется Node 22.22.2+; версия закреплена в `.nvmrc`. На текущем Node 18 сборка/dev прошли, но существующие jsdom/React Router требуют более новой версии. Проверка без замены системного Node:

```bash
npm run build
npm exec --yes --package=node@22.22.2 -- node node_modules/vitest/vitest.mjs run
```

## Environment

Frontend `.env.local` уже настроен и исключён из git:

```dotenv
VITE_API_URL=http://localhost:8000/api/v1
VITE_ALLOW_UNVERIFIED_LOCAL_MEDIA=false
```

Опциональные `VITE_API_REQUEST_TIMEOUT_MS=15000`, `VITE_YANDEX_MAPS_API_KEY` (ключ JavaScript API карт). Пустой `VITE_API_URL` включает отдельный demo-режим. Live-данные не дополняются demo-квартирами, локальными фото или демо-рекомендациями.

Backend `.env`: обязательный `DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/geodom`; storage: `STORAGE_ENDPOINT=localhost:9000`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_SECURE=false`, `STORAGE_USER_BUCKET=geodom-user-media`. `CORS_ORIGINS=["http://localhost:5173"]`, `AUTH_COOKIE_SECURE=false` для локального HTTP; эти значения уже являются defaults. Для geocoder используются существующие `GEOCODING_*` настройки.

Открывайте UI через **localhost**, а не 127.0.0.1: cookie/CORS привязаны к согласованным хостам.

## Что изменено

- `src/lib/backendAdapter.ts`: отдельные FastAPI DTO; Decimal, nullable-поля, владельцы, районы, обложки, оценки и explanations.
- `src/lib/api.ts`: относительные маршруты к `/api/v1`, cookie credentials, pagination, listing/photo lifecycle, отсутствие запросов к неподдержанным endpoints.
- `src/types.ts`, `src/store/useGeoDomStore.ts`, `src/App.tsx`, `src/pages/Auth.tsx`: типы и восстановление сессии до проверки protected routes; logout на сервере.
- `src/pages/Account.tsx`, `src/pages/ListingForm.tsx`: мои объявления, изменение скрытых квартир через `/my/{id}`, sale/rent, hide/publish/delete, фото/обложка/удаление. Повторная отправка после ошибки загрузки не создаёт дубликат квартиры.
- `src/pages/Catalog.tsx`, `src/components/PreferencePanel.tsx`, `src/lib/catalog.ts`, `src/lib/preferences.ts`, `src/components/Ui.tsx`: sale/rent, период аренды, студии, цена, существующие фильтры и карта.
- `src/pages/Detail.tsx`, `Compare.tsx`, `Report.tsx`, `src/components/ScorePanel.tsx`, `RecommendationResults.tsx`, `MapPanel.tsx`: null не становится нулём; score 0–100 переводится в 0–10; отсутствующие координаты не дают marker.
- `src/lib/media.ts`, `recommendations.ts`, `pro.ts`: изоляция live/demo, отсутствие подстановки архивных фото.
- `.env.example`, `.env.test`, `.nvmrc`, тесты API/адаптера, небольшой CSS для photo-controls; npm обновил lockfile при install (он был изменён и до начала работы).
- Backend: `apartments/schemas.py` добавляет существующие координаты/owner/source без migration; `apartments/router.py` и `recommendations/{service,dependencies}.py` используют photo-presenter; scoring рассматривает до 1000 кандидатов вместо первых 100. `apartments/service.py` не геокодирует неизменившийся адрес повторно. Алгоритм scoring не изменён.
- Backend `scripts/smoke_api.py`, `tests/test_public_photos.py`: повторяемая API-проверка и права публикации.

## Проверено

- TypeScript и production build — успешно.
- 82 frontend tests; 2 backend tests — успешно.
- Backend compile/import, Alembic current/head и check — успешно, новых migrations нет.
- Реальный API smoke: каталог 300 квартир, 7 районов, фильтры, рекомендации, auth/cookie/logout, create/update/my, hide/publish/delete, multipart upload, list/cover/order/delete photos и HTTP 200 по presigned URL.
- Рекомендации при бюджете 12 млн: 224 кандидата, top score 93.1551/100; fallback=false.
- Chrome через Playwright: реальный UI lifecycle, reload `/account` не перенаправляет на login, cookie HttpOnly, загруженное фото декодируется, смена обложки работает, 68 API responses без критических 404/500 и без JS page errors. Только ожидаемые anonymous `/auth/me` 401.
- После отдельного разрешения владельца проекта импортированы 1187 локальных seed-фото для 300 квартир в MinIO `geodom-seed-media`; публичный показ этих фото разрешён, статус `operator_authorized_for_publication`. Запрет подписания остальных `publication_allowed=false` сохранён и отдельно проверен regression-тестом. Публичная карточка/каталог/recommendations используют этот presenter.

Повтор API smoke (создаёт тестового пользователя и soft-deleted тестовое объявление, удаляет загруженные тестовые фото):

```bash
cd /home/naw/hakaton/geodom-backend
env -u DEBUG uv run python scripts/smoke_api.py
env -u DEBUG uv run pytest tests -q
```

## Ограничения и secondary features

- Pro/CRM/продвижение и публикация профиля поиска отключены в live UI; event tracking — no-op. Запросов к отсутствующим API нет.
- Районная статистика вычисляется из реальных квартир; geo/POI слой пуст с пояснением. Карта зависит от доступности Яндекс API. Future infrastructure показывает отсутствие подтверждённых данных.
- Подбор сейчас для покупки; аренда поддержана в каталоге и редакторе. Возраст детей UI не спрашивает: состав семьи/взнос остаются для планирования, рейтинг использует явные приоритеты. Экология/безопасность и маршруты не выдумываются — ограничения scorer отображаются.
- Новые квартиры имеют pending infrastructure features; показывается «нет данных», пока отдельный pipeline не рассчитает признаки.
- Создание/смена адреса зависит от внешнего Nominatim. Проверенный адрес: `Красноярск, улица Ленина, 25`.
- Для небольшого MVP UI загружает каталог полностью, проходя страницы API, и фильтрует локально. При существенном росте базы стоит перейти на server-side pagination; scoring пока ограничен 1000 кандидатами.
- Presigned URL действует ограниченное время; повторное открытие карточки получает свежие ссылки.

## Демо на 3–5 минут

1. Открыть каталог, выбрать район/комнаты/бюджет, показать карту и карточку.
2. Изменить приоритеты, получить подбор, показать рейтинг, причины и честные ограничения.
3. Зарегистрироваться, обновить кабинет — сессия сохранена.
4. Создать квартиру по проверенному адресу, загрузить свою фотографию.
5. Изменить цену, выбрать обложку, скрыть/опубликовать; открыть публичную карточку с фото.
6. Удалить тестовое объявление, выйти и войти снова.

## Сравнение покупки и аренды

В карточке квартиры → «Финансы» → «Купить или снимать». Кнопка «Сравнить с арендой» в результате ипотечного мастера переносит цену, взнос, ставку и срок кредита. Также можно независимо задать фактическую ставку, срок сравнения, аренду и допущения.

Сравниваем итоговый капитал при одинаковых стартовых деньгах и ежемесячном бюджете:

- Покупатель: цена жилья в конце периода − остаток долга − расходы продажи + накопления.
- Арендатор: сохранённые взнос и расходы покупки + накопления.
- Разницу месячных затрат откладывает тот вариант, который дешевле в конкретном месяце; доходность применяется до очередного пополнения.
- Аннуитет рассчитывается с месячной ставкой `annualRate / 1200`; рост аренды, стоимости жилья и доходность — эффективные годовые ставки, переведённые в месячные.
- Аренда первого месяца равна введённой. После погашения ипотеки кредитные платежи прекращаются. Отрицательный капитал покупателя при падении цены и большом долге сохраняется в расчёте.
- Содержание задаётся в процентах текущей стоимости за год; включает вводимую пользователем оценку ремонта, страховки и налога. Общие коммунальные расходы, налоговые вычеты и досрочное погашение отдельно не моделируются. Расходы продажи могут включать комиссию и ожидаемые налоги. Итог — будущие номинальные рубли, рост цен и доходность не являются прогнозом.

Проверочный пример: квартира 6 млн ₽ без кредита, аренда 30 тыс. ₽/мес, расходы покупки и продажи по 10%, весь рост/доходность/содержание = 0. За 1 год аренда выгоднее на 840 тыс. ₽; за 5 лет покупка выгоднее на 600 тыс. ₽. Изменение срока меняет вывод из-за разовых расходов сделки.

Проверки: контрольные численные сценарии, остаток долга, отсутствие двойного учёта тела кредита, границы ввода, UI-пересчёт и browser smoke переноса параметров из ипотечного мастера. Методология аннуитета сверена с [описанием CFPB](https://www.consumerfinance.gov/ask-cfpb/how-does-paying-down-a-mortgage-work-en-1943/); банковские ставки остаются сохранёнными примерами, не live-предложениями.

## Фильтры и карта

- Комнаты (студия = 0 в API, «4+» = 4…20), район, тип сделки и цена передаются в backend до ранжирования. Каталог, карта и подбор используют выбранные фильтры; изменение параметров запускает обновление с задержкой 350 мс, устаревшие ответы не заменяют новый результат.
- Работа: выбирается точкой на карте. При выбранной точке предел времени действует как фильтр, квартиры с неизвестными координатами исключаются. Backend использует геодезическое расстояние по прямой и условную скорость 30 км/ч; каталог использует сферическое приближение. Это приблизительные минуты, без дорог и пробок. Пограничные расстояния могут незначительно отличаться между приближениями.
- `/api/v1/geo-objects` отдаёт сохранённый набор реальных объектов OSM (`backend/data/map/geo_objects.json`). Выгрузка: `uv run python scripts/export_map_objects.py`; обновление парковок: добавить `--refresh-parking`. Для уже полученного Overpass JSON доступен `--parking-json PATH`. Сеть при открытии каталога для сбора OSM не нужна.
- Добавлен слой парковок. Лимит отображаемых объектов распределяется между включёнными слоями, чтобы многочисленные парковки не вытесняли школы и парки.
- Технические версии, идентификаторы расчётов и диагностические ограничения удалены из пользовательских карточек и отчёта. Ошибки загрузки и недоступность подбора остаются видны. Диагностика по-прежнему есть в API.
