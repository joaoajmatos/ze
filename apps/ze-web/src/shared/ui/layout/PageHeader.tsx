interface PageHeaderProps {
  label: string;
  title: string;
}

export function PageHeader({ label, title }: PageHeaderProps) {
  return (
    <div>
      <p className="text-xs font-semibold tracking-widest uppercase text-smoke mb-1">
        {label}
      </p>
      <p className="font-display text-2xl font-medium text-foreground">{title}</p>
    </div>
  );
}
