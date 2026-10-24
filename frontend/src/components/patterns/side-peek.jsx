import { ExternalLink, X } from "lucide-react";
import { useEffect, useRef, useSyncExternalStore } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui";

/** Notion-style side peek: a full-height panel at the end of the screen for reading one item
 *  (a story, a thread) without leaving the list. `href` adds "Open as page". Esc closes it,
 *  unless Esc is closing a dialog opened from inside. Use from tablet up; phones get a page. */
export function SidePeek({ id, href, state, label, onClose, children }) {
  const ref = useRef(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => ref.current?.focus(), [id]);
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && !document.querySelector('[role="dialog"][data-state="open"]') && close.current();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <aside
      ref={ref}
      tabIndex={-1}
      aria-label={label}
      className="fixed inset-y-0 end-0 z-[45] flex w-full max-w-[540px] flex-col border-s border-line bg-surface shadow-float outline-none animate-in slide-in-from-right-8 fade-in-0 duration-200 ease-kajo rtl:slide-in-from-left-8"
    >
      <div className="flex h-14 shrink-0 items-center gap-1 border-b border-line px-3">
        <Button variant="ghost" size="icon" onClick={onClose} aria-label={`Close ${label.toLowerCase()}`}><X size={18} /></Button>
        {href && (
          <Button asChild variant="ghost" size="sm" className="ms-auto text-muted">
            <Link to={href} state={state}><ExternalLink size={14} />Open as page</Link>
          </Button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto px-6 py-6">{children}</div>
    </aside>
  );
}

// From tablet up a list opens items in the side peek; on phones they open as a page.
const PEEK = "(min-width: 768px)";
const subscribe = (cb) => {
  const m = window.matchMedia(PEEK);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
};
export const useCanPeek = () => useSyncExternalStore(subscribe, () => window.matchMedia(PEEK).matches);
