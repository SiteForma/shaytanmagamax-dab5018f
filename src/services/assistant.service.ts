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

const CANNED_RESPONSES: { match: RegExp; build: (q: string) => Omit<AiResponseMock, "id" | "createdAt"> }[] = [
  {
    match: /reserve.*leman|leman.*reserve/i,
    build: (q) => ({
      question: q,
      answer:
        "For Leman Pro on a 3-month horizon with safety factor 1.1, 38 SKUs require attention: 12 are critical (coverage < 0.6 months), 18 are warning (coverage < 1 month), and 8 are partially covered by inbound deliveries within 60 days. Total reserve shortage is 9,420 units. The category most exposed is Drawer slides (4,210 units short).",
      sources: [
        { label: "calculateReserve(client=client_2, months=3, safety=1.1)", ref: "reserve.service" },
        { label: "stock_snapshot_shch.csv", ref: "uploads/u2" },
        { label: "inbound_dec.csv", ref: "uploads/u4" },
      ],
      followUps: [
        "Show only critical positions for Leman Pro",
        "Which inbound deliveries close Leman Pro shortages?",
        "Compare Leman Pro vs OBI Russia exposure",
      ],
    }),
  },
  {
    match: /under.?cover|under.?reserve/i,
    build: (q) => ({
      question: q,
      answer:
        "Across all DIY networks, 184 positions are currently under their reserve target. The top 3 most exposed networks are Leroy Merlin (62 positions), Leman Pro (38), and OBI Russia (29). 41 of these positions have inbound deliveries within the next 60 days that fully or partially close the gap.",
      sources: [
        { label: "DashboardOverview.topRiskSkus", ref: "dashboard.service" },
        { label: "InboundTimeline (eta < 60d)", ref: "inbound.service" },
      ],
      followUps: [
        "Filter to positions with no inbound coverage",
        "Group exposure by category",
        "Open Reserve Calculator with these inputs",
      ],
    }),
  },
  {
    match: /stock risk.*sku|sku.*risk/i,
    build: (q) => ({
      question: q,
      answer:
        "This SKU has trailing-6-month average demand of 412 units/month. Free stock is 240 units (coverage 0.58 months), which falls below the 1-month safety floor. One inbound delivery of 1,800 units is confirmed for ETA in 18 days, lifting projected coverage to 4.9 months. Risk classification: warning, downgraded by inbound.",
      sources: [
        { label: "monthlySales(sku)", ref: "sku.service" },
        { label: "STOCK_SNAPSHOTS", ref: "mocks/stock" },
        { label: "inbound[sku]", ref: "inbound.service" },
      ],
      followUps: ["Open SKU detail", "Show client split", "Add to watchlist"],
    }),
  },
  {
    match: /inbound.*close|close.*shortage/i,
    build: (q) => ({
      question: q,
      answer:
        "23 inbound deliveries scheduled within the next 60 days will close 64% of current reserve shortage (24,580 of 38,420 units). 6 deliveries are currently flagged as 'delayed' or 'uncertain' and represent 7,120 units of at-risk relief.",
      sources: [
        { label: "InboundTimeline", ref: "inbound.service" },
        { label: "DashboardSummary.totalReserveShortage", ref: "dashboard.service" },
      ],
      followUps: ["Show only delayed deliveries", "Group impact by client", "Export plan"],
    }),
  },
];

export async function askAssistant(payload: AssistantPayload): Promise<AiResponseMock> {
  await latency(700);
  const matched = CANNED_RESPONSES.find((c) => c.match.test(payload.question));
  const base =
    matched?.build(payload.question) ??
    {
      question: payload.question,
      answer:
        "I can analyze reserve coverage, stock risk, inbound impact, DIY-network exposure and data quality issues. Try asking about a specific client, SKU, category, or horizon — for example: \"Calculate reserve for Leman Pro for 3 months\" or \"Which inbound deliveries will close current shortages?\".",
      sources: [{ label: "Knowledge contract", ref: "assistant.service" }],
      followUps: [
        "Calculate reserve for Leman Pro for 3 months",
        "Show which positions are under-covered for DIY clients",
        "Which inbound deliveries will close current shortages?",
      ],
    };

  return {
    ...base,
    id: `ai_${Date.now()}`,
    createdAt: new Date().toISOString(),
  };
}

export const SUGGESTED_PROMPTS = [
  "Calculate reserve for Leman Pro for 3 months for these SKUs",
  "Show which positions are under-covered for DIY clients",
  "Explain stock risk for SKU 12345",
  "Which inbound deliveries will close current shortages?",
];
