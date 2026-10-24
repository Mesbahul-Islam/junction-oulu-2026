import { cn } from "@/lib/utils";

/** Labelled bar for a measured value ("Affects you 78%", vote tallies). */
export function Meter({ label, value, max = 1, display, tone = "ink", className }) {
  const pct = Math.max(0, Math.min(100, Math.round((value / max) * 100)));
  return (
    <div className={cn("grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5", className)}>
      <span className="text-meta text-ink">{label}</span>
      <span className="text-meta tabular-nums text-muted">{display ?? `${pct}%`}</span>
      <span className="col-span-2 h-1.5 overflow-hidden rounded-pill bg-sunk" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
        <span className={cn("block h-full rounded-pill transition-[width] duration-500 ease-kajo", tone === "newsroom" ? "bg-newsroom" : "bg-ink")} style={{ width: `${pct}%` }} />
      </span>
    </div>
  );
}
