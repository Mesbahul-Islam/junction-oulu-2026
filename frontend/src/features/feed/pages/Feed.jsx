import { BarChart3, Bookmark, Hash, MessageCircle, MoreHorizontal, Search, Sparkles, TrendingUp } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Avatar, Button } from "@/components/ui";
import { QueryBoundary, Wordmark } from "@/components/patterns";
import { Spinner } from "@/shared/components/Spinner";
import { useAuth } from "@/features/auth/AuthProvider";
import { languageName, timeAgo } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { getFeed } from "../api";
import { TimelineItem } from "../components/TimelineItem";

const TABS = [
  { id: "foryou", label: "For you" },
  { id: "trending", label: "Trending" },
  { id: "news", label: "News" },
];

const cache = { foryou: null, trending: null, news: null, scroll: 0 };

const TRENDING = [
  { tag: "#OuluWinter", posts: "1.2K stories" },
  { tag: "#HousingFinland", posts: "842 stories" },
  { tag: "#UkrainianInFinland", posts: "634 stories" },
  { tag: "#PublicTransport", posts: "421 stories" },
];

export default function Feed() {
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = ["trending", "news"].includes(params.get("tab")) ? params.get("tab") : "foryou";
  const [items, setItems] = useState(cache[tab]);
  const [error, setError] = useState("");
  const listRef = useRef(null);

  useEffect(() => {
    setError("");
    if (cache[tab]) {
      setItems(cache[tab]);
      return;
    }
    setItems(null);
    getFeed({ limit: 40 })
      .then((d) => {
        const results = d.results || d || [];
        cache[tab] = results;
        setItems(results);
      })
      .catch((e) => setError(e.message));
  }, [tab]);

  useLayoutEffect(() => {
    if (tab === "foryou" && items && listRef.current && cache.scroll) {
      listRef.current.scrollTo({ top: cache.scroll, behavior: "instant" });
    }
  }, [tab, items]);

  return (
    <div className="min-h-dvh bg-paper">
      <div className="mx-auto grid w-full max-w-[1260px] grid-cols-1 lg:grid-cols-[280px_minmax(0,600px)_340px]">
        <aside className="sticky top-0 hidden h-dvh flex-col px-6 py-3 lg:flex">
          <div className="flex h-16 items-center">
            <Wordmark />
          </div>
          <nav className="mt-2 flex flex-col gap-1">
            {[{ label: "Home", active: true, icon: Sparkles }, { label: "Explore", to: "/explore", icon: Search }, { label: "Communities", to: "/communities", icon: Hash }, { label: "Decide", to: "/vote", icon: BarChart3 }, { label: "Bookmarks", to: "/saved", icon: Bookmark }, { label: "Profile", to: "/profile", icon: Avatar }].map((item) => {
              const Icon = item.icon === Avatar ? null : item.icon;
              if (item.to) {
                return (
                  <Link
                    key={item.label}
                    to={item.to}
                    className="focus-ring flex items-center gap-4 rounded-full px-4 py-3 text-title transition-colors hover:bg-ink/5"
                  >
                    {Icon ? <Icon size={24} /> : <Avatar name={me?.username || me?.email} size="sm" />}
                    <span>{item.label}</span>
                  </Link>
                );
              }
              return (
                <button key={item.label} className="flex items-center gap-4 rounded-full px-4 py-3 text-title transition-colors hover:bg-ink/5">
                  <Icon size={24} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
          <Button size="lg" className="mt-4 rounded-full">Post a tip</Button>
          <Link to="/profile" className="focus-ring mt-auto mb-4 flex items-center gap-3 rounded-full p-3 hover:bg-ink/5">
            <Avatar name={me?.username || me?.email} size="md" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-ui font-medium">@{me?.username || "reader"}</p>
              <p className="truncate text-meta text-muted">{languageName(me?.preferred_language)}</p>
            </div>
            <MoreHorizontal size={18} className="text-muted" />
          </Link>
        </aside>

        <main className="min-w-0 border-x border-line">
          <header className="sticky top-0 z-20 border-b border-line bg-paper/80 backdrop-blur-xl">
            <div className="flex h-14 items-center justify-between px-4 sm:h-[53px] sm:px-6 lg:px-4">
              <h1 className="text-title">Home</h1>
              <button type="button" className="focus-ring rounded-full p-2 text-muted hover:bg-ink/5 hover:text-ink">
                <Sparkles size={20} />
              </button>
            </div>
            <nav className="flex" role="tablist">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={tab === t.id}
                  onClick={() => setParams(t.id === "foryou" ? {} : { tab: t.id }, { replace: true })}
                  className="group relative flex flex-1 items-center justify-center px-4 py-3"
                >
                  <span className={cn("text-ui", tab === t.id ? "font-medium text-ink" : "text-muted group-hover:text-ink")}>
                    {t.label}
                  </span>
                  {tab === t.id && <span className="absolute bottom-0 h-[4px] w-14 rounded-full bg-newsroom" />}
                </button>
              ))}
            </nav>
          </header>

          <div className="hidden border-b border-line px-4 py-3 lg:flex lg:items-start lg:gap-3 lg:px-4">
            <Avatar name={me?.username || me?.email} size="md" />
            <div className="flex-1">
              <textarea
                rows={1}
                placeholder="Send a tip to the newsroom..."
                className="w-full resize-none bg-transparent py-2 text-title placeholder:text-muted focus:outline-none"
              />
              <div className="flex items-center justify-between border-t border-line pt-2">
                <div className="flex items-center gap-1 text-newsroom">
                  <button type="button" className="focus-ring rounded-full p-1.5 hover:bg-newsroom/5"><MessageCircle size={18} /></button>
                </div>
                <Button size="sm" className="rounded-full px-4">Post</Button>
              </div>
            </div>
          </div>

          <div
            ref={listRef}
            onScroll={(e) => {
              if (tab === "foryou") cache.scroll = e.currentTarget.scrollTop;
            }}
          >
            <QueryBoundary
              isLoading={!error && items === null}
              error={error}
              isEmpty={Array.isArray(items) && items.length === 0}
              empty={<div className="px-4 py-12 text-center text-ui text-muted">No stories yet.</div>}
              loading={<div className="grid place-items-center py-16"><Spinner /></div>}
            >
              {Array.isArray(items) && items.map((card) => <TimelineItem key={card.id} card={card} lang={me?.preferred_language} />)}
            </QueryBoundary>
          </div>
        </main>

        <aside className="sticky top-0 hidden h-dvh flex-col gap-4 px-6 py-3 xl:flex">
          <div className="mt-1 flex items-center gap-2 rounded-full border border-line bg-sunk/40 px-4 py-2.5">
            <Search size={18} className="text-muted" />
            <input type="search" placeholder="Search Oulu News" className="w-full bg-transparent text-ui placeholder:text-muted focus:outline-none" />
          </div>
          <div className="overflow-hidden rounded-card border border-line">
            <div className="flex items-center justify-between px-4 py-3">
              <h2 className="text-title">What's happening</h2>
              <TrendingUp size={18} className="text-muted" />
            </div>
            <div className="divide-y divide-line">
              {TRENDING.map((t) => (
                <button key={t.tag} className="flex w-full flex-col items-start gap-0.5 px-4 py-2.5 text-left hover:bg-ink/[0.01]">
                  <span className="text-caption text-muted">Trending in Oulu</span>
                  <span className="text-ui font-medium">{t.tag}</span>
                  <span className="text-caption text-muted">{t.posts}</span>
                </button>
              ))}
            </div>
            <button className="w-full px-4 py-2.5 text-left text-meta text-newsroom hover:bg-ink/[0.01]">Show more</button>
          </div>
          <div className="overflow-hidden rounded-card border border-line">
            <div className="px-4 py-3">
              <h2 className="text-title">Who to follow</h2>
            </div>
            <div className="divide-y divide-line">
              {["Oulu City News", "Kela Finland", "Newcomers Oulu"].map((name) => (
                <div key={name} className="flex items-center gap-3 px-4 py-2.5">
                  <Avatar name={name} size="md" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-ui font-medium">{name}</p>
                    <p className="truncate text-meta text-muted">@{name.toLowerCase().replace(/\s+/g, "_")}</p>
                  </div>
                  <Button size="sm" variant="secondary" className="rounded-full">Follow</Button>
                </div>
              ))}
            </div>
            <button className="w-full px-4 py-2.5 text-left text-meta text-newsroom hover:bg-ink/[0.01]">Show more</button>
          </div>
          <p className="px-2 text-caption text-muted">Terms · Privacy · About · © 2026 Oulu News</p>
        </aside>
      </div>
    </div>
  );
}
