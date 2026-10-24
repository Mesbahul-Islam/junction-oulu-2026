import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils";

const chipVariants = cva(
  "inline-flex items-center gap-1 rounded-pill text-xs font-semibold px-2.5 py-1",
  {
    variants: {
      variant: {
        neutral: "bg-line text-muted",
        lang: "bg-accent text-accent-ink",
        outline: "border border-line text-muted",
        warn: "bg-danger/10 text-danger",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export function Chip({ className, variant, ...props }) {
  return <span className={cn(chipVariants({ variant }), className)} {...props} />;
}
