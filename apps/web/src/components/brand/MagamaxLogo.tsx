import magamaxMark from "@/assets/magamax-mark.png";
import magamaxWordmarkOrange from "@/assets/magamax-wordmark-orange.png";
import magamaxWordmarkWhite from "@/assets/magamax-wordmark-white.png";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
  showWordmark?: boolean;
  compact?: boolean;
}

export function MagamaxLogo({ className, showWordmark = true, compact = false }: LogoProps) {
  const { theme } = useTheme();
  const wordmarkAsset = theme === "dark" ? magamaxWordmarkWhite : magamaxWordmarkOrange;

  return (
    <div className={cn("inline-flex items-center gap-2 select-none", className)}>
      <img
        src={magamaxMark}
        alt="MAGAMAX"
        className={cn("block w-auto shrink-0", compact ? "h-6" : "h-7")}
        draggable={false}
      />
      {showWordmark && !compact ? (
        <img
          src={wordmarkAsset}
          alt=""
          aria-hidden="true"
          className={cn("block w-auto shrink-0", compact ? "h-6" : "h-7")}
          draggable={false}
        />
      ) : null}
    </div>
  );
}
