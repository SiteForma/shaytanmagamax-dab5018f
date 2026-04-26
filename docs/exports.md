# Exports

## Поддерживаемые выгрузки

Продукт сейчас поддерживает:

- результаты reserve run
- покрытие склада
- top-risk SKU
- quality issues
- экспозицию DIY-клиентов
- DIY report pack

Форматы:

- `csv`
- `xlsx`

`DIY report pack` доступен только в `xlsx`, потому что это многолистовой артефакт.

## API

- `POST /api/exports/reserve-runs/{run_id}`
- `POST /api/exports/stock-coverage`
- `POST /api/exports/dashboard/top-risk`
- `POST /api/exports/quality/issues`
- `POST /api/exports/clients/exposure`
- `POST /api/exports/report-packs/diy-exposure`
- `GET /api/exports/jobs`
- `GET /api/exports/jobs/{job_id}`
- `GET /api/exports/jobs/{job_id}/download`

## Async flow для крупных выгрузок

Если объём превышает `EXPORT_ASYNC_ROW_THRESHOLD` или тип выгрузки принудительно помечен как async-only, экспорт идёт через worker-flow:

1. создаётся `ExportJob`
2. создаётся `JobRun` с `job_name=generate_export`
3. job уходит в очередь `exports`
4. worker материализует артефакт и переводит job в `completed` или `failed`

Основные env-переменные:

- `EXPORT_ASYNC_ENABLED`
- `EXPORT_ASYNC_ROW_THRESHOLD`

## Хранение и метаданные

Выгрузки хранятся как строки `ExportJob` и файловые артефакты под `EXPORT_ROOT`.

Для каждого job сохраняются:

- тип выгрузки
- инициатор
- формат
- количество строк
- filters payload
- summary payload
- storage key
- статус
- completed timestamp
- download count

Для `xlsx` всегда добавляется лист `meta` с:

- временем генерации
- пользователем
- типом выгрузки
- ключевым фильтром/срезом
- relevant summary metadata

## Безопасность

- генерация требует `exports:generate`
- просмотр истории и скачивание требуют `exports:download`
- не-admin пользователь видит только свои `ExportJob`
- повторная генерация через admin retry разрешена только для safe export job path

## Frontend surfaces

Экспортные действия подключены в:

- Overview
- Reserve Calculator
- Stock & Coverage
- Data Quality
- DIY Networks
- Admin
