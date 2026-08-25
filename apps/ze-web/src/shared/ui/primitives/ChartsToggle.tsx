import { BarChart2 } from "lucide-react";
import { cn } from "@/shared/lib/cn";

interface ChartsToggleProps {
  pressed: boolean;
  onPressedChange: (pressed: boolean) => void;
  className?: string;
}

export function ChartsToggle({ pressed, onPressedChange, className }: ChartsToggleProps) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={() => onPressedChange(!pressed)}
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors border",
        pressed
          ? "bg-plum-voltage/20 border-plum-voltage/50 text-plum-voltage"
          : "bg-transparent border-foreground/10 text-smoke hover:border-foreground/20 hover:text-foreground",
        className,
      )}
    >
      <BarChart2 className="size-3.5" />
      Charts
    </button>
  );
}
