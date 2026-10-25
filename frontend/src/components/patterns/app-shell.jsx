import { Bookmark, ChevronLeft, CircleUser, ListPlus, MessageCircleQuestion, Newspaper, Users } from "lucide-react";
import { useLayoutEffect } from "react";
import { NavLink, Outlet, useLocation, useNavigate, useNavigationType } from "react-router-dom";

import { Avatar, Button } from "@/components/ui";
import { useAuth } from "@/features/auth/AuthProvider";
import { languageName, RTL } from "@/lib/i18n";
import { routeCommitted } from "@/lib/transition";
import { cn } from "@/lib/utils";

// The information architecture: read, take part, decide, you. The community sits in the
// nav as a peer of the news, not under a menu.
export const NAV = [
  { to: "/", label: "For You", icon: Newspaper, end: true },
  { to: "/communities", label: "Community", icon: Users },
  { to: "/vote", label: "Next stories", icon: ListPlus },
  { to: "/saved", label: "Saved", icon: Bookmark },
  { to: "/profile", label: "You", icon: CircleUser },
];

/** Kalevalo (Kaleva + valo, "light"): the Kajo mark, first light on the horizon, and the name in the display face. */
export function Wordmark({ className }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-display text-[21px] leading-none tracking-[-0.02em]", className)}>
      <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 16a7 7 0 0 1 14 0Z" fill="currentColor" />
        <path d="M2.5 19.5h19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <span>Kalevalo</span>
    </span>
  );
}

// Scroll position per history entry. We restore it ourselves (not the browser) so it is set
// before a view transition captures the new screen: Back lands exactly where the reader was.
const scrolls = new Map();
let currentKey = null;
if (typeof window !== "undefined") {
  history.scrollRestoration = "manual";
  window.addEventListener("scroll", () => scrolls.set(currentKey, window.scrollY), { passive: true });
}

function useScrollMemory() {
  const { key } = useLocation();
  const type = useNavigationType();
  // Children have committed (lists render from the query cache), so the page has its height.
  useLayoutEffect(() => {
    currentKey = key;
    window.scrollTo(0, type === "POP" ? scrolls.get(key) ?? 0 : 0);
    routeCommitted();
  }, [key, type]);
}

/** Responsive app frame: desktop left rail, mobile bottom tab bar. Use as a layout route. */
export function AppShell() {
  const { me } = useAuth();
  useScrollMemory();
  const lang = me?.preferred_language || "en";
  return (
    <div dir={RTL.has(lang) ? "rtl" : "ltr"} lang={lang} className="min-h-dvh bg-paper font-sans text-ink lg:grid lg:grid-cols-[72px_minmax(0,1fr)] xl:grid-cols-[256px_minmax(0,1fr)]">
      {/* 1024–1279px: icons only, so the page keeps room for its side column; labels from 1280px. */}
      <aside className="sticky top-0 hidden h-dvh flex-col gap-8 border-e border-line px-3 py-6 lg:flex xl:px-4">
        <Wordmark className="px-3 max-xl:[&>span]:sr-only" />
        <nav aria-label="Main" className="flex flex-col gap-0.5">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn("focus-ring flex h-11 items-center gap-3 rounded-control px-3 text-ui transition-colors",
                  isActive ? "bg-sunk font-medium text-ink" : "text-muted hover:bg-sunk/60 hover:text-ink")}
            >
              <Icon size={19} strokeWidth={1.8} className="shrink-0" /><span className="max-xl:sr-only">{label}</span>
            </NavLink>
          ))}
        </nav>
        <Button asChild variant="secondary" className="max-xl:px-0 xl:justify-start">
          <NavLink to="/create" aria-label="Ask the newsroom"><MessageCircleQuestion size={18} className="shrink-0" /><span className="max-xl:hidden">Ask the newsroom</span></NavLink>
        </Button>
        {me && (
          <NavLink to="/profile" className="focus-ring mt-auto flex items-center gap-3 rounded-control p-2 hover:bg-sunk/60">
            <Avatar name={me.username || me.email} size="md" />
            <span className="flex min-w-0 flex-col max-xl:sr-only">
              <span className="truncate text-meta font-medium">@{me.username}</span>
              <span className="truncate text-caption text-muted">Reading in {languageName(lang)}</span>
            </span>
          </NavLink>
        )}
      </aside>

      <main className="min-w-0 pb-[calc(4.25rem+env(safe-area-inset-bottom))] lg:pb-0">
        <Outlet />
      </main>

      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-line bg-surface/90 pb-safe backdrop-blur-md lg:hidden">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn("focus-ring flex h-[4.25rem] flex-col items-center justify-center gap-1 text-caption transition-colors",
                isActive ? "font-medium text-ink" : "text-muted")}
          >
            {({ isActive }) => (
              <>
                <Icon size={22} strokeWidth={isActive ? 2.1 : 1.7} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

// Desktop frame shared by Column and Page: a 680px content column plus a side column, centred
// together. Pages without side content keep the space empty, so every page's content sits at
// the same x as For You's and nothing jumps between tabs.
const FRAME = "lg:flex lg:justify-center lg:gap-6 lg:px-6 xl:gap-8 xl:px-8 2xl:gap-10 2xl:px-10";
const RAIL_W = "w-[300px] shrink-0 xl:w-[320px] 2xl:w-[340px]";
const railSpacer = <div aria-hidden="true" className={cn("hidden lg:block", RAIL_W)} />;

/** Page container: a reading column, in the same place as a Column's. `wide` for grids (design page). */
export function Page({ wide, className, children }) {
  if (wide) return <div className={cn("mx-auto w-full max-w-5xl px-4 sm:px-6", className)}>{children}</div>;
  return (
    <div className={FRAME}>
      <div className={cn("mx-auto w-full max-w-read px-4 sm:px-6 lg:mx-0 lg:max-w-[680px]", className)}>{children}</div>
      {railSpacer}
    </div>
  );
}

/** Page title block. `back` shows a back button; `actions` sit at the end of the top row. */
export function PageHeader({ title, subtitle, back, actions, className }) {
  const navigate = useNavigate();
  return (
    <header className={cn("flex flex-col gap-4 pb-2 pt-[max(1rem,env(safe-area-inset-top))] lg:pt-10", className)}>
      {(back || actions) && (
        <div className="flex min-h-11 items-center gap-2">
          {back && (
            <Button variant="ghost" size="icon" className="-ms-3" aria-label="Back" onClick={() => (typeof back === "function" ? back() : navigate(-1))}>
              <ChevronLeft size={22} className="rtl:rotate-180" />
            </Button>
          )}
          <div className="ms-auto flex items-center gap-1">{actions}</div>
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <h1 className="text-display text-balance">{title}</h1>
        {subtitle && <p className="max-w-[60ch] text-ui text-muted">{subtitle}</p>}
      </div>
    </header>
  );
}

/** Timeline page (For You, Next stories): one surface column, max 680px, centred in the main
 *  area on desktop and full-bleed on phones, with a sticky header. `rail` is a side column beside
 *  it from 1024px (context that would otherwise interrupt the timeline); below that it's not shown,
 *  so pages keep a phone fallback for whatever they put there. */
export function Column({ header, rail, children }) {
  return (
    <div className={cn("min-h-dvh", FRAME)}>
      <div className="min-h-dvh w-full min-w-0 max-w-[680px] bg-surface md:border-x md:border-line">
        <header className="sticky top-0 z-20 border-b border-line bg-surface/90 backdrop-blur-md">{header}</header>
        {children}
      </div>
      {rail ? (
        <aside className={cn("sticky top-0 hidden h-dvh flex-col gap-4 overflow-y-auto py-8 [scrollbar-width:thin] lg:flex", RAIL_W)}>
          {rail}
        </aside>
      ) : railSpacer}
    </div>
  );
}

/** A titled panel in a Column rail. */
export function RailPanel({ icon: Icon, title, action, children, className }) {
  return (
    <section className={cn("rounded-card border border-line bg-surface", className)}>
      <header className="flex items-center gap-2 px-4 pt-4 text-caption font-semibold uppercase tracking-wide text-muted">
        {Icon && <Icon size={13} />}
        <h2 className="flex-1">{title}</h2>
        {action}
      </header>
      <div className="px-4 pb-4 pt-3">{children}</div>
    </section>
  );
}

/** Title row for a Column header. `aside` sits at the end (a status, a count). */
export function ColumnTitle({ title, subtitle, aside }) {
  return (
    <div className="flex items-end justify-between gap-4 px-4 pb-3 pt-[max(1rem,env(safe-area-inset-top))] sm:px-6 lg:pt-8">
      <div className="min-w-0">
        <h1 className="text-headline lg:text-display">{title}</h1>
        {subtitle && <p className="mt-0.5 text-meta text-muted first-letter:uppercase">{subtitle}</p>}
      </div>
      {aside && <div className="flex shrink-0 items-center gap-3 pb-0.5 text-meta text-muted">{aside}</div>}
    </div>
  );
}

/** A filter in a Column header (topics, communities). Selected is ink: the reader's own choice. */
export function FilterChip({ active, onClick, icon: Icon, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "focus-ring inline-flex h-8 shrink-0 items-center gap-1.5 rounded-pill border px-3 text-meta transition-colors [@media(pointer:coarse)]:h-10",
        active ? "border-ink bg-ink text-on-ink" : "border-line text-muted hover:border-ink/25 hover:text-ink",
      )}
    >
      {Icon && <Icon size={14} />}{children}
    </button>
  );
}

/** Horizontal, scrollable row of FilterChips under a ColumnTitle. */
export function FilterBar({ label, children }) {
  return (
    <nav aria-label={label} className="-mb-px flex gap-2 overflow-x-auto px-4 pb-3 [scrollbar-width:none] sm:px-6">{children}</nav>
  );
}
