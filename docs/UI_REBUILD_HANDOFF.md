# UI Rebuild — Session Handoff

_Last updated: 2026-10-24_

Production rebuild of the **reader app** (`frontend/`). The design system is **Kajo** (Finnish: the
faint light of the polar night). Live reference of everything: **http://localhost:5173/design**.

---

## TL;DR — where we are

> **Read `/AGENTS.md` first.** It sets the direction: Notion look and feel on Kajo tokens, designed
> desktop **and** mobile layouts, and no reuse of the demo UI's layouts. It overrides this doc.

- **Branch:** `design/ui-refresh`. Kajo is built but **uncommitted**.
- **Kajo tokens/primitives/patterns exist** and are shown at `/design`. AGENTS.md §2 lists the changes
  still needed for the Notion feel (smaller radii, denser desktop controls, sidebar/top bar/side peek…).
- **Welcome and Onboarding were rejected:** they still follow the demo's mobile-centric layouts.
  Redo both per AGENTS.md §4.

Dev server: Docker at **http://localhost:5173**. Demo login on Welcome:
**newcomer@example.com / demo-reader** (Ukrainian) or **fan@example.com** (Finnish).

---

## The rule (why the last pass was rejected)

Do **not** keep a legacy screen's layout and swap its colours. For each feature: start from what
the reader is trying to do and which challenge criterion it proves (`the_challenge.md`), then compose
it from Kajo patterns. If a pattern is missing, add it to `components/patterns/` and to `/design`.

---

## Kajo in one paragraph

The interface is **monochrome** (polar-night ink on snow; primary buttons are ink). **Colour only
ever says who stands behind content** — the challenge's trust criteria made visible:

| Token | Meaning | Where |
|---|---|---|
| `newsroom` (blue) | Editor-reviewed; "in your language" | LangStatus, Provenance, "What this means for you" |
| `community` (cloudberry) | A member's words, not reviewed | posts, avatars ring, "Asked for by…" |
| `confirmed` (spruce) | People confirmed it | Community notes shown, "you voted, we covered it" |
| `danger` (red) | Correction / error / high risk | corrections, report, error states |

Selection and focus are **ink**, never a tone. Type is **IBM Plex Sans + Plex Sans Arabic** (one voice
across Latin/Sámi/Cyrillic/Arabic; Schibsted Grotesk had no Cyrillic). Radius encodes hierarchy:
`rounded-control` 12 < `rounded-card` 18 < `rounded-sheet` 28; `rounded-pill` only for tags.
Shadows only on floating things (`shadow-float`). All text/background pairs pass WCAG AA in both
themes (checked).

---

## Files

**Tokens**
- `src/styles/globals.css` — all colour channels (`--*-hsl`), light + both dark blocks.
- `tailwind.config.js` — colours, type scale (`text-caption/meta/ui/body/lead/title/headline/display/hero`),
  radii, shadows, `ease-kajo`, `max-w-read` (40rem reading column).
- `src/lib/utils.js` — `cn()`; tailwind-merge is **extended with Kajo's custom scales** (otherwise it
  reads `text-ui` as a colour and drops `text-on-ink`). Self-check: `node src/lib/utils.js`.

**Primitives** — `src/components/ui/` (barrel `index.js`)
`Button` (primary/secondary/ghost/link/danger; sm/md/lg/icon/icon-sm), `Badge` (tone × solid/soft/outline),
`Card` (flat/sunk/float/ghost), `Field`, `Input`, `Textarea`, `Switch`, `RadioCards`, `ToggleCards`, `ToggleChips` (pills),
`Stepper`, `Tabs`, `Dialog` + `DialogContent placement="center"|"sheet"` (sheet = bottom on phones,
right panel on desktop), `toast()` + `Toaster` (mounted in `app/providers.jsx`; replaces
`window.alert/confirm/prompt`), `Meter`, `Avatar` (`community` ring), `Spinner`, `Skeleton`.

**Patterns** — `src/components/patterns/` (barrel `index.js`)
- `AppShell` (layout route: desktop left rail, mobile bottom bar; sets `dir`/`lang`), `NAV`
  (Today · Community · Decide · You, plus "Ask the newsroom"), `Page` (reading column / `wide`),
  `PageHeader`, `Wordmark`.
- `trust.jsx`: `LangStatus` + `langStatusOf(card)` (yours / human-translated incl. Sámi / fallback /
  original), `Provenance` (newsroom / community / correction), `TrustBlock` (ruled block by tone),
  `NeedTag` (Kaleva's six reader needs, from `card.reader_needs`).
- `StoryCard` (`variant="row"|"lead"`, takes the API card as-is).
- `QueryBoundary` (loading/error/empty around a React Query result), `EmptyState`, `ErrorState`,
  `ListSkeleton`.

**Showcase** — `src/features/design/pages/DesignSystem.jsx` at `/design` (no login). Uses sample
data in the API's real card shape, so it doubles as the pattern contract.

**i18n** — `LANGUAGES` now has all three Sámi languages (se, smn, sms); `SAMI` set mirrors the backend.

**Legacy (temporary)** — `src/styles.css` + Inter/Source Serif font links. The legacy `.block` class
was renamed `.story-block` (it collided with Tailwind's `block`). Watch for other legacy class names
that collide with utilities. Delete the file once every screen has moved.

---

## Roadmap (restructure, in order)

1. **AppShell + Today (Feed)** — swap `LegacyFrame` for `<AppShell>` as the layout route. Today =
   `PageHeader` + `Tabs` (For you / From your community) + lead `StoryCard` + rows, inside
   `QueryBoundary`. Search (old Explore) moves into Today's header. Saved moves under You.
2. **Story** — the trust page. Order: headline → `Provenance` → `LangStatus` (+ fallback `TrustBlock`)
   → "What this means for you" `TrustBlock` → key facts → community notes / corrections → "Why you're
   seeing this" `Meter`s → sources → Report (`Dialog` + `toast`). Listen player restyled. The swipe
   `StorySlide` stays an immersive dark mode, driven by tokens.
3. **Community** — posts with `Provenance kind="community"`, replies in a sheet, "Ask the newsroom to
   check" as the bridge from a post to journalism.
4. **Decide (Vote)** — the shortlist as a vote with tallies; "You voted, we covered it" in `confirmed`.
5. **Notes** — rating flow in a sheet; status via `Badge` (shown = confirmed, pending = neutral, hidden = danger).
6. **You (Profile)** — language, situation, saved, communities, Fantasy toggle (`Switch`).
7. **Welcome + Onboarding** — redo per AGENTS.md §4 (rejected rebuilds).
8. **Create / Ask the newsroom** — `Field` + `Textarea` + consent, `toast` on send.
9. **Fantasy** — keep its own energy; align neutrals and type to tokens.

---

## Gotchas / environment

- Hot reload is automatic for `.jsx`/`.css`. **New deps or config changes** (`tailwind.config.js`,
  `postcss.config.js`, `vite.config.js`) may need `docker compose up -d --force-recreate frontend`.
- Host `npm run build` works for fast validation.
- Legacy `styles.css` loads after Tailwind and sets `body` font to Inter: rebuilt roots must set
  `font-sans` (AppShell does).
- Legacy `button { border: 0 }` was changed to `border-width: 0`; the shorthand set
  `border-style: none` and hid every Tailwind border on buttons (tabs, secondary buttons).
- Never write dynamic Tailwind class names (`` `bg-${tone}` ``); map to literal strings.
- Never put made-up text in Sámi (or any reader language) on screen; the challenge calls out that
  errors offend the language community. Use glyph samples or real reviewed content.
- Browser tooling: screenshots sometimes come back blank or time out — retry. The viewport can't be
  resized to phone width; reason from the DOM.
- The Django HTML admin (`backend/frontend/*.html`) is out of scope.
