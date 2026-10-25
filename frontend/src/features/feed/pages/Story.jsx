import { ChevronLeft, Newspaper } from "lucide-react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { Column, RailPanel } from "@/components/patterns";
import { Button } from "@/components/ui";
import { useAuth } from "@/features/auth/AuthProvider";
import { timeAgo } from "@/lib/i18n";
import { transitionTo } from "@/lib/transition";
import { StoryView } from "../components/StoryView";
import { useTimeline } from "../hooks/useFeed";

/** Next stories from the reader's timeline (already cached when they came from For You). */
function MoreForYou({ id, lang }) {
  const navigate = useNavigate();
  const more = (useTimeline(null).data || []).filter((s) => s.id !== Number(id)).slice(0, 5);
  if (!more.length) return null;
  return (
    <RailPanel icon={Newspaper} title="More for you">
      <ul className="flex flex-col divide-y divide-line">
        {more.map((s) => (
          <li key={s.id}>
            <Link
              to={`/story/${s.id}`}
              state={s}
              onClick={(e) => {
                if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
                e.preventDefault();
                transitionTo(() => navigate(`/story/${s.id}`, { state: s }), s.id);
              }}
              className="focus-ring group flex gap-3 rounded-control py-3"
              dir="auto"
            >
              <span className="min-w-0 flex-1">
                <span className="line-clamp-3 text-meta font-medium group-hover:underline">{s.headline}</span>
                <span className="mt-1 block text-caption text-muted">{timeAgo(s.published_at, lang)}</span>
              </span>
              {s.image_url && (
                <img src={s.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" onError={(e) => e.currentTarget.remove()} className="h-14 w-14 shrink-0 rounded-control bg-sunk object-cover" />
              )}
            </Link>
          </li>
        ))}
      </ul>
    </RailPanel>
  );
}

/** A story on its own page, opened from the feed (replacing it; Back returns) or a shared link.
 *  Same Column frame as For You, so only the content changes when it opens. */
export default function Story() {
  const { id } = useParams();
  const { me } = useAuth();
  const navigate = useNavigate();
  const { state, key } = useLocation(); // the feed card, if we came from the feed (has the ranking)
  const card = state?.id === Number(id) ? state : undefined;
  const lang = me?.preferred_language;
  // A shared link opened fresh has nothing to go back to: Back goes to For You instead.
  const back = () => transitionTo(() => (key !== "default" ? navigate(-1) : navigate("/")), Number(id));
  return (
    <Column
      rail={<MoreForYou id={id} lang={lang} />}
      header={
        <div className="flex min-h-14 items-center px-4 pt-[env(safe-area-inset-top)] sm:px-6">
          <Button variant="ghost" size="sm" className="-ms-2.5" onClick={back}>
            <ChevronLeft size={16} className="rtl:rotate-180" />Back
          </Button>
        </div>
      }
    >
      <div className="px-4 pb-16 pt-6 sm:px-6">
        <StoryView id={id} card={card} ranking={card?.ranking} lang={lang} size="page" onReported={() => navigate("/")} />
      </div>
    </Column>
  );
}
