import { useState, type DragEvent } from "react";
import { PageHeader, SectionTitle } from "@/components/ui-ext/PageHeader";
import { MagamaxLogo } from "@/components/brand/MagamaxLogo";
import { useTheme } from "@/lib/theme";
import { Button } from "@/components/ui/button";
import { LoginDialog } from "@/components/auth/LoginDialog";
import { useCurrentUserQuery, useLogoutAction } from "@/hooks/queries/use-auth";
import { NAV_SECTIONS } from "@/lib/constants";
import { hasCapability } from "@/lib/access";
import {
  DEFAULT_SIDEBAR_MENU_LABELS,
  applyNavLabels,
  moveSidebarMenuPath,
  orderNavItems,
  renameSidebarMenuPath,
  useSidebarMenuLabels,
  useSidebarMenuOrder,
} from "@/lib/navigation-preferences";
import {
  Boxes,
  Building2,
  Calculator,
  GripVertical,
  LayoutDashboard,
  RotateCcw,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Truck,
  Upload,
  Warehouse,
  Workflow,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ICONS = {
  LayoutDashboard,
  Calculator,
  Boxes,
  Building2,
  Warehouse,
  Truck,
  Upload,
  Workflow,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Settings,
} as const;

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [loginOpen, setLoginOpen] = useState(false);
  const [draggedPath, setDraggedPath] = useState<string | null>(null);
  const { data: currentUser } = useCurrentUserQuery();
  const logout = useLogoutAction();
  const { order, setOrder, resetOrder } = useSidebarMenuOrder();
  const { labels, setLabels, resetLabels } = useSidebarMenuLabels();
  const menuItems = applyNavLabels(
    orderNavItems(
      NAV_SECTIONS.filter((item) => !currentUser || !item.capability || hasCapability(currentUser, item.capability)),
      order,
    ),
    labels,
  );

  const handleDragStart = (event: DragEvent<HTMLDivElement>, path: string) => {
    setDraggedPath(path);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", path);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>, targetPath: string) => {
    event.preventDefault();
    const activePath = draggedPath ?? event.dataTransfer.getData("text/plain");
    if (activePath) setOrder(moveSidebarMenuPath(order, activePath, targetPath));
    setDraggedPath(null);
  };

  return (
    <>
      <PageHeader eyebrow="Рабочее пространство" title="Настройки" description="Личные значения по умолчанию: тема, плотность таблиц, горизонт резерва, статус брендовых ассетов." />

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="panel p-5 space-y-4">
          <SectionTitle>Значения по умолчанию</SectionTitle>
          {[
            {
              label: "Тема",
              control: (
                <select
                  value={theme}
                  onChange={(e) => setTheme(e.target.value as "dark" | "light")}
                  className="rounded-md border border-line-subtle bg-surface-panel px-2 py-1 text-sm focus-ring"
                >
                  <option value="dark">Тёмная</option>
                  <option value="light">Светлая</option>
                </select>
              ),
            },
            { label: "Плотность таблицы", control: <select className="rounded-md border border-line-subtle bg-surface-panel px-2 py-1 text-sm focus-ring"><option>Компактная</option><option>Стандартная</option><option>Просторная</option></select> },
            { label: "Горизонт резерва", control: <select className="rounded-md border border-line-subtle bg-surface-panel px-2 py-1 text-sm focus-ring"><option>3 месяца</option><option>2 месяца</option></select> },
            { label: "Коэффициент безопасности", control: <span className="text-num text-sm">×1,10</span> },
            { label: "Группировка по умолчанию", control: <select className="rounded-md border border-line-subtle bg-surface-panel px-2 py-1 text-sm focus-ring"><option>По клиенту</option><option>По категории</option><option>Без группировки</option></select> },
            { label: "Уведомления", control: <select className="rounded-md border border-line-subtle bg-surface-panel px-2 py-1 text-sm focus-ring"><option>Только критичные</option><option>Все</option><option>Отключены</option></select> },
          ].map((r) => (
            <div key={r.label} className="flex items-center justify-between border-b border-line-subtle/60 pb-3 last:border-0">
              <span className="text-sm text-ink-secondary">{r.label}</span>
              {r.control}
            </div>
          ))}
        </div>

        <div className="panel p-5 space-y-4">
          <SectionTitle>Брендовый ассет</SectionTitle>
          <div className="rounded-lg border border-line-subtle bg-surface-muted/50 p-4">
            <MagamaxLogo />
          </div>
          <p className="text-xs text-ink-muted">Используется оригинальный знак MAGAMAX и отдельный theme-aware wordmark без фоновой подложки. Для замены обновляйте файлы <span className="text-num">apps/web/src/assets/magamax-mark.png</span> и <span className="text-num">apps/web/src/assets/magamax-wordmark-*.png</span>.</p>
          <div className="flex items-center justify-between rounded-md border border-line-subtle bg-surface-muted/50 px-3 py-2 text-xs">
            <span className="text-ink-muted">Основной цвет бренда</span>
            <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-brand" /><span className="text-num">#FF671F</span></span>
          </div>

          <div className="rounded-lg border border-line-subtle bg-surface-muted/50 p-4 space-y-3">
            <SectionTitle className="!text-[11px]">Сессия</SectionTitle>
            <div className="space-y-1 text-sm">
              <div className="font-medium text-ink">{currentUser?.fullName ?? "Локальная dev-сессия"}</div>
              <div className="text-xs text-ink-muted">
                {currentUser?.email ?? "Доступ в development через X-Dev-User: user_admin"}
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="border-line-subtle bg-surface-panel"
                onClick={() => setLoginOpen(true)}
              >
                {currentUser ? "Сменить сессию" : "Войти"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-line-subtle bg-surface-panel"
                onClick={() => logout()}
              >
                Выйти
              </Button>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-4">
        <div className="panel p-5 space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1">
              <SectionTitle>Порядок левого меню</SectionTitle>
              <p className="max-w-2xl text-xs leading-relaxed text-ink-muted">
                Перетащите пункт выше или ниже. Порядок сохраняется для этого браузера и сразу применяется в левом сайдбаре.
              </p>
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="border-line-subtle bg-surface-panel"
              onClick={resetOrder}
            >
              <RotateCcw className="mr-2 h-3.5 w-3.5" />
              Сбросить порядок
            </Button>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {menuItems.map((item, index) => {
              const Icon = NAV_ICONS[item.icon];
              const isDragging = draggedPath === item.path;
              return (
                <div
                  key={item.path}
                  draggable
                  onDragStart={(event) => handleDragStart(event, item.path)}
                  onDragEnd={() => setDraggedPath(null)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => handleDrop(event, item.path)}
                  className={cn(
                    "group flex cursor-grab items-center gap-3 rounded-xl border border-line-subtle bg-surface-muted/45 px-3 py-2.5 transition",
                    "hover:border-brand/45 hover:bg-surface-muted active:cursor-grabbing",
                    isDragging && "scale-[0.99] border-brand/60 opacity-50",
                  )}
                  aria-label={`Перетащить пункт меню ${item.label}`}
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-surface-panel text-[11px] text-ink-muted">
                    {index + 1}
                  </span>
                  <Icon className="h-4 w-4 shrink-0 text-brand" />
                  <div className="min-w-0 flex-1 space-y-1">
                    <label className="sr-only" htmlFor={`menu-label-${item.path.replace(/\W+/g, "-")}`}>
                      Название пункта меню {DEFAULT_SIDEBAR_MENU_LABELS[item.path]}
                    </label>
                    <input
                      id={`menu-label-${item.path.replace(/\W+/g, "-")}`}
                      value={item.label}
                      maxLength={48}
                      onChange={(event) =>
                        setLabels(renameSidebarMenuPath(labels, item.path, event.target.value))
                      }
                      onClick={(event) => event.stopPropagation()}
                      onDragStart={(event) => event.preventDefault()}
                      className="h-8 w-full rounded-lg border border-transparent bg-surface-panel/60 px-2 text-sm font-medium text-ink outline-none transition focus:border-brand/50 focus:bg-surface-panel"
                    />
                    <div className="truncate px-2 text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                      {item.path}
                    </div>
                  </div>
                  <GripVertical className="h-4 w-4 shrink-0 text-ink-muted opacity-60 transition group-hover:opacity-100" />
                </div>
              );
            })}
          </div>
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="text-ink-muted hover:text-ink"
              onClick={resetLabels}
            >
              Сбросить названия
            </Button>
          </div>
        </div>
      </section>

      <LoginDialog open={loginOpen} onOpenChange={setLoginOpen} />
    </>
  );
}
