import { Check, Plus, Users } from "lucide-react";

/** A community with why it's suggested (`reasons`) and a join / joined toggle. */
export default function CommunityCard({ community, joined, busy, onToggle, actionLabel }) {
  return (
    <div className={`community-card${joined ? " joined" : ""}`}>
      <div className="community-main">
        <div className="name">{community.name}</div>
        {community.description && <div className="desc">{community.description}</div>}
        {community.reasons?.length > 0 && (
          <ul className="reasons">{community.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        )}
        <div className="members"><Users size={13} /> {community.member_count} {community.member_count === 1 ? "member" : "members"}</div>
      </div>
      <button className="community-toggle" disabled={busy} onClick={onToggle} aria-pressed={joined}>
        {actionLabel || (joined ? <><Check size={16} /> Joined</> : <><Plus size={16} /> Join</>)}
      </button>
    </div>
  );
}
