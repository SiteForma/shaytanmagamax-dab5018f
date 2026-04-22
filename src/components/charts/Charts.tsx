import {
  Area,
  AreaChart,
  CartesianGrid,
  Bar,
  BarChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const BRAND = "hsl(18 100% 56%)";
const NEUTRAL = "hsl(30 6% 56%)";
const GRID = "hsl(24 6% 18%)";
const AXIS = "hsl(30 6% 46%)";

const tooltipStyles = {
  background: "hsl(24 8% 9%)",
  border: "1px solid hsl(24 6% 22%)",
  borderRadius: 8,
  padding: "8px 10px",
  color: "hsl(30 12% 96%)",
  fontSize: 12,
  boxShadow: "0 8px 24px -12px rgba(0,0,0,0.6)",
};

export function CoverageAreaChart({ data }: { data: { month: string; coverage: number; target: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ left: -16, right: 8, top: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="cv" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={BRAND} stopOpacity={0.35} />
            <stop offset="100%" stopColor={BRAND} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} width={32} />
        <Tooltip contentStyle={tooltipStyles} cursor={{ stroke: BRAND, strokeOpacity: 0.2 }} />
        <Area type="monotone" dataKey="coverage" stroke={BRAND} strokeWidth={2} fill="url(#cv)" />
        <Line type="monotone" dataKey="target" stroke={NEUTRAL} strokeWidth={1} strokeDasharray="4 4" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function InboundShortageBarChart({ data }: { data: { month: string; inbound: number; shortage: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ left: -16, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} width={36} />
        <Tooltip contentStyle={tooltipStyles} cursor={{ fill: "hsl(24 6% 14% / 0.4)" }} />
        <Bar dataKey="shortage" fill="hsl(24 6% 28%)" radius={[3, 3, 0, 0]} />
        <Bar dataKey="inbound" fill={BRAND} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function MonthlySalesLineChart({ data }: { data: { month: string; qty: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ left: -16, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke={AXIS} fontSize={11} tickLine={false} axisLine={false} width={36} />
        <Tooltip contentStyle={tooltipStyles} cursor={{ stroke: BRAND, strokeOpacity: 0.25 }} />
        <Line type="monotone" dataKey="qty" stroke={BRAND} strokeWidth={2} dot={{ r: 2.5, fill: BRAND }} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
