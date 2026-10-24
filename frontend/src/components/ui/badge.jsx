import { cn } from "@/lib/utils";

// Tone = provenance (see globals.css). Appearance = emphasis: solid for the one signal that
// must lead (e.g. "In your language"), soft for status, outline for neutral facts.
const TONES = {
  neutral: { solid: "bg-ink text-on-ink", soft: "bg-sunk text-muted", outline: "border-line text-muted" },
  newsroom: { solid: "bg-newsroom text-on-ink", soft: "bg-newsroom-weak text-newsroom", outline: "border-newsroom/40 text-newsroom" },
  community: { solid: "bg-community text-on-ink", soft: "bg-community-weak text-community", outline: "border-community/40 text-community" },
  confirmed: { solid: "bg-confirmed text-on-ink", soft: "bg-confirmed-weak text-confirmed", outline: "border-confirmed/40 text-confirmed" },
  danger: { solid: "bg-danger text-on-ink", soft: "bg-danger-weak text-danger", outline: "border-danger/40 text-danger" },
};

export function Badge({ tone = "neutral", appearance = "soft", className, ...props }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1 whitespace-nowrap rounded-pill border border-transparent px-2.5 py-[3px] text-caption font-medium [&_svg]:shrink-0",
        TONES[tone][appearance],
        className,
      )}
      {...props}
    />
  );
}
