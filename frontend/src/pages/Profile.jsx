import { ChevronRight, Languages, LogOut, Sparkles, Users } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth";
import { languageName, SITUATIONS, topicLabel } from "../lib/i18n";

export default function Profile() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const initials = (me.display_name || me.email).slice(0, 2).toUpperCase();
  const situation = SITUATIONS.find((s) => s.value === me.reader_situation)?.label;

  return (
    <main className="screen">
      <div className="profile-head">
        <span className="avatar">{initials}</span>
        <div>
          <div style={{ fontWeight: 600, fontSize: 18 }}>{me.display_name || me.email}</div>
          <div style={{ opacity: 0.8, fontSize: 14 }}>{me.email}</div>
        </div>
      </div>

      <section className="panel">
        <div className="row-link"><span><Languages size={16} style={{ verticalAlign: -3 }} /> Language</span><b>{languageName(me.preferred_language)}</b></div>
        <div className="row-link"><span><Sparkles size={16} style={{ verticalAlign: -3 }} /> Situation</span><b>{situation || "—"}</b></div>
        <div className="row-link"><span>Arrived in Finland</span><b>{me.arrival_date || "—"}</b></div>
        <div className="row-link" style={{ display: "block" }}>
          <div style={{ marginBottom: 8 }}>Topics you follow</div>
          <div className="meta-row" style={{ marginTop: 0 }}>
            {(me.profile?.interests || []).map((t) => <span key={t} className="tag-chip">{topicLabel(t)}</span>)}
          </div>
        </div>
        <Link to="/communities" className="row-link" style={{ color: "inherit" }}>
          <span><Users size={16} style={{ verticalAlign: -3 }} /> Communities</span><ChevronRight size={18} />
        </Link>
        <Link to="/onboarding" className="btn-primary" style={{ marginTop: 10 }}>Edit preferences</Link>
      </section>

      <button className="btn-ghost" onClick={() => { logout(); navigate("/welcome"); }}>
        <LogOut size={16} style={{ verticalAlign: -3 }} /> Log out
      </button>
    </main>
  );
}
