import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils";

const cardVariants = cva("rounded-lg bg-surface", {
  variants: {
    variant: {
      flat: "border border-line",
      float: "shadow-float",
      ghost: "",
    },
  },
  defaultVariants: { variant: "flat" },
});

export function Card({ className, variant, ...props }) {
  return <div className={cn(cardVariants({ variant }), className)} {...props} />;
}
