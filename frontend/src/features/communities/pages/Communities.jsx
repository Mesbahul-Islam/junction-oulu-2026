import { ChevronLeft } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import CommunityCard from "../components/CommunityCard";
import { joinCommunity, leaveCommunity } from "../api";
import { useCommunities } from "../hooks/useCommunities";
import { Spinner } from "@/shared/components/Spinner";

/** Your communities, ones suggested from your profile (with why), and the rest. */
export default function Communities() {
  const navigate = useNavigate();
  const { data, isLoading, error, refetch } = useCommunities();
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");

  const toggle = async (c) => {
    setBusy(c.slug);
    setActionError("");
    try {
      await (c.is_member ? leaveCommunity(c.slug) : joinCommunity(c.slug));
      await refetch();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusy("");
    }
  };

  if (isLoading || !data) return <main className="screen">{error ? <div className="error">{error.message}</div> : <Spinner />}</main>;
  const { all, suggested } = data;
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
      {actionError && <div className="error">{actionError}</div>}
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
