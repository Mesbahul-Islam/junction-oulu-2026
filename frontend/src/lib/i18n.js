// Language names, topic icons and small formatting helpers.

import {
  Briefcase, Bus, CalendarDays, Clock, CloudSun, GraduationCap, HeartPulse, House, Landmark, Newspaper,
  Palette, Plane, Scale, ShieldAlert, Trophy,
} from "lucide-react";

// Languages a reader can choose. The newsroom translates into every language its readers pick.
export const LANGUAGES = [
  { code: "fi", name: "Suomi", english: "Finnish" },
  { code: "en", name: "English", english: "English" },
  { code: "sv", name: "Svenska", english: "Swedish" },
  { code: "uk", name: "Українська", english: "Ukrainian" },
  { code: "ru", name: "Русский", english: "Russian" },
  { code: "ar", name: "العربية", english: "Arabic" },
  { code: "so", name: "Soomaali", english: "Somali" },
  { code: "et", name: "Eesti", english: "Estonian" },
  { code: "se", name: "Davvisámegiella", english: "Northern Sámi" },
];
export const RTL = new Set(["ar"]);
export const languageName = (code) => LANGUAGES.find((l) => l.code === code)?.name || code;

export const SITUATIONS = [
  { value: "newcomer", label: "I just moved to Finland", short: "a newcomer" },
  { value: "student", label: "I'm a student", short: "a student" },
  { value: "seasonal_worker", label: "I'm a seasonal worker", short: "a seasonal worker" },
  { value: "resident", label: "I've lived here a while", short: "a local" },
];

// Interest / topic slugs from the API -> icon and a short subtitle for the category cards.
export const TOPICS = {
  housing: { icon: House, blurb: "Rent, housing, neighbourhoods" },
  work: { icon: Briefcase, blurb: "Jobs and working life" },
  health: { icon: HeartPulse, blurb: "Health care and wellbeing" },
  transport: { icon: Bus, blurb: "Buses, roads, travel" },
  education: { icon: GraduationCap, blurb: "Schools and studying" },
  culture: { icon: Palette, blurb: "Arts, theatre, music" },
  sports: { icon: Trophy, blurb: "Kärpät and local sport" },
  events: { icon: CalendarDays, blurb: "What's on in town" },
  services: { icon: Landmark, blurb: "Kela, city services" },
  weather: { icon: CloudSun, blurb: "Weather and conditions" },
  immigration: { icon: Plane, blurb: "Permits and moving here" },
  legal: { icon: Scale, blurb: "Laws and rights" },
  safety: { icon: ShieldAlert, blurb: "Safety notices" },
  opening_hours: { icon: Clock, blurb: "Opening hours" },
};
export const topicIcon = (slug) => TOPICS[slug]?.icon || Newspaper;
export const topicLabel = (slug) => (slug || "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

// "3 hours ago", in the reader's language.
export function timeAgo(iso, lang = "en") {
  if (!iso) return "";
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  const steps = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return rtf.format(0, "minute");
}
