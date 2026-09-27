# GeoDom — сервер 193.39.245.27

Сайт: http://193.39.245.27
API: http://193.39.245.27/api/v1
S3: http://193.39.245.27:9000 (приватные buckets; фото доступны по presigned URL)

Развёрнуто без Docker: nginx + systemd + PostgreSQL 17 + Python 3.12 + PGSTY SILO.
Существующий сторонний PostgreSQL на 5432 сохранён; GeoDom использует отдельный локальный PostgreSQL на 5434.

## Сервисы

```bash
systemctl status geodom-api geodom-storage nginx postgresql@17-main
systemctl restart geodom-api
journalctl -u geodom-api -n 100 --no-pager
journalctl -u geodom-storage -n 100 --no-pager
```

Все сервисы включены в автозапуск. API слушает 127.0.0.1:8000; nginx проксирует /api/.
Frontend собран с `VITE_API_URL=/api/v1`, поэтому браузер обращается к тому же IP.
Cookie HttpOnly; Secure=false для текущего HTTP-развёртывания без домена.

## Пути

- Backend и scoring package: `/opt/geodom/backend`
- Frontend build: `/opt/geodom/frontend`
- Frontend source: `/opt/geodom/source/frontend`
- MinIO/SILO data: `/var/lib/geodom-storage`
- Backend configuration: `/etc/geodom/backend.env` (root:geodom, 0640)
- Storage credentials: `/etc/geodom/storage.env` (root, 0600)
- Nginx: `/etc/nginx/sites-available/geodom`
- Systemd units: `/etc/systemd/system/geodom-api.service`, `geodom-storage.service`
- Исходный snapshot PostgreSQL: `/root/geodom-backups/local-geodom-before-deploy.dump`

Пароли созданы на сервере, не включены в репозиторий. SSH-пароль не сохранён в deploy-файлах.

## Community storage

GitHub: https://github.com/pgsty/silo — форк MinIO, поддерживаемый PGSTY.
Зафиксированный release: `RELEASE.2026-09-16T00-00-00Z`.
Archive: `silo_20260916000000.0.0_linux_amd64.tar.gz`.
SHA-256: `381e745510a8fb64323d7bb3207f95984b7f4ed826f4fcad318f97683c420c73`.
Digest сверён с GitHub Release API перед установкой. Binary: `/usr/local/bin/silo`.

Консоль слушает только 127.0.0.1:9001. Доступ через SSH:

```bash
ssh -L 19001:127.0.0.1:9001 root@193.39.245.27
```

После подключения открыть http://localhost:19001; credentials находятся в `/etc/geodom/storage.env`.

## Обновление frontend

Локально в frontend repo:

```bash
VITE_API_URL=/api/v1 VITE_ALLOW_UNVERIFIED_LOCAL_MEDIA=false npm run build
rsync -az dist/ root@193.39.245.27:/opt/geodom/frontend/
```

## Обновление backend

Перед migration создайте snapshot БД. Не копируйте локальные `.env`, `.venv` или credentials на сервер.
После переноса кода:

```bash
cd /opt/geodom/backend
runuser -u geodom -- env UV_CACHE_DIR=/var/cache/geodom /usr/local/bin/uv sync --locked --no-dev --python /usr/bin/python3.12
runuser -u geodom -- .venv/bin/alembic upgrade head
systemctl restart geodom-api
```

Для восстановления S3 из локального media-архива и уже восстановленной БД:

```bash
cd /opt/geodom/backend
runuser -u geodom -- .venv/bin/python scripts/restore_media_objects.py
```

Этот импорт проверяет SHA-256, сохраняет исходные bucket/key, не меняет разрешения публикации и пропускает существующие объекты.
Новые пользовательские фото хранятся только в S3, поэтому для их резервирования сохраняйте весь `/var/lib/geodom-storage` вместе с PostgreSQL и `/etc/geodom`.

## Проверка после развёртывания (2026-09-27)

- PostgreSQL snapshot восстановлен; Alembic head/check — без расхождений.
- 300 опубликованных квартир, 1187 фото, все исходные infrastructure features перенесены.
- Внешний API smoke: каталог, районы, фильтры, рекомендации, регистрация/login/me/logout, создание/update/hide/publish/delete, multipart upload, cover/order/delete и HTTP 200 по presigned URL.
- Реальный Chrome через публичный IP: 64 API responses, без JS-ошибок и критических 404/500; HttpOnly cookie и reload кабинета, создание с двумя фото, обложка и весь listing lifecycle прошли.
- Системные unit-файлы включены в автозапуск; действующее стороннее приложение PostgreSQL на 5432 не изменено.
