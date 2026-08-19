import type { ReactNode } from "react";

interface DashboardHeroProps {
  value: ReactNode;
  caption: ReactNode;
}

export function DashboardHero({ value, caption }: DashboardHeroProps) {
  return (
    <div>
      <p className="font-display text-[64px] font-light leading-none tracking-tight text-foreground">
        {value}
      </p>
      <p className="mt-2 text-[10px] text-smoke tracking-widest uppercase">{caption}</p>
    </div>
  );
}
