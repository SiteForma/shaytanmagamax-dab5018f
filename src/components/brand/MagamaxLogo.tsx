import magamaxLogo from "@/assets/magamax-logo.png";
import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
  showWordmark?: boolean;
  compact?: boolean;
}

/**
 * Official MAGAMAX logo.
 * Asset is the real brand mark sampled from magamax.ru.
 * Do not redesign — only swap the asset file at src/assets/magamax-logo.png.
 */
export function MagamaxLogo({ className, showWordmark = true, compact = false }: LogoProps) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <img
        src={magamaxLogo}
        alt="MAGAMAX"
        className={cn(
          "h-7 w-auto select-none",
          compact && "h-6",
        )}
        draggable={false}
      />
      {showWordmark && !compact && (
        <div className="flex flex-col leading-none">
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-ink-muted">
            Internal
          </span>
          <span className="text-[13px] font-semibold tracking-tight text-ink">
            Shaytan Machine
          </span>
        </div>
      )}
    </div>
  );
}
