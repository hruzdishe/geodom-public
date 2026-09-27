# Подключение к бэкенду

Установите пакет из этой папки. Python-импорты остаются `krasnoyarsk_ml`.
HTTP-обёртку реализуйте в своём приложении или отдельном Python-сервисе.
Предлагаемые маршруты: `POST /recommendations/apartments` и
`POST /recommendations/districts`. Они пока не реализованы в этом пакете.

## Контракт запроса

Тело запроса обоих скореров описано в `examples/preferences.schema.json`.
Пример — `examples/preferences_family.json` (координаты работы демонстрационные).
Цена в рублях, комнаты — список целых чисел, 0 означает студию.
Районы в фильтре задаются именами `district_name`, не ID.
Приоритеты — целые веса 0–5. Неизвестные поля и ключи приоритетов запрещены.
Серверные настройки имеют отдельную схему `examples/scoring_config.schema.json`.
Не передавайте настройку скорости или формулы под прямой контроль клиента.

## Квартиры: вызов из памяти или БД

```python
from krasnoyarsk_ml.scoring import Preferences, ScoringConfig, recommend

preferences = Preferences.model_validate(request_body)
config = ScoringConfig(assumed_car_speed_kmh=30)
result = recommend(apartments, apartment_features, preferences, limit=10, config=config)
```

`apartments` и `apartment_features` — списки словарей из вашей БД или Parquet.
Минимальный рабочий пример обоих скореров: `examples/backend_example.py`.

| Строка | Необходимые поля и смысл |
|---|---|
| Квартира | `id`: уникальная непустая строка; `price`: положительное число; `rooms`: целое >=0; `currency`: RUB; `offer_type`: sale/rent; `district_name`; `lat`, `lon`: WGS84 |
| Признаки квартиры | `apartment_id = apartments.id`; `feature_version`; `distance_method`; поля групп инфраструктуры ниже |
| Признак группы | `<group>_observed_in_snapshot`: bool; `<group>_nearest_distance_m`: число метров или null; `<group>_nearest_poi_id`: строка или null |

Группы берутся из `features.GROUPS`, соответствие приоритетам — из `scoring.PRIORITIES`.
Версии берите из `features.VERSION` и `features.METHOD`; не меняйте метку версии,
чтобы выдать несовместимые признаки за совместимые. Числовые поля из PostgreSQL
Decimal приведите к int/float, ID оставляйте строками, пропуски — None.

`recommend` возвращает словарь: `status`, `eligible_count`, `returned_count`,
`results`, веса, конфигурацию и ограничения. В элементах выдачи есть `apartment_id`,
`apartment`, `score`, `components`, `score_coverage`, `score_upper_bound`, `commute`.
Сохраните эти объяснения в API. Не заменяйте null нулём. Баллы 0–100; для шкалы
интерфейса 0–10 делите на 10. `limit` допускает 1–1000.

## Районы

```python
from krasnoyarsk_ml.districts import rank_districts

result = rank_districts(
    districts, reference_points, reference_features, preferences, config,
    apartment_result=all_eligible_apartments,
)
```

| Аргумент | Поля |
|---|---|
| `districts` | `district_id`, `district_name`; сохраняйте `boundary_version` при хранении |
| `reference_points` | `id`, `district_id`, `lat`, `lon`, положительный `weight_m2` — площадь жилой территории |
| `reference_features` | `point_id = reference_points.id`; те же версии и поля групп, что у квартир |
| `apartment_result` | Полный ответ квартирного скорера после фильтров, без усечения top-N; можно None |

Количество объявлений не влияет на балл района. При `apartment_result=None`
счётчики объявлений неизвестны, а районный скоринг всё равно работает.
Для счётчиков `returned_count` должен равняться `eligible_count`. Пример вызывает
`recommend(..., limit=max(1, len(apartments)))`; такой путь поддерживает до 1000 квартир.
Для большей базы доработайте получение полной выборки, не передавайте обрезанную выдачу.

Используйте согласованную пространственную привязку `district_name` для обоих
скореров: район из объявления может отличаться от района по геометрии.
Исходное имя храните отдельно. В файловом пути это делает районный аудит;
прямые вызовы из БД требуют этой подготовки на стороне бэкенда.

## Файловая интеграция

После подготовки данных командами из [PARSERS.md](PARSERS.md):

```bash
uv run ml-recommend --preferences examples/preferences_family.json --config examples/scoring_straight_line_car.json
uv run ml-districts recommend --preferences examples/preferences_family.json --config examples/scoring_straight_line_car.json
```

CLI проверяет согласованность снимков и контрольные суммы. Прямые Python-вызовы
не проверяют файлы: ответственность за связи, версии, даты и обновление признаков
лежит на вызывающем коде. При изменении координат пересчитайте признаки.
Для районов есть также `districts.recommend_from_files`; он проверяет манифесты
и каждый раз загружает файлы. Загрузку и проверки лучше выполнять при старте
процесса, затем использовать данные из памяти.

## Поведение API и ограничения

- Невалидный запрос: обработайте Pydantic ValidationError как 400/422.
- Ошибка входных данных/версий: серверная ошибка; не возвращайте случайные квартиры.
- Пустая выдача: корректный результат, фильтры не ослабляются автоматически.
- Расчёт синхронный: не блокируйте им async event loop; используйте worker/thread.
- Скорость 30 км/ч — условное допущение. Без неё возвращается только расстояние.
- Люфт 15% включает предупреждение о времени, но не исключает квартиру.
- Экология, безопасность и кафе не участвуют в баллах. Возвращайте `unsupported_priorities`.
- Адрес работы должен быть преобразован бэкендом в координаты.
- Фото и MinIO не нужны для вычисления скоринга; карточки обогащаются отдельно.
- Параллельная нагрузка и качество на пользовательской разметке не измерены.
