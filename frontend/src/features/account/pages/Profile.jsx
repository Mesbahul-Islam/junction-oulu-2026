import { AtSign, ChevronRight, Languages, LogOut, Sparkles, Trophy, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { updateMe } from "../api";
import { useAuth } from "@/features/auth/AuthProvider";
import { useFantasyMode } from "@/features/fantasy/lib/fantasyMode";
import { preloadFantasy } from "@/features/fantasy/lib/fantasyPreload";
import { languageName, SITUATIONS, topicLabel } from "@/lib/i18n";

export default function Profile() {
  const { me, logout, refresh } = useAuth();
  const [editing, setEditing] = useState(false);
  const [username, setUsername] = useState(me.username || "");
  const [error, setError] = useState("");

  const saveUsername = async () => {
    setError("");
    try {
      await updateMe({ username: username.trim() });
      await refresh();
      setEditing(false);
    } catch (err) {
      setError(err.data?.username?.[0] || err.message);
    }
  };
  const navigate = useNavigate();
  const [fantasyMode, setFantasyMode] = useFantasyMode();
  // Fantasy mode on: fetch the game's data and warm player photos now, before the reader taps in.
  useEffect(() => { if (fantasyMode) preloadFantasy(); }, [fantasyMode]);
  const initials = (me.display_name || me.username || me.email).slice(0, 2).toUpperCase();
  const situation = SITUATIONS.find((s) => s.value === me.reader_situation)?.label;

  return (
    <main className="screen">
      <div className="profile-head">
        <span className="avatar">{initials}</span>
        <div>
          <div style={{ fontWeight: 600, fontSize: 18 }}>{me.display_name || `@${me.username}`}</div>
          <div style={{ opacity: 0.8, fontSize: 14 }}>@{me.username} · {me.email}</div>
        </div>
      </div>

      <section className="panel">
        <div className="row-link" style={editing ? { display: "block" } : undefined}>
          <span><AtSign size={16} style={{ verticalAlign: -3 }} /> Username</span>
          {editing ? (
            <div className="field" style={{ margin: "8px 0 0" }}>
              <input value={username} maxLength={30} onChange={(e) => setUsername(e.target.value.replace(/\s/g, ""))} />
              {error && <div className="error" style={{ marginTop: 6 }}>{error}</div>}
              <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                <button className="btn-link" onClick={saveUsername}>Save</button>
                <button className="btn-link" style={{ color: "var(--muted)" }} onClick={() => { setEditing(false); setUsername(me.username); setError(""); }}>Cancel</button>
              </div>
            </div>
          ) : (
            <button className="btn-link" onClick={() => setEditing(true)}>@{me.username} · Change</button>
          )}
        </div>
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
        <label className="row-link" style={{ cursor: "pointer" }}>
          <span><Trophy size={16} style={{ verticalAlign: -3 }} /> Fantasy mode</span>
          <input type="checkbox" role="switch" className="switch" checked={fantasyMode} onChange={(e) => setFantasyMode(e.target.checked)} />
        </label>
        {fantasyMode && (
          <Link to="/fantasy" className="row-link" style={{ color: "inherit" }}>
            <span><Trophy size={16} style={{ verticalAlign: -3 }} /> Lämäri fantasy</span>
            <ChevronRight size={18} />
          </Link>
        )}
        <Link to="/onboarding" className="btn-primary" style={{ marginTop: 10 }}>Edit preferences</Link>
      </section>

      <button className="btn-ghost" onClick={() => { logout(); navigate("/welcome"); }}>
        <LogOut size={16} style={{ verticalAlign: -3 }} /> Log out
      </button>
    </main>
  );
}
