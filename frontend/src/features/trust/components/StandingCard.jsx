import { BadgeCheck } from "lucide-react";

import { useMyTrust } from "../hooks";

const LEVEL = {
  member: "Member",
  contributor: "Contributor",
  eligible: "Waiting for an editor",
  trusted: "Trusted voice",
  paused: "Trusted voice, paused",
};
const SIGNAL = {
  helpful_note: "helpful notes",
  unhelpful_note: "notes rated not helpful",
  accepted_contribution: "questions and tips accepted",
  contribution_in_story: "became a story",
  story_candidate: "questions others asked too",
  like: "likes from others",
  good_rating: "ratings that matched",
  removed_post: "posts removed",
};

function Next({ t }) {
  const n = t.next || {};
  if (t.level === "eligible") return <p className="trust-next">An editor of this community will review your standing.</p>;
  if (t.level === "paused") return <p className="trust-next">Raise your score or keep posts within the rules to restore it.</p>;
  if (n.level === "contributor") return <p className="trust-next">{n.points} more points to Contributor.</p>;
  if (n.level === "eligible") {
    const parts = [n.points > 0 && `${n.points} more points`, n.verified > 0 && `${n.verified} more helpful note or accepted question`].filter(Boolean);
    return parts.length ? <p className="trust-next">To become a trusted voice: {parts.join(" and ")}.</p> : null;
  }
  return null;
}

/** Profile: your standing in each community, what earned it, and the next step. */
export default function StandingCard() {
  const { data } = useMyTrust();
  if (!data?.length) return null;
  return (
    <section className="panel trust-card">
      <div className="trust-title">Your community standing</div>
      {data.map((t) => (
        <div key={t.id} className="trust-row">
          <div className="trust-head">
            <b>{t.community_name}</b>
            <span className={`trust-level ${t.level}`}>{t.level === "trusted" && <BadgeCheck size={13} />} {LEVEL[t.level]}</span>
          </div>
          <div className="trust-score">{t.score} points</div>
          {Object.keys(t.breakdown).length > 0 && (
            <div className="trust-why">
              {Object.entries(t.breakdown).map(([k, v]) => <span key={k}>{v.count} {SIGNAL[k] || k}</span>)}
            </div>
          )}
          <Next t={t} />
        </div>
      ))}
      <p className="trust-how">Points come from what others verify: notes rated helpful by people in different situations, questions the editors accepted, and likes. An editor approves trusted voices.</p>
    </section>
  );
}
