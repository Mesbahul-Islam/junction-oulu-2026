import { Pause, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

// Browser speech voices by app language code.
const VOICE_LANG = { fi: "fi-FI", en: "en-GB", sv: "sv-SE", uk: "uk-UA", ru: "ru-RU", ar: "ar-SA", so: "so-SO", et: "et-EE" };
const BARS = 46;
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** Reads the story aloud in the reader's language with the browser's speech synthesis. */
export function useListen(text, lang) {
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0); // 0..1
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const duration = useMemo(() => Math.max(5, text.split(/\s+/).length / 2.6), [text]); // ~155 words/min

  useEffect(() => () => supported && window.speechSynthesis.cancel(), [supported]);

  const toggle = () => {
    if (!supported) return;
    const synth = window.speechSynthesis;
    if (playing) {
      synth.cancel();
      setPlaying(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = VOICE_LANG[lang] || lang;
    utterance.rate = 0.95;
    utterance.onboundary = (e) => setProgress(Math.min(1, e.charIndex / text.length));
    utterance.onend = () => { setPlaying(false); setProgress(1); };
    synth.cancel();
    synth.speak(utterance);
    setProgress(0);
    setPlaying(true);
  };
  return { playing, progress, duration, toggle, supported };
}

export function PlayButton({ listen }) {
  if (!listen.supported) return null;
  return (
    <button className="play-btn" onClick={listen.toggle} aria-label={listen.playing ? "Stop reading aloud" : "Read aloud"}>
      {listen.playing ? <Pause size={24} /> : <Play size={24} />}
    </button>
  );
}

export function Waveform({ listen }) {
  const heights = useRef(Array.from({ length: BARS }, (_, i) => 20 + Math.abs(Math.sin(i * 1.7)) * 70 + (i % 5) * 4));
  if (!listen.supported) return null;
  return (
    <div className="player">
      <div className="wave" aria-hidden>
        {heights.current.map((h, i) => (
          <i key={i} className={i / BARS < listen.progress ? "on" : ""} style={{ height: `${Math.min(100, h)}%` }} />
        ))}
      </div>
      <div className="player-row">
        <span>{fmt(listen.progress * listen.duration)}</span>
        <span>{listen.playing ? "Reading aloud…" : "Listen to this story"}</span>
        <span>{fmt(listen.duration)}</span>
      </div>
    </div>
  );
}
