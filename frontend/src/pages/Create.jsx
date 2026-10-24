import { ChevronLeft, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createPost, getMyCommunities, sendContribution } from "../lib/api";

const MODES = [
  { id: "post", label: "Community post", hint: "Shown in Community News to members of your community. Written by you, not reviewed by editors; others can report it." },
  { id: "tip", label: "Tip or question", hint: "Goes privately to the newsroom. Editors may turn it into a story; it is never published as you wrote it." },
];
const TIP_KINDS = [
  { value: "question", label: "A question" },
  { value: "tip", label: "A local tip" },
  { value: "topic_suggestion", label: "A story idea" },
];

/** The "+" screen: post to your community, or send a tip / question to the newsroom (FR-3.10). */
export default function Create() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("post");
  const [communities, setCommunities] = useState([]);
  const [community, setCommunity] = useState(null);
  const [kind, setKind] = useState("question");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    getMyCommunities().then((list) => { setCommunities(list); setCommunity(list[0] || null); });
  }, []);

  const submit = async () => {
    if (!community || !body.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      if (mode === "post") {
        await createPost(community.slug, body.trim());
        navigate("/?tab=community");
      } else {
        await sendContribution(community.id, kind, body.trim());
        setBody("");
        setMessage("Thanks! The newsroom will look at it. You'll see a story if editors pick it up.");
      }
    } catch (err) {
      setMessage(Object.values(err.data || {}).flat()[0] || err.message);
    } finally {
      setBusy(false);
    }
  };

  const current = MODES.find((m) => m.id === mode);
  return (
    <main className="screen">
      <div className="back-row">
        <button className="avatar" onClick={() => navigate(-1)} aria-label="Back"><ChevronLeft size={22} /></button>
        <h1>Create</h1>
      </div>

      <div className="pills" style={{ margin: "0 0 14px", padding: 0 }}>
        {MODES.map((m) => <button key={m.id} className={`pill${mode === m.id ? " active" : ""}`} onClick={() => setMode(m.id)}>{m.label}</button>)}
      </div>
      <p className="lead" style={{ fontSize: 14 }}>{current.hint}</p>

      <section className="panel">
        {communities.length === 0 ? (
          <p style={{ margin: 0 }}>Join a community first (it's set when you onboard with a QR code).</p>
        ) : (
          <>
            {communities.length > 1 && (
              <div className="field">
                <label htmlFor="community">Community</label>
                <select id="community" value={community?.slug} onChange={(e) => setCommunity(communities.find((c) => c.slug === e.target.value))}>
                  {communities.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
                </select>
              </div>
            )}
            {mode === "tip" && (
              <div className="field">
                <label htmlFor="kind">What is it?</label>
                <select id="kind" value={kind} onChange={(e) => setKind(e.target.value)}>
                  {TIP_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
                </select>
              </div>
            )}
            <div className="field">
              <label htmlFor="body">{mode === "post" ? `Post to ${community?.name || "your community"}` : "Your message"}</label>
              <textarea id="body" rows={6} maxLength={1000} value={body} onChange={(e) => setBody(e.target.value)} dir="auto"
                placeholder={mode === "post" ? "Share something useful with your neighbours…" : "e.g. Why is the bus 3 timetable changing?"}
                style={{ border: "1px solid var(--line)", borderRadius: 14, padding: "12px 14px", font: "inherit", resize: "vertical" }} />
            </div>
            {mode === "post" && <p style={{ fontSize: 12.5, color: "var(--muted)", margin: 0 }}>Be kind and don't share other people's private details. Posts that break this are removed.</p>}
            {message && <div className="error" style={{ background: "#eaf6ef", color: "#1d5c3a", marginTop: 12 }}>{message}</div>}
            <button className="btn-primary" disabled={busy || !body.trim()} onClick={submit}>
              <Send size={18} /> {mode === "post" ? "Post" : "Send to newsroom"}
            </button>
          </>
        )}
      </section>
    </main>
  );
}
