import { ChevronLeft, CircleUser, ListPlus, MessageCircleQuestion, Newspaper, Users } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { Avatar, Button } from "@/components/ui";
import { useAuth } from "@/features/auth/AuthProvider";
import { languageName, RTL } from "@/lib/i18n";
import { cn } from "@/lib/utils";

// The information architecture: read, take part, decide, you. The community sits in the
// nav as a peer of the news, not under a menu.
export const NAV = [
  { to: "/", label: "Today", icon: Newspaper, end: true },
  { to: "/communities", label: "Community", icon: Users },
  { to: "/vote", label: "Next stories", icon: ListPlus },
  { to: "/profile", label: "You", icon: CircleUser },
];

/** Kajo mark: first light on the horizon. */
export function Wordmark({ className }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-title font-semibold tracking-tight", className)}>
      <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 16a7 7 0 0 1 14 0Z" fill="currentColor" />
        <path d="M2.5 19.5h19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      Oulu News
    </span>
  );
}

/** Responsive app frame: desktop left rail, mobile bottom tab bar. Use as a layout route. */
export function AppShell() {
  const { me } = useAuth();
  const lang = me?.preferred_language || "en";
  return (
    <div dir={RTL.has(lang) ? "rtl" : "ltr"} lang={lang} className="min-h-dvh bg-paper font-sans text-ink lg:grid lg:grid-cols-[256px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-dvh flex-col gap-8 border-e border-line px-4 py-6 lg:flex">
        <Wordmark className="px-3" />
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
              <Icon size={19} strokeWidth={1.8} />{label}
            </NavLink>
          ))}
        </nav>
        <Button asChild variant="secondary" className="justify-start">
          <NavLink to="/create"><MessageCircleQuestion size={18} />Ask the newsroom</NavLink>
        </Button>
        {me && (
          <NavLink to="/profile" className="focus-ring mt-auto flex items-center gap-3 rounded-control p-2 hover:bg-sunk/60">
            <Avatar name={me.username || me.email} size="md" />
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-meta font-medium">@{me.username}</span>
              <span className="truncate text-caption text-muted">Reading in {languageName(lang)}</span>
            </span>
          </NavLink>
        )}
      </aside>

      <main className="min-w-0 pb-[calc(4.25rem+env(safe-area-inset-bottom))] lg:pb-0">
        <Outlet />
      </main>

      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-line bg-surface/90 pb-safe backdrop-blur-md lg:hidden">
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

/** Page container: a reading column, centred. `wide` for grids (communities, design page). */
export function Page({ wide, className, children }) {
  return <div className={cn("mx-auto w-full px-4 sm:px-6", wide ? "max-w-5xl" : "max-w-read", className)}>{children}</div>;
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

/** Timeline page (Today, Next stories): one surface column, max 680px, left-aligned in the main
 *  area on desktop and full-bleed on phones, with a sticky header. */
export function Column({ header, children }) {
  return (
    <div className="min-h-dvh lg:ps-8 xl:ps-12">
      <div className="min-h-dvh w-full max-w-[680px] bg-surface md:border-x md:border-line">
        <header className="sticky top-0 z-20 border-b border-line bg-surface/90 backdrop-blur-md">{header}</header>
        {children}
      </div>
    </div>
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
