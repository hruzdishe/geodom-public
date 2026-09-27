# Парсеры и подготовка данных

Все команды выполняются из корня `scoring` после `uv sync --locked`.
Сбор требует сети и доступности источников. Выгрузки создаются в `data/`,
исключённой из Git. В комплекте нет результатов прошлых запусков.

## Основной путь

```bash
# 1. Инфраструктура OSM / Overpass, raw-архив, нормализация и метаданные
uv run ml-data osm
# 2. Квартиры Сибдома и фотографии, целевой размер выборки настраивается
uv run ml-housing --target 300 --max-photos 5 --allow-uneven
# 3. Признаки квартир по их координатам и POI
uv run ml-features
# 4. Границы и жилая территория районов
uv run ml-districts collect
# 5. Жилая сетка, её признаки и пространственная привязка квартир
uv run ml-districts build
# 6. Оба скоринга
uv run ml-recommend --preferences examples/preferences_family.json --config examples/scoring_straight_line_car.json
uv run ml-districts recommend --preferences examples/preferences_family.json --config examples/scoring_straight_line_car.json
```

300 — целевой размер, а не гарантия результата. Проверяйте статус отчёта сбора.
При сбое источника не продолжайте с неполной или несогласованной выгрузкой.
Актуальные параметры реализованной команды доступны через `--help`.
Сетевой сбор при подготовке этой папки повторно не запускался.

## Результаты, которые потребуются бэкенду

| Этап | Файлы, создаваемые локально |
|---|---|
| POI | `data/processed/geo_objects.parquet`, `geo_objects.metadata.json` |
| Квартиры | `data/processed/housing/apartments.parquet`, `media.parquet`, JSONL и отчёт |
| Признаки | `data/processed/features/apartment_features.parquet`, `apartment_nearest_pois.parquet`, `feature_report.json` |
| Районы | `data/processed/districts/districts.geojson`, `district_summary.json`, `district_reference_points.parquet`, `reference_point_features.parquet`, `apartment_district_audit.parquet`, `manifest.json` |

Сохраняйте метаданные и манифесты вместе с таблицами: файловые скореры проверяют
хэши исходных квартир и признаков. Переданные отдельно таблицы из разных запусков
нельзя считать согласованным набором.

Можно использовать собственные квартиры из PostgreSQL, если экспорт соответствует
схеме парсера и требованиям `features.py`. Пример минимальных строк для вызова
скоринга напрямую приведён в [BACKEND.md](BACKEND.md).

## Дополнительные команды

- `ml-addresses --help`: сбор адресных объектов OSM и обогащение POI.
  Приблизительные адреса помечаются; это не новые точные координаты.
- `ml-housing-export --help`: проверка фото и экспорт своих локальных данных.
- `ml-district-export --help`: генерация JSONL/SQL из подготовленного районного
  набора и файла примера ответа. Команда не подключается к БД. По умолчанию ожидает
  `data/processed/recommendations/districts_family.json`; передайте `--example
  data/processed/recommendations/districts.json` после основного пути выше.
- `ml-district-environment collect-air --help`: архив экологических наблюдений.
- `ml-district-environment build --help`: справочные сведения по районам.
  Нужны архив воздуха, границы и отдельный подготовленный JSON преступности
  (по умолчанию `data/research/districts/crime_2024_official.json`). Его здесь нет.
  Автоматического парсера преступности в исходном проекте нет; данные в прошлом
  были подготовлены отдельно. Этот этап необязателен для обоих скорингов.

`.env.example` задаёт настройки `ML_*` для OSM и адресного обогащения.
Остальные команды имеют собственные CLI-параметры путей; `ML_DATA_DIR` не является
универсальным переключателем всех команд. Для основного пути оставьте `data/`.
Сохраняйте источник, дату снимка, условия использования и контрольные суммы.
