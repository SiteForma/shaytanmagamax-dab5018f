// Number, currency, date formatters used across the workspace.
const compactFmt = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const intFmt = new Intl.NumberFormat("en-US");
const oneDecFmt = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function fmtInt(n: number) { return intFmt.format(n); }
export function fmtCompact(n: number) { return compactFmt.format(n); }
export function fmtMonths(n: number) { return `${oneDecFmt.format(n)} mo`; }
export function fmtPct(n: number) { return `${(n * 100).toFixed(0)}%`; }

export function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtRelative(iso: string) {
  const diff = (Date.now() - +new Date(iso)) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function fmtBytes(n: number) {
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}
