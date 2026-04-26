import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { LoginFormPanel } from "@/components/auth/LoginFormPanel";

interface LoginDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function LoginDialog({ open, onOpenChange }: LoginDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-line-subtle bg-surface-elevated sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle className="text-ink">Вход в MAGAMAX</DialogTitle>
          <DialogDescription className="text-sm text-ink-muted">
            Внутренняя сессия для работы с резервом, качеством данных и ingestion workflows.
          </DialogDescription>
        </DialogHeader>

        <LoginFormPanel onCancel={() => onOpenChange(false)} onSuccess={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
