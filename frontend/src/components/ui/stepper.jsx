import { cn } from "@/lib/utils";

// Thin progress segments for a multi-step flow. `current` is 0-based.
export function Stepper({ total, current, className }) {
  return (
    <div
      className={cn("flex gap-1.5", className)}
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={total}
      aria-valuenow={current + 1}
      aria-label={`Step ${current + 1} of ${total}`}
    >
      {Array.from({ length: total }).map((_, i) => (
        <span
          key={i}
          className={cn("h-1 flex-1 rounded-full transition-colors", i <= current ? "bg-accent" : "bg-line")}
        />
      ))}
    </div>
  );
}
