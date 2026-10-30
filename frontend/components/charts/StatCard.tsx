import { cn } from "@/lib/utils";

type Tone = "default" | "danger" | "success" | "primary";

const TONES: Record<Tone, string> = {
  default: "text-foreground",
  danger: "text-danger",
  success: "text-success",
  primary: "text-observed",
};

export function StatCard({
  label,
  value,
  unit,
  hint,
  tone = "default",
  icon: Icon,
  className,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  hint?: string;
  tone?: Tone;
  icon?: React.ElementType;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-2 rounded-[20px] border bg-card p-4", tone === "danger" && "border-danger/40", className)}>
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {Icon && <Icon className={cn("size-3.5", tone === "danger" && "text-danger")} aria-hidden="true" />}
        {label}
      </span>
      <span className={cn("font-mono text-4xl font-medium leading-none tabular", TONES[tone])}>
        {value}
        {unit && <span className="ml-1 text-base text-muted-foreground">{unit}</span>}
      </span>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  );
}
