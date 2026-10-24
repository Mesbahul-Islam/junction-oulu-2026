import { MessageCircle, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { askLamari } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useT } from "../../lib/lamariText";

const KEY = "lamari:chat";
const COOLDOWN_MS = 2000; // the server also limits questions per minute and per day

/** Your Lämäri coach: helps you win, using Liiga data only. Anything else gets a polite no. */
export default function Chat({ startOpen = false }) {
  const { me } = useAuth();
  const t = useT();
  const STARTERS = t("starters");
  const [readyAt, setReadyAt] = useState(0);
  const [open, setOpen] = useState(startOpen);
  const [messages, setMessages] = useState(() => { try { return JSON.parse(sessionStorage.getItem(KEY)) || []; } catch { return []; } });
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);

  useEffect(() => {
    try { sessionStorage.setItem(KEY, JSON.stringify(messages.slice(-30))); } catch { /* ignore */ }
    end.current?.scrollIntoView({ block: "end" });
  }, [messages, open]);

  const send = async (q) => {
    const message = q.trim();
    if (!message || busy || Date.now() < readyAt) return;
    setReadyAt(Date.now() + COOLDOWN_MS);
    setText("");
    setMessages((m) => [...m, { from: "me", text: message }]);
    setBusy(true);
    try {
      const r = await askLamari(message);
      setMessages((m) => [...m, { from: "bot", text: r.answer, ai: r.source === "ai", suggestions: r.suggestions }]);
    } catch (e) {
      setMessages((m) => [...m, { from: "bot", text: e.message }]);
    }
    setBusy(false);
  };

  if (!open) {
    return <button type="button" className="fx-chat-fab" onClick={() => setOpen(true)} aria-label={t("askCoach")}><MessageCircle size={22} /></button>;
  }
  const last = messages[messages.length - 1];
  const chips = !messages.length ? STARTERS : last?.suggestions?.length ? last.suggestions : [];
  const waiting = busy || Date.now() < readyAt;

  return (
    <div className="fx-chat" role="dialog" aria-label={t("coachTitle")}>
      <div className="fx-chat-head">
        <MessageCircle size={18} /><b>{t("coachTitle")}</b>
        <button type="button" onClick={() => setOpen(false)} aria-label={t("close")}><X size={20} /></button>
      </div>
      <div className="fx-chat-log">
        <div className="fx-msg bot"><p>{t("greeting", { user: me.username })}</p></div>
        {messages.map((m, i) => (
          <div key={i} className={`fx-msg ${m.from}`}>
            <p>{m.text}</p>
            {m.ai && <small>{t("aiWording")}</small>}
          </div>
        ))}
        {busy && <div className="fx-msg bot typing"><p><span /><span /><span /></p></div>}
        <div ref={end} />
      </div>
      {chips.length > 0 && (
        <div className="fx-chat-chips">{chips.map((c) => <button key={c} type="button" onClick={() => send(c)}>{c}</button>)}</div>
      )}
      <form className="fx-chat-input" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t("askCoach")} maxLength={300} />
        <button type="submit" disabled={!text.trim() || waiting} aria-label={t("send")}><Send size={18} /></button>
      </form>
    </div>
  );
}
