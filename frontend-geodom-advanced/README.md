# ГеоДом — фронтенд MVP для квартир Красноярска

React + TypeScript клиент для кейса: персональный подбор по бюджету, семье, месту работы и приоритетам; карта и каталог квартир; карточка с районом, инфраструктурой, будущими проектами и объяснимой оценкой; регистрация и объявления владельца.

![Стек](https://img.shields.io/badge/React-19-0878ee) ![Стек](https://img.shields.io/badge/TypeScript-5-0878ee)

## Запуск

```bash
npm install
npm run dev -- --host 127.0.0.1
```

Без `VITE_API_URL` запускается **демонстрационный режим**. Он содержит примерные квартиры, иллюстративные фотографии и вымышленные проекты, специально помеченные как демо. Параметры подбора, фильтры, сохранение, сравнение, регистрация, вход и объявления работают в браузере. Демо-данные, события, параметры, сохранённые квартиры, сравнение и последняя успешная подборка хранятся в `localStorage`; auth-сессия — в `sessionStorage`. Не используйте реальные пароли: клиентское демо-хеширование не заменяет серверную аутентификацию.

Демо-скоринг использует только заранее заданные признаки школ, парков и транспорта. Экология, безопасность, реальное время маршрута и CatBoost-прогноз цены **не рассчитаны**; интерфейс показывает эти ограничения. Персональный score — от 0 до 10. Сохранённые квартиры остаются только в текущем браузере.

Для подключения GeoDom Go backend:

```bash
cp .env.example .env.local
# VITE_API_URL=http://localhost:8080
npm run dev
```

Настройте CORS backend для origin Vite. После установки `VITE_API_URL` демо-хранилище отключается и все операции идут через `src/lib/api.ts`. Все карточки, признаки, проекты, оценка и причины приходят готовым DTO от backend. Фронтенд не вызывает ML, геокодер, PostgreSQL или object storage напрямую.

## API контракт, ожидаемый клиентом

| Метод | URL | Результат |
| --- | --- | --- |
| GET | `/api/apartments` | `Apartment[]` опубликованных квартир |
| GET | `/api/apartments/:id` | `Apartment` с вложенными `district`, `features`, `development_projects`, `recommendation`, `photos` |
| POST | `/api/v1/recommendations` | `RecommendationResponse`; тело `RecommendationRequest` с бюджетом, взносом, семьёй, координатами работы, временем в пути и весами приоритетов |
| POST | `/api/v1/events` | `204` или пустой `200`; тело `{request_id, event, entity_type, entity_id, position}` |
| POST | `/api/auth/register` | `{id, login}`; тело `{login, password}` |
| POST | `/api/auth/login` | `{access_token, user: {id, login}}`; тело `{login, password}` |
| GET | `/api/auth/me` | `{id, login}` |
| GET | `/api/users/me/apartments` | `Apartment[]`, включая скрытые |
| POST | `/api/apartments` | `Apartment`; тело `ListingInput` |
| PATCH | `/api/apartments/:id` | `Apartment`; тело `ListingInput` |
| DELETE | `/api/apartments/:id` | скрывает объявление; `204` |
| POST | `/api/apartments/:id/photos` | `multipart/form-data`, поле `file`, до 10 фото |

`src/types.ts` — интерфейсы DTO. Рекомендация содержит `request_id`, `model_version`, `scoring_version` и `items` с `score` 0–10, `scores`, `reasons`, `warnings`, `predicted_price_m2` и `cover_image_url`. Клиент допускает отсутствующие необязательные подоценки и относительные URL фото. Событие `impression` отправляется после появления карточки на экране; `click`, `save` и `compare` — при соответствующем действии. Логирование событий на сервере не должно блокировать навигацию.

В реальном режиме клиент передаёт адрес как строку, сервер геокодирует и сохраняет координаты/район, рассчитывает признаки и возвращает их. Если ML недоступен, backend может вернуть rule-based score с `ml_available: false` и предупреждениями либо не вернуть оценку; каталог продолжает работать. Future development показывается отдельно и **не включается** в оценку на MVP. Для проекта указываются `source_name`, `source_url`, статус и срок; ссылка на источник отображается, когда она есть.

После создания объявления фото загружаются последовательно. Если загрузка одного файла упала, само объявление может уже существовать — его можно открыть в кабинете и повторить редактирование. Для production лучше добавить endpoint пакетной загрузки/удаления фото и серверный откат либо явную повторную загрузку.

## Проверка

```bash
npm test
npm run build
```

Карта построена на **Yandex Maps JavaScript API 2.1**. Для стабильного запуска задайте `VITE_YANDEX_MAPS_API_KEY` в `.env.local`. Колесо мыши и кнопки масштаба включены. На обзорном zoom показываются score-карточки районов и компактные точки квартир; с zoom 12 появляются price-pins квартир, а районы схлопываются в точки. Место работы выбирается кликом по основной карте, выбранную точку можно перетащить. Панель POI-слоёв сворачивается, в том числе для мобильного экрана.

Параметры подбора, место работы, фильтры каталога и последняя успешная рекомендация сохраняются в `localStorage`, поэтому обычная перезагрузка страницы не должна сбрасывать интерфейс. Результат с backend обновляет сохранённую копию после успешного ответа.

## Структура

- `src/pages/Catalog.tsx` — аналитический главный экран, карта, фильтры, квартиры.
- `src/pages/Detail.tsx` — готовый DTO квартиры, инфраструктура, будущие объекты, оценка, ипотечный сценарий и сохранение.
- `src/pages/Report.tsx` — клиентский printable/PDF-отчёт по последней успешной подборке.
- `src/pages/Compare.tsx` — отдельный comparison workspace; сравнение больше не висит поверх карты/каталога.
- `src/components/PreferencePanel.tsx`, `RecommendationResults.tsx`, `ScorePanel.tsx`, `MortgageCalculator.tsx` — параметры, персональная выдача, объяснение score и финансовый сценарий.
- `src/pages/Auth.tsx`, `Account.tsx`, `ListingForm.tsx` — пользовательский сценарий.
- `src/components/MapPanel.tsx` — Yandex Maps, квартиры/районы, zoom-aware маркеры и выбор места работы; геопризнаки на клиенте не считает.
- `src/store/useGeoDomStore.ts` — Zustand-store для auth/UI, параметров, фильтров, сохранённых и сравниваемых квартир.
- `src/lib/api.ts` — единая точка подключения backend и интерактивное демо.
- `src/lib/recommendations.ts` — mock-рекомендация, нормализация API-ответа и хранение локальных демо-событий.
- `src/data/demo.ts` — явно вымышленные данные для демонстрации интерфейса.

В карточке квартиры работает 4-шаговый ипотечный сценарий: выбор программы и банка, параметры заёмщика, стоимость/взнос/срок, затем сравнение рассчитанных предложений. Черновик восстанавливается после reload, а финальные расчёты можно сохранить и увидеть в личном кабинете. Банковские ставки остаются датированным snapshot/ориентиром и не являются офертой или одобрением банка. Аренды, чата, платежей и отдельной админ-панели пока нет.


## Geo parquet и пропуски

Загруженный набор `geo_objects` содержит OSM-поля вроде `osm_id`, `category`, `subcategory`, `name`, `address`, WKT `geometry`, `source_url`, временные поля и признаки качества адреса. На клиенте добавлен `src/lib/dataSanitizers.ts` для строк, приходящих из такого parquet после сериализации backend:

- пустые строки, `NaN`, `None`, `null`, `<NA>` и аналогичные значения превращаются в `null`, а не в текст «nan»;
- числовой `NaN/Infinity` превращается в `null`;
- WKT `POINT (lon lat)` валидируется и преобразуется в `{lat, lon}`;
- строки без валидной геометрии или идентификатора не попадают на карту;
- отсутствующие необязательные поля не подменяются нулём, если ноль меняет смысл показателя.

Тот же принцип используется для recommendation DTO: невалидные подоценки и `predicted_price_m2` становятся `null`, чтобы UI показывал отсутствие данных вместо `NaN`.


## Frontend MVP readiness

Текущий frontend-срез считается функциональным MVP, когда PR проходит `npm test` и `npm run build` и сохраняются следующие пользовательские сценарии:

- ввод параметров и произвольного бюджета;
- выбор места работы на Yandex Maps;
- zoom-aware карта районов, квартир и POI;
- персональная выдача с reasons/warnings и объяснением score;
- каталог, detail, сохранение и сравнение до трёх вариантов;
- printable/PDF-отчёт по последней успешной подборке;
- reload без потери параметров, фильтров, сохранений и последнего результата;
- mobile layout, сворачиваемые слои карты и fallback при ошибке React-render;
- demo auth, кабинет и публикация/редактирование объявления.

После этого функциональный MVP **замораживается**, а визуальный этап идёт отдельными feature-ветками: Framer Motion/GSAP для навигации и micro-interactions, затем Three.js только там, где он добавляет смысл, а не мешает карте и основному decision flow.

Текущий `develop` уже проходит frontend CI: тесты, production build, size-check и Docker build являются обязательным gate.


## Карта и большие наборы данных

Карта использует LOD-политику: при сильном отдалении квартиры не рендерятся вообще, затем появляются кластеры, и только на близком масштабе — price-pins. На близком масштабе рендер ограничен текущим viewport; если price-pins становятся слишком многочисленными, интерфейс автоматически возвращается к кластерам. POI также скрываются на дальнем масштабе и ограничиваются viewport/cap, чтобы карта не деградировала при больших наборах данных.

Подробный performance-план для React, карты, Framer Motion и Three.js: `docs/frontend-performance-roadmap.md`.


## Временный локальный media bridge

Go backend уже моделирует импортированные фото через media metadata и позже должен отдавать frontend реальные URL. Пока сами файлы ещё не подключены через backend, frontend умеет использовать локальную копию архива **только как временный dev-fallback**.

Подготовка:

```bash
mkdir -p public/media local-data

# Скопировать содержимое media/ из housing-архива в public/media/
# Скопировать processed/housing/media.jsonl:
cp /path/to/archive/processed/housing/media.jsonl local-data/media.jsonl

npm run media:manifest
npm run dev
```

Генератор создаёт `src/data/localHousingMedia.generated.ts` и связывает `entity_id` с фотографиями по `position`. Backend URL в `photos[].url` **всегда имеет приоритет**. Локальный `storage_key/local_path` используется только когда URL отсутствует.

В production unverified media с `publication_allowed=false` локальным fallback не показывается. Для закрытого dev-demo оно доступно через `VITE_ALLOW_UNVERIFIED_LOCAL_MEDIA=true`.

После готовности выдачи фото из Go API этот bridge удаляется без изменения UI-компонентов: компоненты уже работают через общий `resolvePhotoUrl()`.


## Районы Красноярска

Форма создания объявления содержит явный выбор одного из 7 административных районов: Железнодорожный, Кировский, Ленинский, Октябрьский, Свердловский, Советский и Центральный. В live-режиме `district_name` отправляется в Go backend, сервер валидирует его по собственному справочнику районов и сохраняет вместе с `district_id`. Геокодирование адреса по-прежнему определяет координаты квартиры.

## Docker / Compose

Подготовлен production-style frontend image и отдельный Compose service:

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

По умолчанию frontend доступен на `http://localhost:3000`, health check — `/healthz`. Временные локальные фото монтируются из `./public/media` read-only и не встраиваются в каждый слой image. Детали и план подключения Go container: `docs/docker.md`.

Для production используйте строгий compose-профиль, который не позволит случайно собрать публичный frontend без API URL и Yandex Maps browser key:

```bash
cp .env.production.example .env.production
# заполнить реальные VITE_API_URL и VITE_YANDEX_MAPS_API_KEY
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

CI дополнительно запускает собранный nginx image, проверяет `/healthz`, SPA fallback для прямых маршрутов и обязательные security headers.


## Finance and GeoDom Pro

Apartment detail now contains two frontend decision tools:

- a Krasnoyarsk mortgage directory/calculator using a dated public snapshot of secondary-housing bank offers, plus a custom-rate mode;
- a configurable buy-vs-rent model that compares home equity with a renter investment scenario over a chosen horizon.

Bank conditions are not live quotes and are never treated as approval. Each bank entry carries a source and update date.

Authenticated demo users can also open `/pro`:

- CRM-style qualified lead matching against their own listings;
- consent-gated synthetic contact reveal;
- paid-promotion demo persisted locally;
- a clearly labelled sponsored catalog slot that does not modify organic recommendation score;
- developer B2B demo;
- aggregated GeoDom Analytics demo.

The commercial/product model and privacy boundaries are documented in `docs/monetization.md`.
