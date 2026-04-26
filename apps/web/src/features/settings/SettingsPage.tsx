import { useEffect, useState, type DragEvent, type FormEvent } from "react";
import { PageHeader, SectionTitle } from "@/components/ui-ext/PageHeader";
import { useTheme } from "@/lib/theme";
import { Button } from "@/components/ui/button";
import { LoginDialog } from "@/components/auth/LoginDialog";
import {
  useCurrentUserQuery,
  useLogoutAction,
  useUpdateCurrentUserProfileMutation,
} from "@/hooks/queries/use-auth";
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
import { toast } from "sonner";

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
  const [profileForm, setProfileForm] = useState({
    firstName: "",
    lastName: "",
    currentPassword: "",
    newPassword: "",
  });
  const { data: currentUser } = useCurrentUserQuery();
  const updateProfile = useUpdateCurrentUserProfileMutation();
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

  useEffect(() => {
    if (!currentUser) return;
    setProfileForm((current) => ({
      ...current,
      firstName: currentUser.firstName,
      lastName: currentUser.lastName,
    }));
  }, [currentUser]);

  const handleProfileSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!currentUser) {
      setLoginOpen(true);
      return;
    }
    if (profileForm.newPassword && !profileForm.currentPassword) {
      toast.error("Укажите текущий пароль для смены пароля");
      return;
    }

    try {
      await updateProfile.mutateAsync({
        firstName: profileForm.firstName,
        lastName: profileForm.lastName,
        currentPassword: profileForm.currentPassword || undefined,
        newPassword: profileForm.newPassword || undefined,
      });
      setProfileForm((current) => ({ ...current, currentPassword: "", newPassword: "" }));
      toast.success("Профиль пользователя обновлён");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось обновить профиль");
    }
  };

  return (
    <>
      <PageHeader eyebrow="Рабочее пространство" title="Настройки" description="Личные значения по умолчанию, профиль пользователя и порядок рабочего меню." />

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

        <form className="panel p-5 space-y-4" onSubmit={handleProfileSubmit}>
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <SectionTitle>Пользователь</SectionTitle>
              <p className="text-xs leading-relaxed text-ink-muted">
                Данные синхронизируются с таблицей пользователей в БД. Роль назначается администратором.
              </p>
            </div>
            <span className="rounded-full border border-brand/25 bg-brand/10 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] text-brand">
              {currentUser?.roles?.[0] ?? "dev"}
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1.5 text-xs text-ink-muted">
              <span>Имя</span>
              <input
                value={profileForm.firstName}
                onChange={(event) => setProfileForm((current) => ({ ...current, firstName: event.target.value }))}
                className="h-10 w-full rounded-lg border border-line-subtle bg-surface-panel px-3 text-sm font-medium text-ink outline-none transition focus:border-brand/50"
                placeholder="Имя"
                disabled={!currentUser || updateProfile.isPending}
              />
            </label>
            <label className="space-y-1.5 text-xs text-ink-muted">
              <span>Фамилия</span>
              <input
                value={profileForm.lastName}
                onChange={(event) => setProfileForm((current) => ({ ...current, lastName: event.target.value }))}
                className="h-10 w-full rounded-lg border border-line-subtle bg-surface-panel px-3 text-sm font-medium text-ink outline-none transition focus:border-brand/50"
                placeholder="Фамилия"
                disabled={!currentUser || updateProfile.isPending}
              />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1.5 text-xs text-ink-muted">
              <span>Email</span>
              <input
                value={currentUser?.email ?? "Доступ в development через X-Dev-User: user_admin"}
                readOnly
                className="h-10 w-full rounded-lg border border-line-subtle bg-surface-muted/55 px-3 text-sm text-ink-secondary outline-none"
              />
            </label>
            <label className="space-y-1.5 text-xs text-ink-muted">
              <span>Роль</span>
              <input
                value={currentUser?.roles?.join(", ") || "dev"}
                readOnly
                className="h-10 w-full rounded-lg border border-line-subtle bg-surface-muted/55 px-3 text-sm text-ink-secondary outline-none"
              />
            </label>
          </div>

          <div className="rounded-xl border border-line-subtle bg-surface-muted/35 p-3 space-y-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
              Смена пароля
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1.5 text-xs text-ink-muted">
                <span>Текущий пароль</span>
                <input
                  type="password"
                  value={profileForm.currentPassword}
                  onChange={(event) => setProfileForm((current) => ({ ...current, currentPassword: event.target.value }))}
                  className="h-10 w-full rounded-lg border border-line-subtle bg-surface-panel px-3 text-sm text-ink outline-none transition focus:border-brand/50"
                  placeholder="Введите текущий пароль"
                  disabled={!currentUser || updateProfile.isPending}
                />
              </label>
              <label className="space-y-1.5 text-xs text-ink-muted">
                <span>Новый пароль</span>
                <input
                  type="password"
                  value={profileForm.newPassword}
                  onChange={(event) => setProfileForm((current) => ({ ...current, newPassword: event.target.value }))}
                  className="h-10 w-full rounded-lg border border-line-subtle bg-surface-panel px-3 text-sm text-ink outline-none transition focus:border-brand/50"
                  placeholder="Минимум 8 символов"
                  disabled={!currentUser || updateProfile.isPending}
                />
              </label>
            </div>
          </div>

          <div className="flex flex-wrap justify-between gap-2">
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="border-line-subtle bg-surface-panel"
                onClick={() => setLoginOpen(true)}
              >
                {currentUser ? "Сменить сессию" : "Войти"}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="border-line-subtle bg-surface-panel"
                onClick={() => logout()}
              >
                Выйти
              </Button>
            </div>
            <Button
              type="submit"
              size="sm"
              className="bg-brand text-brand-foreground hover:bg-brand-hover"
              disabled={!currentUser || updateProfile.isPending}
            >
              {updateProfile.isPending ? "Сохранение…" : "Сохранить профиль"}
            </Button>
          </div>
        </form>
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
