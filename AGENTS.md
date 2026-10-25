# Agent instructions — Kalevalo reader app (`frontend/`)

Read this before touching any UI. It overrides any earlier plan, including `docs/UI_REBUILD_HANDOFF.md`.

## 1. The demo UI is not a reference

The old demo UI (phone frame, TikTok-style `StorySlide`/`PostSlide`, `NewsCard`, `BottomNav`, the `.screen`/`.block`/`.vote-card` classes in `styles.css`) was a **throwaway**. Two rebuilds were rejected for keeping its layout and recolouring it.

- **Do not port that layout, section order, component split or class structure.** Not "cleaned up", not "restyled". A new screen that a reviewer can map 1:1 onto the old demo screen is a failed screen.
- **What you may reuse:** data and behaviour only — `features/*/api.js`, `features/*/hooks/`, `AuthProvider`, `lib/api.js`, `lib/i18n.js`, and side effects from the old implementations (QR-code preset in onboarding, `interact()` ranking signals in Story, OAuth hash handling in Welcome). Read the implementation to list its behaviours, then design from the reader's job.

## 2. Look and feel: Clean, fast news feed

**Kajo** (our design system, `/design`, `src/components/ui` + `src/components/patterns`) supplies the
**tokens**: colour, type and meaning. Keep the UI minimal, scannable, and mobile-first with strong desktop layouts.

Kajo stays as is for:
- **Colour = provenance.** Monochrome UI. Blue (`newsroom`) = editor-reviewed / in your language;
  cloudberry (`community`) = a member's words, unreviewed; spruce (`confirmed`) = people confirmed it;
  red (`danger`) = correction/error. Selection, focus and primary actions are ink.
- **Type:** IBM Plex Sans + Plex Sans Arabic, Kajo's type scale.
- **Patterns:** `Provenance`, `LangStatus`, `TrustBlock`, `NeedTag`, `QueryBoundary`, `Meter`, toasts, dialogs.

Feed guidelines:
- **Timeline-first.** For the home/feed, use a vertical timeline similar to X/Twitter: tight rows with avatar/source, headline, summary/image, and lightweight actions. Prioritize scannability.
- **Clean chrome.** Subtle dividers between items, minimal shadows, plenty of breathing room on mobile.
- **Responsive.** Design desktop and mobile separately; don't just stretch the phone layout.
- **Provenance visible.** Show language status and who stands behind content clearly.

## 3. Layouts — design desktop and mobile separately

Desktop is not a stretched phone and mobile is not a squeezed desktop. Every screen ships with
**both** layouts designed on purpose. A centred 400px column on a 1440px screen, a sticky
full-width button on desktop, or a bottom tab bar on desktop is a bug.

**Desktop (≥ 1024px)**
```
┌──────────────┬─────────────────────────────────────────────────┬──────────────┐
│ Kalevalo  ▾ │  For You / Housing               updated 2h  ⋯ │              │
│──────────────│─────────────────────────────────────────────────│  side peek   │
│ 🔍 Search    │                                                 │  (story,     │
│ ⌂ For You    │   Page title                                     │   replies,  │
│ ◉ Next stories│   properties · · ·                               │   notes)    │
│ ✎ Ask        │                                                 │              │
│              │   content column, max 720px, left-aligned       │  480–560px   │
│ COMMUNITIES  │   inside the main area (full width for          │  opens over  │
│  › Newcomers │   database views)                               │  or beside   │
│  › Students  │                                                 │  main        │
│──────────────│                                                 │              │
│ ◐ Українська │                                                 │              │
│ 👤 @olena    │                                                 │              │
└──────────────┴─────────────────────────────────────────────────┴──────────────┘
 sidebar 240px, collapsible (⌘\), bg-sunk
```

**Tablet (768–1023px):** sidebar collapses to a drawer opened from the top bar; side peek becomes a
full-height overlay panel.

**Mobile (< 768px)**
```
┌───────────────────────────┐
│ ☰  For You          🔍 ⋯ │  top bar: menu opens the sidebar as a drawer
│───────────────────────────│
│ Page title                │
│ content, 16px gutters     │
│                           │
│                           │
│───────────────────────────│
│  ⌂     👥     ◉     ✎    │  bottom bar ONLY on mobile: For You, Community,
└───────────────────────────┘  Next stories, Ask (Notion mobile: Home/Search/Inbox/New)
```
Sticky bottom CTAs are allowed only on mobile, only for single-task flows (onboarding, compose).

## 4. Screen mapping (what each screen is, in Notion terms)

| Screen | Reader's job | Layout | Desktop | Mobile |
|---|---|---|---|---|
| Auth | Get in fast; judges use demo | Clean auth | Centred column with wordmark, Google first, email form, demo links; generous spacing | Full-width, comfortable controls (44px) |
| Onboarding | Set language, topics, situation, communities | Step flow | Centred multi-step form, clear hierarchy, inline actions | One question per screen, sticky bottom action |
| For You (feed) | See what affects me, in my language | **X/Twitter timeline** | Left sidebar + centred timeline (max ~680px), dividers, composer/filters optional, click story → full page or side panel | Full-width timeline rows, tap → story page, bottom nav |
| Story | Understand it, trust it, act | Reading page | Spacious reading column (max ~720px) with provenance, trust blocks, sources, actions | Single column, clear hierarchy, sticky/share actions as appropriate |
| Community | Ask, answer, help | Timeline/feed of posts | Left sidebar + timeline; post thread in side panel or full page | Full-width posts, thread on full page |
| Next stories (vote) | Choose what gets covered | List of proposals | Clean list with vote actions, Meter, clear states | List with vote buttons, clear states |
| Notes | Rate community notes credibly | Threaded notes | Clean list/thread with badges and rating | Full page/thread |
| You | Preferences, saved, communities | Settings list | Clean settings with sections | Full-page settings |
| Ask / Create | Send a tip/question to the newsroom | Compose form | Centred form/dialog as fits | Full page with sticky Send |

Fantasy stays its own immersive dark experience; only align neutrals and type.

## 5. How to build a screen

1. Write the reader's job and the challenge criterion it proves (`the_challenge.md`, "What we value").
2. List the data (from `api.js`/hooks and `backend/apps/*/serializers.py`) and the behaviours.
3. Pick the layout from §4 and draw **both** wireframes (desktop, mobile) in ASCII in your
   notes before writing JSX. If it resembles the demo screen, start again.
4. Build from Kajo primitives/patterns; add missing ones to `components/` and to `/design` first.
5. Handle loading/empty/error with `QueryBoundary`. Replace every `window.alert/confirm/prompt`.

## 6. Definition of done

- Screenshots checked at **1440px**, **1024px** and **390px** wide, light and dark.
  The browser tool can't resize the window; check mobile by loading the route in an iframe from any
  localhost page:
  `document.body.innerHTML = '<iframe src="/welcome" style="width:390px;height:844px;border:1px solid #ccc">'`
- Keyboard: every action reachable, focus visible. RTL (Arabic) doesn't break the layout.
- No dynamic Tailwind class names; no legacy class names that collide with utilities.
- `npm run build` passes. Never show invented text in Sámi or other reader languages.

## 7. Environment

- Dev server: Docker, http://localhost:5173 (hot reload). Config/dependency changes may need
  `docker compose up -d --force-recreate frontend`. `npm run build` on the host for quick checks.
- Demo accounts: newcomer@example.com / demo-reader (Ukrainian), fan@example.com / demo-reader (Finnish).
- Out of scope: the Django HTML admin (`backend/frontend/*.html`).
