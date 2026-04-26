import { useEffect, useMemo, useState } from "react";
import { Search, Command, Bell, CircleUser, Sun, Moon, LogOut, ShieldCheck, ArrowRight } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useLocation, useNavigate } from "react-router-dom";
import { NAV_SECTIONS } from "@/lib/constants";
import { useTheme } from "@/lib/theme";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { LoginDialog } from "@/components/auth/LoginDialog";
import { useCurrentUserQuery, useLogoutAction } from "@/hooks/queries/use-auth";
import { hasCapability } from "@/lib/access";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";

const COMMAND_METADATA: Partial<Record<(typeof NAV_SECTIONS)[number]["path"], { description: string; keywords: string[] }>> = {
  "/": {
    description: "Сводка по резерву, рискам и свежести данных",
    keywords: ["главная", "обзор", "дашборд", "риски", "dashboard"],
  },
  "/reserve": {
    description: "Запустить расчёт резерва и разобрать критические позиции",
    keywords: ["резерв", "shortage", "coverage", "safety", "demand"],
  },
  "/sku": {
    description: "Открыть карточку SKU и анализ по артикулу",
    keywords: ["sku", "артикул", "товар", "каталог", "product"],
  },
  "/clients": {
    description: "Проверить сети DIY, экспозицию и проблемные позиции",
    keywords: ["клиенты", "сети", "DIY", "экспозиция", "client"],
  },
  "/stock": {
    description: "Покрытие, остатки и риск дефицита",
    keywords: ["склад", "покрытие", "stock", "coverage", "остатки"],
  },
  "/inbound": {
    description: "Входящие поставки, даты прихода и влияние на дефицит",
    keywords: ["поставка", "inbound", "eta", "доставка", "приход"],
  },
  "/uploads": {
    description: "Загрузка файлов, предпросмотр и статусы контура загрузки",
    keywords: ["upload", "ингест", "файл", "загрузка", "preview"],
  },
  "/mapping": {
    description: "Сопоставление колонок, шаблоны и алиасы",
    keywords: ["mapping", "сопоставление", "template", "alias", "поля"],
  },
  "/quality": {
    description: "Ошибки качества данных, уровни серьёзности и контекст источников",
    keywords: ["quality", "качество", "ошибки", "issues", "validation"],
  },
  "/ai": {
    description: "ИИ-консоль с объяснимыми ответами и трассировкой",
    keywords: ["assistant", "ai", "ии", "query", "trace"],
  },
  "/admin": {
    description: "Операционные панели, аудит, очереди и контроль окружения",
    keywords: ["admin", "операции", "очереди", "audit", "exports"],
  },
  "/settings": {
    description: "Сессия, настройки и конфигурация рабочего места",
    keywords: ["settings", "настройки", "theme", "auth", "session"],
  },
};

export function TopBar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { theme, toggle } = useTheme();
  const current = NAV_SECTIONS.find((s) => (s.path === "/" ? pathname === "/" : pathname.startsWith(s.path)));
  const [loginOpen, setLoginOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const { data: currentUser } = useCurrentUserQuery();
  const logout = useLogoutAction();
  const primaryRole = currentUser?.roles?.[0] ?? null;
  const commandItems = useMemo(
    () =>
      NAV_SECTIONS.filter((item) => !item.capability || !currentUser || hasCapability(currentUser, item.capability)).map((item) => ({
        ...item,
        description: COMMAND_METADATA[item.path]?.description ?? "Открыть раздел",
        keywords: COMMAND_METADATA[item.path]?.keywords ?? [],
      })),
    [currentUser],
  );

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((prev) => !prev);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  function openCommandPalette() {
    setCommandOpen(true);
  }

  function handleCommandSelect(path: string) {
    navigate(path);
    setCommandOpen(false);
  }

  return (
    <>
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
              placeholder="Быстрый переход и команды…"
              readOnly
              aria-label="Открыть быстрое меню"
              onClick={openCommandPalette}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  openCommandPalette();
                }
              }}
              className="h-9 cursor-pointer border-line-subtle bg-surface-panel pl-8 pr-16 text-sm placeholder:text-ink-muted"
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

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-9 gap-2 px-2 text-ink-muted hover:text-ink">
                <CircleUser className="h-4 w-4" />
                <span className="hidden max-w-[160px] truncate text-xs font-medium sm:inline">
                  {currentUser?.fullName ?? "Dev-сессия"}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              <DropdownMenuLabel className="space-y-1">
                <div className="text-xs font-medium text-ink">
                  {currentUser?.fullName ?? "Локальная dev-сессия"}
                </div>
                <div className="text-[11px] font-normal text-ink-muted">
                  {currentUser?.email ?? "Через X-Dev-User / user_admin"}
                </div>
                {primaryRole ? (
                  <div className="text-[11px] font-normal uppercase tracking-wide text-brand">
                    {primaryRole}
                  </div>
                ) : null}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="gap-2" onClick={() => setLoginOpen(true)}>
                <ShieldCheck className="h-4 w-4" />
                {currentUser ? "Сменить сессию" : "Войти"}
              </DropdownMenuItem>
              <DropdownMenuItem className="gap-2" onClick={() => logout()}>
                <LogOut className="h-4 w-4" />
                Выйти
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <LoginDialog open={loginOpen} onOpenChange={setLoginOpen} />
      <CommandDialog open={commandOpen} onOpenChange={setCommandOpen}>
        <CommandInput placeholder="Перейти к разделу, операции или панели…" />
        <CommandList>
          <CommandEmpty>Ничего не найдено. Попробуй название раздела, SKU, клиента или типа операции.</CommandEmpty>
          <CommandGroup heading="Разделы">
            {commandItems.map((item) => (
              <CommandItem
                key={item.path}
                value={`${item.label} ${item.keywords.join(" ")}`}
                onSelect={() => handleCommandSelect(item.path)}
                className="items-start gap-3 py-3"
              >
                <ArrowRight className="mt-0.5 h-4 w-4 text-ink-muted" />
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-medium text-ink">{item.label}</span>
                  <span className="truncate text-xs text-ink-muted">{item.description}</span>
                  <span className="sr-only">{item.keywords.join(" ")}</span>
                </div>
                <CommandShortcut>{item.path}</CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading="Подсказки">
            <CommandItem
              value="резерв дефицит критичные позиции reserve shortage"
              onSelect={() => handleCommandSelect("/reserve")}
              className="items-start gap-3 py-3"
            >
              <ArrowRight className="mt-0.5 h-4 w-4 text-ink-muted" />
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="truncate font-medium text-ink">Рассчитать резерв</span>
                <span className="truncate text-xs text-ink-muted">Запуск расчёта и разбор позиций ниже цели</span>
              </div>
            </CommandItem>
            <CommandItem
              value="загрузить файл ingestion mapping upload preview"
              onSelect={() => handleCommandSelect("/uploads")}
                className="items-start gap-3 py-3"
              >
                <ArrowRight className="mt-0.5 h-4 w-4 text-ink-muted" />
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-medium text-ink">Открыть контур загрузки</span>
                  <span className="truncate text-xs text-ink-muted">Загрузка файла, предпросмотр, сопоставление и применение</span>
                </div>
              </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
