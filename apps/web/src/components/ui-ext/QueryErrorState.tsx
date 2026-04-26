import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui-ext/EmptyState";
import { getErrorMessage, getErrorRequestId } from "@/lib/errors";

interface QueryErrorStateProps {
  error: unknown;
  title?: string;
  description?: string;
  retryLabel?: string;
  onRetry?: () => void;
  className?: string;
}

export function QueryErrorState({
  error,
  title = "Не удалось загрузить данные",
  description,
  retryLabel = "Повторить",
  onRetry,
  className,
}: QueryErrorStateProps) {
  const requestId = getErrorRequestId(error);
  const message = description ?? getErrorMessage(error);

  return (
    <EmptyState
      icon={AlertTriangle}
      title={title}
      description={requestId ? `${message} · request id: ${requestId}` : message}
      className={className}
      action={
        onRetry ? (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="border-line-subtle bg-surface-panel"
          >
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            {retryLabel}
          </Button>
        ) : undefined
      }
    />
  );
}
