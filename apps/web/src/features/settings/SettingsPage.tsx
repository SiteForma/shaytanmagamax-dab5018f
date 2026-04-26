import { useState } from "react";
import { PageHeader, SectionTitle } from "@/components/ui-ext/PageHeader";
import { MagamaxLogo } from "@/components/brand/MagamaxLogo";
import { useTheme } from "@/lib/theme";
import { Button } from "@/components/ui/button";
import { LoginDialog } from "@/components/auth/LoginDialog";
import { useCurrentUserQuery, useLogoutAction } from "@/hooks/queries/use-auth";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [loginOpen, setLoginOpen] = useState(false);
  const { data: currentUser } = useCurrentUserQuery();
  const logout = useLogoutAction();
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

      <LoginDialog open={loginOpen} onOpenChange={setLoginOpen} />
    </>
  );
}
