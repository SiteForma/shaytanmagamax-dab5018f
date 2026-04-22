import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { getUploadJobs } from "@/services/upload.service";
import type { UploadJob } from "@/types";
import { fmtBytes, fmtInt, fmtRelative } from "@/lib/formatters";
import { Upload, FileSpreadsheet } from "lucide-react";
import { cn } from "@/lib/utils";

const STATE_TONE: Record<UploadJob["state"], string> = {
  uploaded: "text-ink-muted",
  validating: "text-info",
  mapped: "text-info",
  issues_found: "text-warning",
  ready: "text-success",
};

const STATE_LABEL: Record<UploadJob["state"], string> = {
  uploaded: "загружен",
  validating: "проверка",
  mapped: "сопоставлен",
  issues_found: "есть проблемы",
  ready: "готов",
};

const SOURCE_LABEL: Record<UploadJob["sourceType"], string> = {
  sales: "продажи",
  stock: "склад",
  diy_clients: "клиенты DIY",
  category_structure: "структура категорий",
  inbound: "поставки",
  raw_report: "сырой отчёт",
};

export default function UploadCenterPage() {
  const [jobs, setJobs] = useState<UploadJob[]>([]);
  useEffect(() => { getUploadJobs().then(setJobs); }, []);

  return (
    <>
      <PageHeader eyebrow="Приём данных" title="Центр загрузки" description="Подключайте файлы продаж, склада, клиентов DIY, структуры категорий и поставок." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="panel flex h-48 flex-col items-center justify-center gap-3 border-dashed text-center">
            <div className="grid h-10 w-10 place-items-center rounded-lg border border-line-subtle bg-surface-muted text-brand">
              <Upload className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-medium text-ink">Перетащите файлы для загрузки</div>
              <div className="text-xs text-ink-muted">XLSX, CSV — до 50 МБ. Демо-конвейер без сервера.</div>
            </div>
          </div>
        </div>
        <div className="panel p-5">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Тип источника</div>
          <ul className="mt-3 space-y-1.5 text-sm">
            {["Продажи", "Склад", "Клиенты DIY", "Структура категорий", "Поставки", "Сырой отчёт"].map((s) => (
              <li key={s} className="flex items-center justify-between rounded-md border border-line-subtle bg-surface-muted/40 px-3 py-2 text-ink-secondary">
                <span>{s}</span>
                <span className="chip">канонический</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <section className="panel">
        <div className="border-b border-line-subtle px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">История загрузок</div>
        <ul className="divide-y divide-line-subtle">
          {jobs.map((j) => (
            <li key={j.id} className="flex items-center gap-3 px-4 py-3 text-sm">
              <FileSpreadsheet className="h-4 w-4 text-ink-muted" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-ink">{j.fileName}</div>
                <div className="text-xs text-ink-muted">{SOURCE_LABEL[j.sourceType]} · {fmtBytes(j.sizeBytes)} · {fmtInt(j.rows)} строк · {fmtRelative(j.uploadedAt)}</div>
              </div>
              <span className={cn("text-xs font-medium uppercase tracking-wide", STATE_TONE[j.state])}>{STATE_LABEL[j.state]}</span>
              {j.issues > 0 ? <span className="chip text-warning">{j.issues} проблем</span> : null}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
