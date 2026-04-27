import type { UploadJob } from "@/types";

export const SOURCE_TYPE_LABELS: Record<UploadJob["sourceType"], string> = {
  sales: "продажи",
  stock: "склад",
  diy_clients: "клиенты DIY",
  category_structure: "структура категорий",
  inbound: "поставки",
  sku_costs: "себестоимость",
  raw_report: "сырой отчёт",
};

const CANONICAL_FIELD_LABELS: Record<string, string> = {
  period_date: "период",
  year: "год",
  month: "месяц",
  client_name: "клиент",
  sku_code: "SKU",
  product_name: "товар",
  quantity: "количество",
  revenue: "выручка",
  category_name: "категория",
  source_row_id: "ID строки источника",
  snapshot_date: "дата снимка",
  stock_total: "общий остаток",
  stock_free: "свободный остаток",
  stock_free_qty: "свободный остаток",
  free_stock_qty: "свободный остаток",
  warehouse_name: "склад",
  warehouse_code: "склад",
  reserve_months: "горизонт резерва",
  safety_factor: "коэффициент запаса",
  priority: "приоритет",
  active: "активность",
  region: "регион",
  category_level_1: "категория 1 уровня",
  category_level_2: "категория 2 уровня",
  category_level_3: "категория 3 уровня",
  eta_date: "дата поставки",
  status: "статус",
  article: "артикул",
  cost_rub: "себестоимость",
  raw_value: "сырое значение",
};

const ISSUE_CODE_LABELS: Record<string, string> = {
  duplicate: "дубликат",
  duplicate_row: "дубликат строки",
  duplicate_upload: "дубликат загрузки",
  missing_sku: "нет SKU",
  unmatched_client: "клиент не сопоставлен",
  unmatched_sku: "SKU не сопоставлен",
  unmatched_reference: "нет ссылки",
  missing_reference: "нет ссылки",
  negative_stock: "отрицательный остаток",
  suspicious_spike: "подозрительный всплеск",
  missing_month: "пропущен месяц",
  category_mismatch: "несовпадение категории",
  mapping_required: "нужно сопоставление",
  required_field_missing: "нет обязательного поля",
  empty_normalized_row: "пустая строка после сопоставления",
  invalid_date: "некорректная дата",
  future_period: "период в будущем",
  future_snapshot: "дата снимка в будущем",
  invalid_numeric: "некорректное число",
  invalid_reserve_months: "некорректный горизонт резерва",
  out_of_range: "значение вне диапазона",
  duplicate_active_policy: "дублирующая активная политика",
  broken_hierarchy: "сломанная иерархия",
  invalid_status: "неизвестный статус",
  apply_not_supported: "применение недоступно",
  blocking_issues: "есть блокирующие проблемы",
};

const MESSAGE_LABELS: Record<string, string> = {
  "Duplicate row detected for SKU/month combination": "Найдена дублирующая строка по сочетанию SKU/месяц",
  "SKU referenced in sales not present in master": "SKU из продаж отсутствует в мастер-каталоге",
  "Client name does not resolve to known DIY network": "Имя клиента не связано с известной сетью DIY",
  "Negative free stock value reported": "Получен отрицательный свободный остаток",
  "Monthly sales spike >5σ vs trailing 6m": "Всплеск месячных продаж >5σ относительно 6 месяцев",
  "Gap detected in monthly sales series": "Обнаружен пропуск в ряду месячных продаж",
  "Category in source disagrees with canonical category tree": "Категория источника расходится с каноническим деревом категорий",
  "Negative free stock detected": "Обнаружен отрицательный свободный остаток",
  "Potential duplicate row detected within the uploaded file": "Внутри загрузки найден потенциальный дубликат строки",
  "Row becomes empty after mapping": "После сопоставления строка становится пустой",
  "Sales period date is invalid": "Некорректная дата периода продаж",
  "Sales period cannot be in the future": "Период продаж не может быть в будущем",
  "Quantity must be numeric": "Количество должно быть числом",
  "Revenue value could not be parsed": "Не удалось разобрать значение выручки",
  "Snapshot date is invalid": "Некорректная дата снимка",
  "Snapshot date cannot be in the future": "Дата снимка не может быть в будущем",
  "Reserve horizon must be 2 or 3 months": "Горизонт резерва должен быть 2 или 3 месяца",
  "Safety factor must be numeric": "Коэффициент запаса должен быть числом",
  "Safety factor is outside the recommended range": "Коэффициент запаса вне рекомендованного диапазона",
  "Duplicate active DIY policy for the same client": "Для клиента уже есть активная политика DIY",
  "Either SKU code or product name is required": "Нужен либо SKU, либо название товара",
  "Category level 3 requires level 2": "Категория 3 уровня требует заполненный 2 уровень",
  "Category level 2 requires level 1": "Категория 2 уровня требует заполненный 1 уровень",
  "ETA date is invalid": "Некорректная дата поставки",
  "Inbound quantity must be numeric": "Количество поставки должно быть числом",
  "Inbound status is not recognized": "Статус поставки не распознан",
  "Upload mapping is not defined": "Для загрузки не настроено сопоставление",
  "Upload contains blocking validation issues": "Загрузка содержит блокирующие проблемы проверки",
  "No rows were applied": "Не удалось применить ни одной строки",
  "Upload applied with warnings": "Загрузка применена с предупреждениями",
  "Upload applied successfully": "Загрузка успешно применена",
  "Raw report is available for review": "Сырой отчёт готов к просмотру",
  "Source type detected automatically and awaits confirmation": "Тип данных распознан автоматически и ожидает подтверждения",
  "Required canonical fields are missing": "Не хватает обязательных канонических полей",
  "Auto-validating mapped upload": "Запускаем автопроверку сопоставленной загрузки",
  "Applying normalized data": "Применяем нормализованные данные",
  "Parsing uploaded file": "Разбираем загруженный файл",
  "Mapping suggestions refreshed": "Подсказки по сопоставлению обновлены",
  "Mapping was updated": "Сопоставление обновлено",
  "Filename is required": "Нужно имя файла",
  "Unsupported source type": "Неподдерживаемый тип источника",
  "Upload file not found": "Файл загрузки не найден",
  "Upload batch not found": "Пакет загрузки не найден",
  "Apply is not supported for this source type": "Для этого типа источника применение недоступно",
  "Mapping template not found": "Шаблон сопоставления не найден",
};

function prettifyToken(value: string): string {
  return value.replaceAll("_", " ").trim();
}

export function formatSourceTypeLabel(sourceType: UploadJob["sourceType"] | string): string {
  return SOURCE_TYPE_LABELS[sourceType as UploadJob["sourceType"]] ?? prettifyToken(sourceType);
}

export function canonicalFieldLabel(fieldName: string | null | undefined): string {
  if (!fieldName) return "—";
  return CANONICAL_FIELD_LABELS[fieldName] ?? prettifyToken(fieldName);
}

export function uploadIssueCodeLabel(code: string | null | undefined): string {
  if (!code) return "—";
  return ISSUE_CODE_LABELS[code] ?? prettifyToken(code);
}

export function translateUploadIssueMessage(message: string): string {
  if (!message) return message;
  if (MESSAGE_LABELS[message]) {
    return MESSAGE_LABELS[message];
  }

  const requiredCanonical = message.match(/^Required canonical field '([^']+)' is not mapped$/);
  if (requiredCanonical) {
    return `Обязательное каноническое поле «${canonicalFieldLabel(requiredCanonical[1])}» не сопоставлено`;
  }

  const requiredField = message.match(/^Required field '([^']+)' is missing$/);
  if (requiredField) {
    return `Отсутствует обязательное поле «${canonicalFieldLabel(requiredField[1])}»`;
  }

  const unmatchedClient = message.match(/^Client '(.+)' is not matched$/);
  if (unmatchedClient) {
    return `Клиент «${unmatchedClient[1]}» не сопоставлен`;
  }

  const unmatchedSku = message.match(/^SKU '(.+)' is not matched$/);
  if (unmatchedSku) {
    return `SKU «${unmatchedSku[1]}» не сопоставлен`;
  }

  const numericField = message.match(/^(.+) must be numeric$/);
  if (numericField) {
    return `Поле «${canonicalFieldLabel(numericField[1])}» должно быть числом`;
  }

  const duplicateBatch = message.match(/^Upload duplicates previously seen batch (.+)$/);
  if (duplicateBatch) {
    return `Загрузка дублирует ранее полученный пакет ${duplicateBatch[1]}`;
  }

  return message;
}
