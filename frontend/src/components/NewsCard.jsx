import { Ellipsis } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../lib/auth";
import { languageName, timeAgo, topicIcon, topicLabel } from "../lib/i18n";

/** One story in the feed. Shown in the reader's language; says so when it's a fallback. */
export default function NewsCard({ card, index = 0 }) {
  const { me } = useAuth();
  const Icon = topicIcon(card.tags?.[0]);
  return (
    <Link to={`/story/${card.id}`} state={card} className="news-card" dir="auto">
      <div className={`media${index % 2 ? " alt" : ""}`}>
        {card.image_url ? <img src={card.image_url} alt="" /> : <Icon size={54} strokeWidth={1.3} />}
        <span className="chip">{timeAgo(card.published_at, me?.preferred_language)}</span>
        <span className="chip right"><Ellipsis size={16} /></span>
      </div>
      <div className="body">
        <h3>{card.headline}</h3>
        <p className="summary">{card.summary}</p>
        <div className="meta-row">
          {(card.tags || []).slice(0, 2).map((t) => <span key={t} className="tag-chip">{topicLabel(t)}</span>)}
          {!card.in_your_language && card.requested_language && (
            <span className="tag-chip warn">Not yet in {languageName(card.requested_language)}</span>
          )}
          {card.ranking?.ranker === "jev" && <span>Picked for you</span>}
        </div>
      </div>
    </Link>
  );
}
