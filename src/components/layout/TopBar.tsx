import { Search, Command, Bell, CircleUser, Sun, Moon } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useLocation } from "react-router-dom";
import { NAV_SECTIONS } from "@/lib/constants";
import { useTheme } from "@/lib/theme";

export function TopBar() {
  const { pathname } = useLocation();
  const { theme, toggle } = useTheme();
  const current = NAV_SECTIONS.find((s) => (s.path === "/" ? pathname === "/" : pathname.startsWith(s.path)));

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line-subtle bg-surface/80 px-4 backdrop-blur supports-[backdrop-filter]:bg-surface/60">
      <SidebarTrigger className="-ml-1 h-8 w-8 text-ink-muted hover:text-ink" />

      <div className="hidden items-center gap-2 text-xs text-ink-muted md:flex">
        <span>Рабочее пространство</span>
        <span className="text-ink-disabled">/</span>
        <span className="text-ink">{current?.label ?? "Обзор"}</span>
      </div>

      <div className="ml-auto flex flex-1 items-center justify-end gap-2 sm:max-w-md">
        <div className="relative hidden flex-1 sm:block">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-muted" />
          <Input
            placeholder="Поиск SKU, клиентов, поставок…"
            className="h-9 border-line-subtle bg-surface-panel pl-8 pr-16 text-sm placeholder:text-ink-muted"
          />
          <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 rounded border border-line-subtle bg-surface-muted px-1.5 py-0.5 text-[10px] text-ink-muted sm:inline-flex">
            <Command className="h-2.5 w-2.5" />K
          </kbd>
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={toggle}
          aria-label={theme === "dark" ? "Включить светлую тему" : "Включить тёмную тему"}
          className="h-9 w-9 text-ink-muted hover:text-ink"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
        <Button variant="ghost" size="icon" aria-label="Уведомления" className="h-9 w-9 text-ink-muted hover:text-ink">
          <Bell className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Профиль" className="h-9 w-9 text-ink-muted hover:text-ink">
          <CircleUser className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
