import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Building2, ShieldCheck } from "lucide-react";
import { MagamaxLogo } from "@/components/brand/MagamaxLogo";
import { LoginFormPanel } from "@/components/auth/LoginFormPanel";
import { useCurrentUserQuery } from "@/hooks/queries/use-auth";
import { isStrictAuthEnabled } from "@/lib/auth/config";
import { getCurrentSession } from "@/services/auth.service";

export default function LoginPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const strictAuth = isStrictAuthEnabled();
  const currentUserQuery = useCurrentUserQuery();
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";

  if (!strictAuth) {
    return <Navigate to="/" replace />;
  }

  if (getCurrentSession() && currentUserQuery.data) {
    return <Navigate to={from} replace />;
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto grid min-h-screen max-w-[1180px] grid-cols-1 gap-10 px-6 py-10 lg:grid-cols-[1.15fr_420px] lg:px-10">
        <section className="flex flex-col justify-between rounded-[28px] border border-line-subtle bg-[radial-gradient(circle_at_top_left,rgba(255,103,31,0.18),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0))] p-8 shadow-[0_24px_80px_-36px_rgba(0,0,0,0.55)]">
          <div className="space-y-6">
            <MagamaxLogo className="items-center" />
            <div className="max-w-[560px] space-y-4">
              <div className="text-[11px] uppercase tracking-[0.18em] text-ink-muted">
                MAGAMAX / Shaytan Machine
              </div>
              <h1 className="text-4xl font-semibold tracking-tight text-ink">
                Внутренняя платформа резерва, покрытия и ingestion-процессов.
              </h1>
              <p className="text-base leading-relaxed text-ink-secondary">
                Доступ к расчётам резерва, качеству данных, загрузкам, сопоставлению и операционной аналитике
                защищён общей рабочей сессией.
              </p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {[
              {
                icon: ShieldCheck,
                title: "Защищённый контур",
                text: "Все основные рабочие маршруты и API требуют сессию, без dev-fallback в production.",
              },
              {
                icon: Building2,
                title: "Операционный доступ",
                text: "Одна сессия для обзора, резерва, склада, загрузок и assistant-консоли.",
              },
            ].map((item) => (
              <div key={item.title} className="rounded-2xl border border-line-subtle bg-surface/60 p-4 backdrop-blur">
                <item.icon className="h-4 w-4 text-brand" />
                <div className="mt-4 text-sm font-medium text-ink">{item.title}</div>
                <div className="mt-1 text-sm text-ink-muted">{item.text}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="flex items-center">
          <div className="w-full rounded-[24px] border border-line-subtle bg-surface-elevated p-6 shadow-[0_24px_80px_-44px_rgba(0,0,0,0.62)]">
            <div className="mb-6 space-y-2">
              <div className="text-[11px] uppercase tracking-[0.18em] text-ink-muted">Вход</div>
              <h2 className="text-2xl font-semibold text-ink">Рабочая сессия MAGAMAX</h2>
              <p className="text-sm leading-relaxed text-ink-muted">
                Используй внутреннюю учётную запись, чтобы продолжить работу в защищённом контуре.
              </p>
            </div>
            <LoginFormPanel
              onSuccess={() => navigate(from, { replace: true })}
              submitLabel="Открыть рабочее пространство"
            />
          </div>
        </section>
      </div>
    </div>
  );
}
