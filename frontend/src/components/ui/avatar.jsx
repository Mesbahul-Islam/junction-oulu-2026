import { cn } from "@/lib/utils";

const SIZE = { sm: "h-7 w-7 text-caption", md: "h-9 w-9 text-meta", lg: "h-12 w-12 text-ui" };

/** Initials avatar. Community members get a cloudberry ring so their posts read as members' words. */
export function Avatar({ name = "", size = "md", community, className, ...props }) {
  const initials = name.replace(/^@/, "").split(/[\s._-]+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase() || "?";
  return (
    <span
      {...props}
      aria-hidden="true"
      className={cn(
        "grid shrink-0 place-items-center rounded-full bg-sunk font-semibold text-ink",
        community && "ring-2 ring-community/60 ring-offset-2 ring-offset-surface",
        SIZE[size],
        className,
      )}
    >
      {initials}
    </span>
  );
}
