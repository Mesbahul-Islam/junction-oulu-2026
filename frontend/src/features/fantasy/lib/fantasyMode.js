import { useEffect, useState } from "react";

// Fantasy mode is a per-device setting (Profile > Settings) for readers who want the sports game.
const KEY = "oulu-fantasy-mode";
const read = () => { try { return localStorage.getItem(KEY) === "on"; } catch { return false; } };

export function useFantasyMode() {
  const [on, setOn] = useState(read);
  useEffect(() => { try { localStorage.setItem(KEY, on ? "on" : "off"); } catch { /* private mode */ } }, [on]);
  return [on, setOn];
}
