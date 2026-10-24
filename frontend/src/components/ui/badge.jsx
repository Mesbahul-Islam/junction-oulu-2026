import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Semantic status colors are deliberately separate from the accent hue.
const badgeVariants = cva("inline-flex items-center gap-1 rounded-pill px-2.5 py-0.5 text-xs font-semibold", {
  variants: {
    variant: {
      neutral: "bg-line text-muted",
      accent: "bg-accent-weak text-accent",
      outline: "border border-line text-muted",
      success: "bg-emerald-500/12 text-emerald-700 dark:text-emerald-400",
      warn: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
      danger: "bg-danger/12 text-danger",
    },
  },
  defaultVariants: { variant: "neutral" },
});

export function Badge({ className, variant, ...props }) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
