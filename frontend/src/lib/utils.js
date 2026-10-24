import { clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// tailwind-merge must know Kajo's custom scales (tailwind.config.js), or it reads `text-ui`
// as a text colour and drops the real colour class.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["caption", "meta", "ui", "body", "lead", "title", "headline", "display", "hero"] }],
      rounded: [{ rounded: ["control", "card", "sheet", "pill"] }],
      shadow: [{ shadow: ["float", "soft"] }],
    },
  },
});

// Merge conditional class names and resolve conflicting Tailwind utilities (last wins).
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// Self-check: run `node src/lib/utils.js`.
if (typeof process !== "undefined" && process.argv?.[1]?.endsWith("utils.js")) {
  const assert = (await import("node:assert")).default;
  assert.equal(cn("bg-ink text-on-ink", "text-ui"), "bg-ink text-on-ink text-ui");
  assert.equal(cn("text-caption text-muted", "text-meta"), "text-muted text-meta");
  assert.equal(cn("rounded-control", "rounded-card"), "rounded-card");
  console.log("cn ok");
}
