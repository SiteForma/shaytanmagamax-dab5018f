import type { AiResponseMock } from "@/types";
import { latency } from "./_latency";

export interface AssistantContext {
  selectedClient?: string;
  selectedSku?: string;
  selectedFiles?: string[];
}

export interface AssistantPayload {
  question: string;
  context?: AssistantContext;
}

const CANNED: { match: RegExp; build: (q: string) => Omit<AiResponseMock, "id" | "createdAt"> }[] = [
  {
    match: /леман|leman/i,
    build: (q) => ({
      question: q,
      answer:
        "Для «Леман Про» на горизонте 3 месяца с коэффициентом безопасности 1,1 внимания требуют 38 SKU: 12 — критичных (покрытие < 0,6 мес.), 18 — на внимании (покрытие < 1 мес.), 8 — частично закрываются поставками в течение 60 дней. Общий дефицит резерва — 9 420 шт. Наиболее уязвимая категория — направляющие для ящиков (4 210 шт. дефицита).",
      sources: [
        { label: "calculateReserve(client=client_2, months=3, safety=1.1)", ref: "reserve.service" },
        { label: "stock_snapshot_shch.csv", ref: "uploads/u2" },
        { label: "inbound_dec.csv", ref: "uploads/u4" },
      ],
      followUps: [
        "Показать только критичные позиции по «Леман Про»",
        "Какие поставки закрывают дефицит «Леман Про»?",
        "Сравнить уязвимость «Леман Про» и OBI",
      ],
    }),
  },
  {
    match: /недо.?покрыт|недо.?резерв|under/i,
    build: (q) => ({
      question: q,
      answer:
        "По всем сетям DIY 184 позиции находятся ниже целевого резерва. Топ-3 наиболее уязвимых сетей: «Леруа Мерлен» (62 позиции), «Леман Про» (38), OBI (29). У 41 из этих позиций ближайшие поставки в течение 60 дней полностью или частично закрывают разрыв.",
      sources: [
        { label: "DashboardOverview.topRiskSkus", ref: "dashboard.service" },
        { label: "InboundTimeline (eta < 60д)", ref: "inbound.service" },
      ],
      followUps: [
        "Оставить только позиции без покрытия поставкой",
        "Сгруппировать уязвимость по категориям",
        "Открыть калькулятор резерва с этими параметрами",
      ],
    }),
  },
  {
    match: /риск.*sku|sku.*риск|stock risk/i,
    build: (q) => ({
      question: q,
      answer:
        "У этого SKU средний спрос за 6 месяцев — 412 шт./мес. Свободный остаток — 240 шт. (покрытие 0,58 мес.), это ниже минимального порога в 1 месяц. Подтверждена одна поставка на 1 800 шт. с прибытием через 18 дней — она поднимает прогнозное покрытие до 4,9 мес. Класс риска: «Внимание», смягчён ожидаемой поставкой.",
      sources: [
        { label: "monthlySales(sku)", ref: "sku.service" },
        { label: "STOCK_SNAPSHOTS", ref: "mocks/stock" },
        { label: "inbound[sku]", ref: "inbound.service" },
      ],
      followUps: ["Открыть карточку SKU", "Показать разбивку по клиентам", "Добавить в наблюдение"],
    }),
  },
  {
    match: /поставк.*закр|закр.*дефицит|inbound.*close/i,
    build: (q) => ({
      question: q,
      answer:
        "23 поставки в ближайшие 60 дней закроют 64% текущего дефицита резерва (24 580 из 38 420 шт.). 6 поставок сейчас помечены как «Задержка» или «Не определено» и составляют 7 120 шт. под риском.",
      sources: [
        { label: "InboundTimeline", ref: "inbound.service" },
        { label: "DashboardSummary.totalReserveShortage", ref: "dashboard.service" },
      ],
      followUps: ["Показать только задержанные поставки", "Сгруппировать влияние по клиентам", "Экспортировать план"],
    }),
  },
];

export async function askAssistant(payload: AssistantPayload): Promise<AiResponseMock> {
  await latency(700);
  const matched = CANNED.find((c) => c.match.test(payload.question));
  const base =
    matched?.build(payload.question) ??
    {
      question: payload.question,
      answer:
        "Я могу анализировать покрытие резерва, риски склада, влияние поставок, уязвимость DIY-сетей и проблемы качества данных. Спросите про конкретного клиента, SKU, категорию или горизонт — например: «Рассчитай резерв для Леман Про на 3 месяца» или «Какие поставки закроют текущий дефицит?».",
      sources: [{ label: "Контракт знаний", ref: "assistant.service" }],
      followUps: [
        "Рассчитай резерв для «Леман Про» на 3 месяца",
        "Покажи позиции с недопокрытием по сетям DIY",
        "Какие поставки закроют текущий дефицит?",
      ],
    };

  return { ...base, id: `ai_${Date.now()}`, createdAt: new Date().toISOString() };
}

export const SUGGESTED_PROMPTS = [
  "Рассчитай резерв для «Леман Про» на 3 месяца по этим SKU",
  "Покажи позиции с недопокрытием по сетям DIY",
  "Объясни риск склада для SKU 12345",
  "Какие поставки закроют текущий дефицит?",
];
