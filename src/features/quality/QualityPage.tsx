import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { FilterChips } from "@/components/ui-ext/FilterChips";
import { getQualityIssues } from "@/services/quality.service";
import type { QualityIssue } from "@/types";
import { fmtRelative } from "@/lib/formatters";

const TYPE_LABEL: Record<QualityIssue["type"], string> = {
  duplicate: "дубликат",
  missing_sku: "нет SKU",
  unmatched_client: "клиент не сопоставлен",
  negative_stock: "отрицательный остаток",
  suspicious_spike: "подозрительный всплеск",
  missing_month: "пропущен месяц",
  category_mismatch: "несовпадение категории",
};

export default function QualityPage() {
  const [rows, setRows] = useState<QualityIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [sev, setSev] = useState<string>("all");

  useEffect(() => {
    setLoading(true);
    getQualityIssues({ severity: sev === "all" ? undefined : (sev as any) }).then((r) => { setRows(r); setLoading(false); });
  }, [sev]);

  const columns: ColumnDef<any>[] = [
    { accessorKey: "type", header: "Тип", cell: (i) => <span className="chip">{TYPE_LABEL[i.getValue() as QualityIssue["type"]]}</span> },
    { accessorKey: "entity", header: "Сущность", cell: (i) => <span className="text-num font-medium text-ink">{i.getValue() as string}</span> },
    { accessorKey: "description", header: "Описание", cell: (i) => translateDescription(i.getValue() as string) },
    { accessorKey: "source", header: "Источник", cell: (i) => <span className="text-xs text-ink-muted">{i.getValue() as string}</span> },
    { accessorKey: "detectedAt", header: "Обнаружено", cell: (i) => <span className="text-xs text-ink-muted">{fmtRelative(i.getValue() as string)}</span> },
    { accessorKey: "severity", header: "Важность", cell: (i) => <StatusBadge value={i.getValue() as any} /> },
  ];

  return (
    <>
      <PageHeader eyebrow="Доверие" title="Качество данных" description="Дубликаты, отсутствующие ссылки, отрицательные остатки, подозрительные всплески и расхождения категорий по всем источникам." />
      <FilterChips value={sev} onChange={setSev} allLabel="Все" options={[
        { value: "low", label: "Низкая" }, { value: "medium", label: "Средняя" }, { value: "high", label: "Высокая" }, { value: "critical", label: "Критичная" },
      ]} />
      <DataTable data={rows} columns={columns} loading={loading} searchPlaceholder="Поиск проблем…" density="compact" initialPageSize={20} />
    </>
  );
}

function translateDescription(d: string) {
  const map: Record<string, string> = {
    "Duplicate row detected for SKU/month combination": "Найдена дублирующая строка по сочетанию SKU/месяц",
    "SKU referenced in sales not present in master": "SKU из продаж отсутствует в мастер-каталоге",
    "Client name does not resolve to known DIY network": "Имя клиента не связано с известной сетью DIY",
    "Negative free stock value reported": "Получен отрицательный свободный остаток",
    "Monthly sales spike >5σ vs trailing 6m": "Всплеск месячных продаж >5σ относительно 6 мес.",
    "Gap detected in monthly sales series": "Пропуск в ряду месячных продаж",
    "Category in source disagrees with canonical category tree": "Категория источника расходится с каноническим деревом категорий",
  };
  return map[d] ?? d;
}
