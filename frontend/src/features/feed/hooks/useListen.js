
import { useEffect, useMemo, useState } from "react";

// Browser speech voices by app language code.
const VOICE_LANG = { fi: "fi-FI", en: "en-GB", sv: "sv-SE", uk: "uk-UA", ru: "ru-RU", ar: "ar-SA", so: "so-SO", et: "et-EE" };

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

