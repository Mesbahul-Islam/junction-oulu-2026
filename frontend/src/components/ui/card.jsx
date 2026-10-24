import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Structure comes from hairlines; only floating things get a shadow.
const cardVariants = cva("rounded-card", {
  variants: {
    variant: {
      flat: "border border-line bg-surface",
      sunk: "bg-sunk",
      float: "bg-surface shadow-float",
      ghost: "",
    },
  },
  defaultVariants: { variant: "flat" },
});

export function Card({ className, variant, ...props }) {
  return <div className={cn(cardVariants({ variant }), className)} {...props} />;
}
