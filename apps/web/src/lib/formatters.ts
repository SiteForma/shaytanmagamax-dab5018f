// Числа, даты, относительное время — всё на русском.
const compactFmt = new Intl.NumberFormat("ru-RU", { notation: "compact", maximumFractionDigits: 1 });
const intFmt = new Intl.NumberFormat("ru-RU");
const oneDecFmt = new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function fmtInt(n: number) { return intFmt.format(n); }
export function fmtCompact(n: number) { return compactFmt.format(n); }
export function fmtMonths(n: number) { return `${oneDecFmt.format(n)} мес.`; }
export function fmtPct(n: number) { return `${(n * 100).toFixed(0)}%`; }

export function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" });
}

function plural(n: number, forms: [string, string, string]) {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return forms[2];
  if (b > 1 && b < 5) return forms[1];
  if (b === 1) return forms[0];
  return forms[2];
}

export function fmtRelative(iso: string) {
  const diff = (Date.now() - +new Date(iso)) / 1000;
  if (diff < 60) return "только что";
  if (diff < 3600) {
    const m = Math.floor(diff / 60);
    return `${m} ${plural(m, ["минуту", "минуты", "минут"])} назад`;
  }
  if (diff < 86400) {
    const h = Math.floor(diff / 3600);
    return `${h} ${plural(h, ["час", "часа", "часов"])} назад`;
  }
  const d = Math.floor(diff / 86400);
  return `${d} ${plural(d, ["день", "дня", "дней"])} назад`;
}

export function fmtBytes(n: number) {
  const u = ["Б", "КБ", "МБ", "ГБ"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}
