import { useEffect, useState } from "react";
import {
  Area, AreaChart, CartesianGrid, Bar, BarChart, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const BRAND = "hsl(18 100% 56%)";

function readCss(name: string, fallback: string) {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v ? `hsl(${v})` : fallback;
}

/** Хук, который перечитывает токены при смене темы (наблюдает за классами <html>). */
function useChartTokens() {
  const compute = () => ({
    grid: readCss("--border-subtle", "hsl(24 6% 18%)"),
    axis: readCss("--text-muted", "hsl(30 6% 46%)"),
    tooltipBg: readCss("--bg-elevated", "hsl(24 8% 9%)"),
    tooltipBorder: readCss("--border-strong", "hsl(24 6% 22%)"),
    tooltipText: readCss("--text-primary", "hsl(30 12% 96%)"),
    neutralBar: readCss("--bg-hover", "hsl(24 6% 28%)"),
  });
  const [t, setT] = useState(compute);
  useEffect(() => {
    const obs = new MutationObserver(() => setT(compute()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return t;
}

function tooltipStyles(t: ReturnType<typeof useChartTokens>) {
  return {
    background: t.tooltipBg,
    border: `1px solid ${t.tooltipBorder}`,
    borderRadius: 8,
    padding: "8px 10px",
    color: t.tooltipText,
    fontSize: 12,
    boxShadow: "0 8px 24px -12px rgba(0,0,0,0.35)",
  };
}

export function CoverageAreaChart({ data }: { data: { month: string; coverage: number; target: number }[] }) {
  const t = useChartTokens();
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ left: -16, right: 8, top: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="cv" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={BRAND} stopOpacity={0.35} />
            <stop offset="100%" stopColor={BRAND} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" stroke={t.axis} fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke={t.axis} fontSize={11} tickLine={false} axisLine={false} width={32} />
        <Tooltip contentStyle={tooltipStyles(t)} cursor={{ stroke: BRAND, strokeOpacity: 0.2 }} />
        <Area type="monotone" dataKey="coverage" stroke={BRAND} strokeWidth={2} fill="url(#cv)" />
        <Line type="monotone" dataKey="target" stroke={t.axis} strokeWidth={1} strokeDasharray="4 4" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function InboundShortageBarChart({ data }: { data: { month: string; inbound: number; shortage: number }[] }) {
  const t = useChartTokens();
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ left: -16, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" stroke={t.axis} fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke={t.axis} fontSize={11} tickLine={false} axisLine={false} width={36} />
        <Tooltip contentStyle={tooltipStyles(t)} cursor={{ fill: t.neutralBar, fillOpacity: 0.25 }} />
        <Bar dataKey="shortage" fill={t.neutralBar} radius={[3, 3, 0, 0]} />
        <Bar dataKey="inbound" fill={BRAND} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function MonthlySalesLineChart({ data }: { data: { month: string; qty: number }[] }) {
  const t = useChartTokens();
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ left: -16, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" stroke={t.axis} fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke={t.axis} fontSize={11} tickLine={false} axisLine={false} width={36} />
        <Tooltip contentStyle={tooltipStyles(t)} cursor={{ stroke: BRAND, strokeOpacity: 0.25 }} />
        <Line type="monotone" dataKey="qty" stroke={BRAND} strokeWidth={2} dot={{ r: 2.5, fill: BRAND }} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
