import { ChevronLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import CommunityCard from "../components/CommunityCard";
import { Spinner } from "../components/Spinner";
import { getCommunities, getRecommendedCommunities, joinCommunity, leaveCommunity } from "../lib/api";

/** Your communities, ones suggested from your profile (with why), and the rest. */
export default function Communities() {
  const navigate = useNavigate();
  const [all, setAll] = useState(null);
  const [suggested, setSuggested] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([getCommunities(), getRecommendedCommunities()])
      .then(([groups, recs]) => { setAll(groups); setSuggested(recs); })
      .catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const toggle = async (c) => {
    setBusy(c.slug);
    try {
      await (c.is_member ? leaveCommunity(c.slug) : joinCommunity(c.slug));
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  if (!all) return <main className="screen">{error ? <div className="error">{error}</div> : <Spinner />}</main>;
  const mine = all.filter((c) => c.is_member);
  const suggestedSlugs = new Set(suggested.map((c) => c.slug));
  const others = all.filter((c) => !c.is_member && !suggestedSlugs.has(c.slug));
  const card = (c) => (
    <CommunityCard key={c.slug} community={c} joined={c.is_member} busy={busy === c.slug} onToggle={() => toggle(c)}
      actionLabel={c.is_member ? "Leave" : undefined} />
  );

  return (
    <main className="screen">
      <div className="back-row">
        <button className="avatar" onClick={() => navigate(-1)} aria-label="Back"><ChevronLeft size={22} /></button>
        <h1>Communities</h1>
      </div>
      {error && <div className="error">{error}</div>}
      <p className="lead" style={{ fontSize: 14 }}>
        Posts from your communities appear in Community News, translated into your language.
      </p>

      <div className="section-title">Your communities</div>
      {mine.length ? <div className="community-list">{mine.map(card)}</div> : <p className="lead">You haven't joined any yet.</p>}

      {suggested.length > 0 && (
        <>
          <div className="section-title">Suggested for you</div>
          <div className="community-list">{suggested.map(card)}</div>
        </>
      )}

      {others.length > 0 && (
        <>
          <div className="section-title">More communities</div>
          <div className="community-list">{others.map(card)}</div>
        </>
      )}
    </main>
  );
}
