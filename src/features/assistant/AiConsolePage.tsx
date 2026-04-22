import { useState } from "react";
import { PageHeader, SectionTitle } from "@/components/ui-ext/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { askAssistant, SUGGESTED_PROMPTS } from "@/services/assistant.service";
import type { AiResponseMock } from "@/types";
import { Sparkles, ArrowUp, FileText, Layers, Building2, Boxes } from "lucide-react";
import { cn } from "@/lib/utils";

export default function AiConsolePage() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [responses, setResponses] = useState<AiResponseMock[]>([]);

  async function send(question: string) {
    if (!question.trim()) return;
    setQ("");
    setLoading(true);
    const r = await askAssistant({ question });
    setResponses((rs) => [r, ...rs]);
    setLoading(false);
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6">
        <PageHeader eyebrow="Ассистент" title="ИИ-консоль" description="Задавайте операционные вопросы по резерву, складу, поставкам и качеству данных. В ответе указываются использованные источники." />

        <section className="panel p-4">
          <form onSubmit={(e) => { e.preventDefault(); send(q); }} className="flex items-center gap-2">
            <Sparkles className="ml-1 h-4 w-4 text-brand" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Спросите о резерве, рисках склада, влиянии поставок…" className="h-10 border-0 bg-transparent text-sm focus-visible:ring-0" />
            <Button type="submit" size="sm" disabled={loading} className="h-9 bg-brand text-brand-foreground hover:bg-brand-hover">
              <ArrowUp className="h-3.5 w-3.5" />
            </Button>
          </form>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {SUGGESTED_PROMPTS.map((p) => (
              <button key={p} onClick={() => send(p)} className="rounded-md border border-line-subtle bg-surface-muted/60 px-2.5 py-1 text-xs text-ink-secondary hover:bg-surface-hover hover:text-ink">
                {p}
              </button>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          {loading && <div className="panel p-5 text-sm text-ink-muted">Думаю…</div>}
          {responses.map((r) => (
            <article key={r.id} className="panel p-5 animate-fade-in">
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Вопрос</div>
              <p className="mt-1 text-sm text-ink">{r.question}</p>
              <div className="mt-4 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Ответ</div>
              <p className="mt-1 text-sm leading-relaxed text-ink-secondary">{r.answer}</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div>
                  <SectionTitle className="!text-[10px]">Использованные источники</SectionTitle>
                  <ul className="mt-2 space-y-1.5">
                    {r.sources.map((s, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs text-ink-muted">
                        <FileText className="h-3 w-3" />
                        <span className="text-num text-ink-secondary">{s.label}</span>
                        <span className="text-ink-disabled">— {s.ref}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <SectionTitle className="!text-[10px]">Дальше</SectionTitle>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {r.followUps.map((f) => (
                      <button key={f} onClick={() => send(f)} className="rounded-md border border-line-subtle bg-surface-muted/60 px-2.5 py-1 text-xs text-ink-secondary hover:bg-surface-hover hover:text-ink">
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </article>
          ))}
        </section>
      </div>

      <aside className={cn("space-y-3 lg:sticky lg:top-20 lg:self-start")}>
        <SectionTitle>Контекст</SectionTitle>
        {[
          { icon: Building2, label: "Выбранный клиент", value: "Леман Про" },
          { icon: Boxes, label: "Выбранный SKU", value: "K-2650-CR" },
          { icon: Layers, label: "Выбранные файлы", value: "sales_2025_11.xlsx, inbound_dec.csv" },
        ].map((c) => (
          <div key={c.label} className="panel p-4">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-ink-muted">
              <c.icon className="h-3.5 w-3.5" />{c.label}
            </div>
            <div className="mt-1 text-sm font-medium text-ink">{c.value}</div>
          </div>
        ))}
      </aside>
    </div>
  );
}
