
import { useEffect, useMemo, useRef, useState } from "react";
import { getStoryAudio } from "../api";

// Browser speech voices by app language code.
const VOICE_LANG = { fi: "fi-FI", en: "en-GB", sv: "sv-SE", uk: "uk-UA", ru: "ru-RU", ar: "ar-SA", so: "so-SO", et: "et-EE" };

/** Reads the story aloud in the language of the version shown: the newsroom's ElevenLabs clip when
 *  there is one, else the browser's speech synthesis. */
export function useListen(text, lang, id) {
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0); // 0..1
  const [clipSeconds, setClipSeconds] = useState(null);
  const clip = useRef(null); // HTMLAudioElement, or false once we know there is no clip
  const story = useRef(0); // bumped when the story changes, so a late clip isn't played
  const browser = typeof window !== "undefined" && "speechSynthesis" in window;
  const supported = Boolean(id) || browser;
  const estimate = useMemo(() => Math.max(5, text.split(/\s+/).length / 2.6), [text]); // ~155 words/min

  // A new story or language: drop the old clip and stop whatever is playing.
  useEffect(() => {
    clip.current = null;
    setPlaying(false);
    setLoading(false);
    setClipSeconds(null);
    return () => {
      story.current += 1;
      if (clip.current) { clip.current.pause(); URL.revokeObjectURL(clip.current.src); }
      if (browser) window.speechSynthesis.cancel();
    };
  }, [id, lang, browser]);

  const speak = () => {
    if (!browser) return;
    const synth = window.speechSynthesis;
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

  const toggle = async () => {
    if (loading) return;
    if (playing) {
      if (clip.current) { clip.current.pause(); clip.current.currentTime = 0; }
      if (browser) window.speechSynthesis.cancel();
      setPlaying(false);
      return;
    }
    if (clip.current === null && id) {
      const mine = story.current;
      setLoading(true);
      const blob = await getStoryAudio(id, lang).catch(() => null);
      if (mine !== story.current) return; // the reader moved on while it was being made
      setLoading(false);
      if (blob) {
        const audio = new Audio(URL.createObjectURL(blob));
        audio.onloadedmetadata = () => setClipSeconds(audio.duration);
        audio.ontimeupdate = () => setProgress(audio.currentTime / (audio.duration || 1));
        audio.onended = () => { setPlaying(false); setProgress(1); };
        clip.current = audio;
      } else {
        clip.current = false;
      }
    }
    if (clip.current) {
      clip.current.play();
      setPlaying(true);
    } else {
      speak();
    }
  };
  return { playing, loading, progress, duration: clipSeconds ?? estimate, toggle, supported };
}
