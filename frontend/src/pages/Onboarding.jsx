import { ArrowRight, Check, ChevronLeft, CircleCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import CommunityCard from "../components/CommunityCard";
import { Spinner } from "../components/Spinner";
import { getInterests, getRecommendedCommunities, joinCommunity, resolveCode, saveOnboarding } from "../lib/api";
import { useAuth } from "../lib/auth";
import { LANGUAGES, SITUATIONS, TOPICS, topicIcon } from "../lib/i18n";

const STEPS = ["language", "categories", "about", "communities"];
// Suggestions scoring at least this are pre-selected (e.g. "New in Oulu" for a newcomer).
const PRESELECT_SCORE = 3;

/**
 * Four steps: language (every story is then translated into it), categories
 * (the design's "Choose Categories" grid), situation + arrival date, and communities
 * to join, recommended from the answers so far. Also used to edit preferences later,
 * pre-filled from the profile.
 */
export default function Onboarding() {
  const { me, loading, refresh } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [step, setStep] = useState(0);
  const [interests, setInterests] = useState([]);
  const [form, setForm] = useState(null);
  const [code, setCode] = useState(params.get("code") || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [picked, setPicked] = useState([]);

  useEffect(() => {
    getInterests().then((data) => setInterests(Array.isArray(data) ? data : data.results || []));
  }, []);

  useEffect(() => {
    if (!me || form) return;
    setForm({
      preferred_language: me.preferred_language || "en",
      interests: me.profile?.interests || [],
      reader_situation: me.reader_situation || "newcomer",
      arrival_date: me.arrival_date || "",
    });
  }, [me, form]);

  // A QR code (e.g. at the service point) presets the language and arrival date.
  useEffect(() => {
    if (!code || !form) return;
    resolveCode(code)
      .then((link) => {
        const arrival = new Date(Date.now() - (link.default_arrival_offset_days || 0) * 86400000).toISOString().slice(0, 10);
        setForm((f) => ({ ...f, preferred_language: link.language || f.preferred_language, arrival_date: f.arrival_date || arrival }));
      })
      .catch(() => setCode(""));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, Boolean(form)]);

  if (loading) return <Spinner />;
  if (!me) return <Navigate to={`/welcome?code=${encodeURIComponent(code)}`} replace />;
  if (!form) return <Spinner />;

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const toggle = (slug) =>
    set({ interests: form.interests.includes(slug) ? form.interests.filter((s) => s !== slug) : [...form.interests, slug] });

  const run = async (work) => {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (err) {
      setError(Object.values(err.data || {}).flat()[0] || err.message);
    } finally {
      setBusy(false);
    }
  };

  // Save the profile first: the community suggestions are computed from it.
  const savePreferences = () => run(async () => {
    await saveOnboarding({ ...form, arrival_date: form.arrival_date || null, ...(code ? { onboarding_code: code } : {}) });
    await refresh();
    const list = await getRecommendedCommunities();
    setSuggestions(list);
    setPicked(list.filter((c) => c.score >= PRESELECT_SCORE).map((c) => c.slug));
    setStep(STEPS.indexOf("communities"));
  });

  const finish = () => run(async () => {
    for (const slug of picked) await joinCommunity(slug);
    await refresh();
    navigate("/", { replace: true });
  });

  const togglePick = (slug) => setPicked((p) => (p.includes(slug) ? p.filter((s) => s !== slug) : [...p, slug]));

  const name = STEPS[step];
  return (
    <main className="screen">
      <div className="steps">{STEPS.map((s, i) => <span key={s} className={i <= step ? "on" : ""} />)}</div>
      <div className="back-row">
        <button className="avatar" onClick={() => (step ? setStep(step - 1) : navigate(-1))} aria-label="Back">
          <ChevronLeft size={22} />
        </button>
        <h1>The News</h1>
      </div>
      {error && <div className="error">{error}</div>}

      {name === "language" && (
        <>
          <h2 className="title-serif">Your language</h2>
          <p className="lead">Every story is translated into it for you, with the Finnish original alongside.</p>
          <div className="lang-list">
            {LANGUAGES.map((l) => (
              <button key={l.code} className={`lang-option${form.preferred_language === l.code ? " selected" : ""}`}
                onClick={() => set({ preferred_language: l.code })}>
                <span>
                  <span className="native" dir="auto">{l.name}</span><br />
                  <span className="english">{l.english}</span>
                </span>
                {form.preferred_language === l.code && <Check size={20} color="var(--orange-500)" />}
              </button>
            ))}
          </div>
        </>
      )}

      {name === "categories" && (
        <>
          <h2 className="title-serif">Choose Categories</h2>
          <p className="lead">Choose your favorite topics and personalize your news feed</p>
          <div className="grid2">
            {interests.map((i) => {
              const Icon = topicIcon(i.slug);
              const on = form.interests.includes(i.slug);
              return (
                <button key={i.slug} className={`choice-card${on ? " selected" : ""}`} onClick={() => toggle(i.slug)} aria-pressed={on}>
                  <span className="badge"><CircleCheck size={14} /> {on ? "Following" : "Follow"}</span>
                  <span className="icon-circle"><Icon size={22} strokeWidth={1.7} /></span>
                  <div className="name">{i.name}</div>
                  <div className="sub">{TOPICS[i.slug]?.blurb || "Local news"}</div>
                </button>
              );
            })}
          </div>
        </>
      )}

      {name === "about" && (
        <>
          <h2 className="title-serif">About you</h2>
          <p className="lead">We add a short "what this means for you" to every story.</p>
          <div className="lang-list">
            {SITUATIONS.map((s) => (
              <button key={s.value} className={`lang-option${form.reader_situation === s.value ? " selected" : ""}`}
                onClick={() => set({ reader_situation: s.value })}>
                <span className="native" style={{ fontSize: 15 }}>{s.label}</span>
                {form.reader_situation === s.value && <Check size={20} color="var(--orange-500)" />}
              </button>
            ))}
          </div>
          <div className="panel" style={{ marginTop: 14 }}>
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="arrival">When did you arrive in Finland? (optional)</label>
              <input id="arrival" type="date" value={form.arrival_date || ""} onChange={(e) => set({ arrival_date: e.target.value })} />
            </div>
          </div>
        </>
      )}

      {name === "communities" && (
        <>
          <h2 className="title-serif">Communities for you</h2>
          <p className="lead">
            Neighbours post, ask and help each other here. Posts reach you in your language. We picked these from your answers.
          </p>
          {suggestions.length === 0 ? (
            <p className="lead">You're already in every community that fits you. You can find more later in Profile → Communities.</p>
          ) : (
            <div className="community-list">
              {suggestions.map((c) => (
                <CommunityCard key={c.slug} community={c} joined={picked.includes(c.slug)} onToggle={() => togglePick(c.slug)}
                  actionLabel={picked.includes(c.slug) ? <><Check size={16} /> Added</> : "Add"} />
              ))}
            </div>
          )}
        </>
      )}

      {name === "about" ? (
        <button className="btn-primary" disabled={busy} onClick={savePreferences}>Continue <ArrowRight size={18} /></button>
      ) : name === "communities" ? (
        <button className="btn-primary" disabled={busy} onClick={finish}>
          {picked.length ? `Join ${picked.length} and start reading` : "Start reading"} <ArrowRight size={18} />
        </button>
      ) : (
        <button className="btn-primary" disabled={name === "categories" && !form.interests.length} onClick={() => setStep(step + 1)}>
          Continue <ArrowRight size={18} />
        </button>
      )}
    </main>
  );
}
