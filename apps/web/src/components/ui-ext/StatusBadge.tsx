import { cn } from "@/lib/utils";
import type { ReserveStatus, DeliveryStatus, QualitySeverity } from "@/types";

const STYLES: Record<string, string> = {
  critical:      "bg-danger/15 text-danger border-danger/30",
  warning:       "bg-warning/15 text-warning border-warning/30",
  healthy:       "bg-success/15 text-success border-success/30",
  inactive:      "bg-surface-muted text-ink-muted border-line-subtle",
  overstocked:   "bg-info/15 text-info border-info/30",
  enough:        "bg-success/15 text-success border-success/30",
  no_history:    "bg-surface-muted text-ink-muted border-line-subtle",
  inbound_helps: "bg-info/15 text-info border-info/30",

  confirmed:  "bg-success/15 text-success border-success/30",
  in_transit: "bg-info/15 text-info border-info/30",
  delayed:    "bg-warning/15 text-warning border-warning/30",
  uncertain:  "bg-danger/15 text-danger border-danger/30",

  low:    "bg-surface-muted text-ink-secondary border-line-subtle",
  medium: "bg-info/15 text-info border-info/30",
  high:   "bg-warning/15 text-warning border-warning/30",
  info:   "bg-surface-muted text-ink-secondary border-line-subtle",
  error:  "bg-warning/15 text-warning border-warning/30",

  queued:    "bg-surface-muted text-ink-secondary border-line-subtle",
  running:   "bg-info/15 text-info border-info/30",
  failed:    "bg-danger/15 text-danger border-danger/30",
  completed: "bg-success/15 text-success border-success/30",
  skipped:   "bg-surface-muted text-ink-secondary border-line-subtle",

  uploaded:              "bg-surface-muted text-ink-secondary border-line-subtle",
  parsing:               "bg-info/15 text-info border-info/30",
  source_confirmation_required: "bg-warning/15 text-warning border-warning/30",
  mapping_required:      "bg-warning/15 text-warning border-warning/30",
  validating:            "bg-info/15 text-info border-info/30",
  issues_found:          "bg-warning/15 text-warning border-warning/30",
  ready_to_review:       "bg-info/15 text-info border-info/30",
  ready_to_apply:        "bg-success/15 text-success border-success/30",
  applying:              "bg-info/15 text-info border-info/30",
  applied:               "bg-success/15 text-success border-success/30",
  applied_with_warnings: "bg-warning/15 text-warning border-warning/30",
  normalized:            "bg-success/15 text-success border-success/30",
  mapped:                "bg-info/15 text-info border-info/30",
  ready:                 "bg-success/15 text-success border-success/30",
};

const LABELS: Record<string, string> = {
  critical: "Критично",
  warning: "Внимание",
  healthy: "Норма",
  inactive: "Неактивно",
  overstocked: "Избыток",
  enough: "Норма",
  no_history: "Нет истории",
  inbound_helps: "Закрывает поставка",
  confirmed: "Подтверждено",
  in_transit: "В пути",
  delayed: "Задержка",
  uncertain: "Не определено",
  low: "Низкая",
  medium: "Средняя",
  high: "Высокая",
  info: "Инфо",
  error: "Ошибка",

  queued: "В очереди",
  running: "В работе",
  failed: "С ошибкой",
  completed: "Готово",
  skipped: "Пропущено",

  uploaded: "Загружен",
  parsing: "Разбор",
  source_confirmation_required: "Подтвердите тип",
  mapping_required: "Нужно сопоставление",
  validating: "Проверка",
  issues_found: "Есть проблемы",
  ready_to_review: "Готов к просмотру",
  ready_to_apply: "Готов к применению",
  applying: "Применение",
  applied: "Применён",
  applied_with_warnings: "Применён с предупреждениями",
  normalized: "Нормализован",
  mapped: "Сопоставлен",
  ready: "Готов",
};

export type StatusValue = ReserveStatus | DeliveryStatus | QualitySeverity | string;

export function StatusBadge({ value, className }: { value: StatusValue; className?: string }) {
  const style = STYLES[value] ?? "bg-surface-muted text-ink-muted border-line-subtle";
  const label = LABELS[value] ?? value;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide",
        style,
        className,
      )}
    >
      <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {label}
    </span>
  );
}
