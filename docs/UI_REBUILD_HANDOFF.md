# UI Rebuild — Session Handoff

_Last updated: 2026-10-24_

Production rebuild of the **reader app** (`frontend/`) — replacing the demo UI with a real,
accessible, responsive design system. This doc is the state of play so a new session can continue.

---

## TL;DR — where we are

- **Branch:** `design/ui-refresh` (off `master`, which already has the feature-based refactor + the
  fantasy merge). **Work is currently UNCOMMITTED** — commit early in the next session.
- **Foundation is built and working** (Tailwind + Radix, shadcn-style, token-driven).
- **Auth (Welcome) is rebuilt** — responsive, light + dark, mobile-first. Done & verified on desktop.
- **Next up: Onboarding**, then the reader screens in order (see Roadmap).
- The legacy app stays **pristine and fully working** behind the phone frame; we migrate screen by
  screen and delete `styles.css` rules as each screen moves.

Dev server runs in Docker at **http://localhost:5173** with hot reload. Demo login on the Welcome
screen: **newcomer@example.com / demo-reader** (reads Ukrainian) or **fan@example.com** (Finnish).

---

## Why this rebuild (the challenge)

The reader app is the demo judges see. Its job is to make the **judged** features legible, which the
old demo UI buried: community at the core, human-in-the-loop + open AI disclosure, error/trust
handling (incl. **Sámi languages are never machine-translated**), and explanatory "what this means
for _me_." See `docs/ARCHITECTURE_AND_CHALLENGE_FIT.md` and `the_challenge.md`.

Every rebuilt screen should make those moments **lead**, not hide. Especially: the **Story** trust
rail, and the **"in your language"** treatment (currently reads as a failure tag — should be a calm,
confident feature with an honest fallback state).

---

## Decisions locked (do not re-litigate without reason)

1. **Stack: Radix primitives + Tailwind (shadcn-style).** Not Radix-only, not CSS Modules, not
   plain CSS. Chosen for a production component layer with real a11y. Hand-authored components (we
   own them), not the shadcn CLI.
2. **Design language: "Nordic Paper."** Cool off-white ground, ONE cold Finnish-blue accent
   (`#1B4DD1`), hairline structure, elevation only on things that float. Single typeface **Schibsted
   Grotesk** across weights. Accent is rationed — primary actions + the "in your language" signal only.
3. **Drop the fake phone frame for rebuilt screens.** They are full-viewport responsive (mobile-first,
   genuinely good on desktop). Legacy (not-yet-rebuilt) screens keep the 390px phone frame until
   migrated.
4. **Immersive surfaces stay dark** (the TikTok-style `StorySlide` swipe, and Fantasy) — but driven
   from tokens, not hardcoded colors. Don't flatten them to paper.
5. **Production states everywhere:** real loading / empty / error for each data view (standardize via
   a `QueryBoundary` pattern over the existing React Query hooks). **Replace `window.alert` /
   `confirm` / `prompt`** (Story report, Create) with `Toast` + `Dialog`.
6. Light **and** dark both designed; tokens auto-switch via `prefers-color-scheme` + `data-theme`.

The visual direction was proven in a style-tile artifact: https://claude.ai/artifact/LB3bpjtTnccUJ5BETFbu7b

---

## What exists now (files)

**Design system foundation**
- `frontend/src/styles/globals.css` — **single source of truth** for tokens. HSL-channel vars
  (`--*-hsl`, so Tailwind opacity utilities work) + derived color vars + light/dark blocks + base
  `body`. Imported first in `main.jsx`.
- `frontend/tailwind.config.js` — maps tokens to `paper / surface / ink / muted / line /
  accent{,-weak,-ink} / danger`, `font-sans` (Schibsted Grotesk), radii (`lg/md/sm/pill`),
  `shadow-soft/float`. `darkMode: ["selector", '[data-theme="dark"]']`.
- `frontend/postcss.config.js` — tailwind + autoprefixer.
- `frontend/src/lib/utils.js` — `cn()` (clsx + tailwind-merge).

**UI primitives** — `frontend/src/components/ui/` (barrel `index.js`):
`button`, `chip`, `badge`, `card`, `field`, `input` (+`Textarea`), `spinner`, `stepper`,
`option-card` (`RadioCards` single-select, `ToggleCards` multi-select — both Radix-backed).

**Installed but not yet wrapped** (add primitives when the feature needs them): Radix `dialog`,
`tabs`, `toggle-group`, `radio-group`, `dropdown-menu`, `tooltip`, `toast`, `switch`, `avatar`,
`popover`, `progress`.

**Rebuilt screen**
- `frontend/src/features/auth/pages/Welcome.jsx` — full-viewport, responsive, light+dark.
  Desktop = two-column (brand/value left, form right). Mobile = compact brand → form → value
  points + language chips below. Uses real supported-language chips + 3 challenge-tied value points.

**Shell**
- `frontend/src/App.jsx` — layout-route split: `/welcome` renders full-viewport; everything else is
  wrapped in `<LegacyFrame>` (the phone frame) until rebuilt. As screens are rebuilt, move their
  `<Route>` out of `LegacyFrame` to a full-viewport route.
- `frontend/src/main.jsx` — imports `@/styles/globals.css` **then** `./styles.css`.
- `frontend/index.html` — loads Schibsted Grotesk + Inter + Source Serif (legacy fonts kept until
  `styles.css` is deleted). `theme-color` is paper.

**Legacy (pristine, temporary)**
- `frontend/src/styles.css` — original tokens restored at top; all old component classes intact.
  The desktop scroll-lock is scoped to `body:has(.app)` so full-viewport pages scroll. **Delete this
  file (and the legacy font links) once every screen is migrated.**

---

## Rebuild roadmap (order)

1. ✅ **Welcome / auth**
2. ⏭ **Onboarding** — 4-step flow (language → topics → situation → communities). Build on
   `RadioCards` (language, situation), `ToggleCards` (topics), `Stepper`. Responsive, mobile-first.
   Then promote its route out of `LegacyFrame`. File: `features/account/pages/Onboarding.jsx`.
3. **Feed** (`features/feed/pages/Feed.jsx` + `components/NewsCard`) — hairline reader list on paper
   (not black); "in your language" / "picked for you" as confident signals. Needs `Tabs`. Build the
   responsive `AppShell` + `BottomNav` (mobile bottom nav → desktop side rail) here.
4. **Story** (`features/feed/pages/Story.jsx`) — the trust surface. Make "what this means for you",
   "why you're seeing this", AI/reviewer disclosure, and the translation-fallback notice LEAD.
   Replace `window.prompt`/`alert` report flow with `Dialog` + `Toast`.
5. **Communities** (`Communities`, `PostSlide`, `CommentsSheet`, `CommunityCard`) — "member post,
   not reviewed" labeling; Community Notes as first-class trust device. Needs `Dialog`/`Sheet`.
6. **Shortlist / Vote** — "what should we cover next" as a tactile vote + "you voted, we covered it".
7. **Notes** (`NotesSheet`) — credible rating flow (status: shown/pending/hidden via `Badge`).
8. **Profile** — rebuild rows, fantasy-mode toggle (Radix `Switch`).
9. **Fantasy** — keep its energy; align neutrals/structure/type to the tokens.

Also along the way: `patterns/` layer (AppShell, BottomNav, Header, QueryBoundary, StoryCard,
Disclosure, CommunityNote).

---

## Gotchas / environment

- **Hot reload is automatic** for `.jsx`/`.css` edits (container mounts `./frontend`, runs Vite).
  **New npm deps or config changes (`tailwind.config.js`, `postcss.config.js`, `vite.config.js`)
  need:** `docker compose up -d --force-recreate frontend` (reinstalls into the container's volume).
- Host `node_modules` is owned by `charlie` (was chowned off root). Host `npm run build` works for
  fast validation; the container has its own `frontend_node_modules` volume.
- **Browser tooling limits (this environment):** `resize_window` and viewport-meta overrides do **not**
  change the desktop Chrome viewport, and screenshots intermittently time out (retry 1–3x). Could not
  verify phone-width visually — reason from the DOM or ask the user for a screenshot + width.
- Backend stack also runs via `docker compose` (web :8000, docs at `/api/docs/`). Fantasy data is
  seeded; `setup` service runs migrations+seed on `up`.
- The Django HTML admin (`backend/frontend/index.html`, `fantasy.html`) is **out of scope** — do not
  touch it. Only `frontend/` (the React reader app).

## Open polish items

- Ghost demo-account buttons on Welcome are a touch low-contrast — give clearer affordance.
- Confirm Welcome at true phone width (tooling couldn't; fix was a mobile-first reorder).

## Token system quick ref

Add/adjust colors in `globals.css` as `--x-hsl: H S% L%` (define in `:root`, redefine in both dark
blocks). Reference in CSS as `hsl(var(--x-hsl))` or in Tailwind as the mapped name (`bg-accent`,
`text-muted`, `border-line`, `bg-accent/30` for opacity). Keep the light block the primary; mirror
every token in the `@media (prefers-color-scheme: dark)` and `:root[data-theme="dark"]` blocks.
