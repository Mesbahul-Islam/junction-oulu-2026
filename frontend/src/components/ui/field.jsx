import { cn } from "@/lib/utils";

// Label + control + hint/error, stacked. Pass htmlFor to tie the label to the control's id.
export function Field({ label, hint, error, htmlFor, children, className }) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label && (
        <label htmlFor={htmlFor} className="text-meta font-medium text-ink">
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p role="alert" className="text-meta text-danger">{error}</p>
      ) : hint ? (
        <p className="text-meta text-muted">{hint}</p>
      ) : null}
    </div>
  );
}
