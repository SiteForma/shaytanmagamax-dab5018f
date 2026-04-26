import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { useLoginMutation } from "@/hooks/queries/use-auth";
import { cn } from "@/lib/utils";

const DEFAULT_EMAIL = "admin@magamax.local";
const DEFAULT_PASSWORD = "magamax-admin";

const loginSchema = z.object({
  email: z.string().email("Укажи корректный email"),
  password: z.string().min(1, "Укажи пароль"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

interface LoginFormPanelProps {
  className?: string;
  onCancel?: () => void;
  onSuccess?: () => void;
  submitLabel?: string;
  hideDevHint?: boolean;
}

export function LoginFormPanel({
  className,
  onCancel,
  onSuccess,
  submitLabel = "Войти",
  hideDevHint = false,
}: LoginFormPanelProps) {
  const mutation = useLoginMutation();
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: DEFAULT_EMAIL,
      password: DEFAULT_PASSWORD,
    },
  });

  useEffect(() => {
    mutation.reset();
  }, [mutation]);

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await mutation.mutateAsync(values);
      toast.success("Сессия обновлена");
      onSuccess?.();
    } catch {
      toast.error("Не удалось выполнить вход");
    }
  });

  return (
    <form onSubmit={onSubmit} className={cn("space-y-4", className)}>
      <div className="space-y-1.5">
        <label className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">
          Email
        </label>
        <Input
          type="email"
          autoComplete="username"
          placeholder={DEFAULT_EMAIL}
          {...form.register("email")}
        />
        {form.formState.errors.email ? (
          <p className="text-xs text-danger">{form.formState.errors.email.message}</p>
        ) : null}
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">
          Пароль
        </label>
        <Input
          type="password"
          autoComplete="current-password"
          placeholder="••••••••"
          {...form.register("password")}
        />
        {form.formState.errors.password ? (
          <p className="text-xs text-danger">{form.formState.errors.password.message}</p>
        ) : null}
      </div>

      {mutation.error ? (
        <QueryErrorState
          error={mutation.error}
          title="Вход не выполнен"
          retryLabel="Повторить"
          onRetry={onSubmit}
          className="p-5"
        />
      ) : null}

      {!hideDevHint ? (
        <div className="rounded-lg border border-line-subtle bg-surface-muted/50 p-3 text-xs text-ink-secondary">
          В локальной среде dev-учётка уже создана: <span className="text-num">{DEFAULT_EMAIL}</span> /
          <span className="text-num"> {DEFAULT_PASSWORD}</span>.
        </div>
      ) : null}

      <div className="flex justify-end gap-2">
        {onCancel ? (
          <Button
            type="button"
            variant="outline"
            className="border-line-subtle bg-surface-panel"
            onClick={onCancel}
          >
            Отмена
          </Button>
        ) : null}
        <Button
          type="submit"
          disabled={mutation.isPending}
          className="bg-brand text-brand-foreground hover:bg-brand-hover"
        >
          {mutation.isPending ? "Вход…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}
