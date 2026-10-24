# Reader app (React + Vite)

The phone-first app readers use, laid out like TikTok: two full-screen, vertically swiping
feeds, **For You** (reviewed news, personalised and in the reader's own language) and
**Community News** (posts written by members of their community), plus onboarding, story
pages, a "+" composer, saved stories and the profile. It talks to the
Django API in `../backend` over HTTP (CORS is enabled for it).

## Run it

**With Docker (from the repo root), nothing to install:**

```bash
docker compose up -d          # also starts the backend
```

Open http://localhost:5173. Edits to `src/` reload instantly.

**Without Docker** (needs Node 20+; the backend must be running on :8000):

```bash
cd frontend
npm install
npm run dev
```

The API address comes from `VITE_API_URL`, default `http://localhost:8000`. Copy `.env.example`
to `.env` to change it, e.g. to your computer's LAN IP when you open the app on a phone.

Log in with a demo account (buttons on the welcome screen), or create one:
- `newcomer@example.com` / `demo-reader`: reads Ukrainian, newcomer, arrived 5 days ago
- `fan@example.com` / `demo-reader`: reads Finnish, sports and culture

## Structure

```
src/
  main.jsx            entry: router + auth provider
  App.jsx             routes; signed-out → /welcome, not onboarded → /onboarding
  styles.css          the whole design: tokens (colours, radius) at the top, then per screen
  lib/
    api.js            every API call the app makes (one function per endpoint)
    auth.jsx          login state (JWT in localStorage), useAuth()
    i18n.js           languages, reader situations, topic icons, "3 hours ago"
  components/
    StorySlide        one full-screen For You story + right-hand action rail
    PostSlide         one full-screen community post (labelled): Like, Comments, Share (with counts), Report
    CommentsSheet     a post's replies (translated, likeable) and a box to add one
    NotesSheet        Community Notes on a post: read, rate (helpful? + reasons) and write one
    CommunityCard     a community with why it's suggested and a Join / Leave button
    BottomNav         TikTok-style bar: Home, Discover, +, Saved, Profile
    NewsCard          list card (Discover, Saved); ListenPlayer (read-aloud); Spinner
  pages/
    Welcome           sign up / log in / demo accounts
    Onboarding        language → categories → situation + arrival date → communities to join (also "Edit preferences")
    Communities       your communities, suggested ones (with why) and the rest; Join / Leave
    Feed              home: For You = one continuous list of story cards (tap opens the story); Community News = full-screen swipe of member posts
    Create            "+": post to your community, or send a tip / question to the newsroom
    Story             full story: for-you text, key facts, Finnish original, why ranked, report
    Explore           "Discover": topics + the newcomer "first week" sequence
    Vote              "What should we cover next?": members vote on the newsroom's shortlist (votes count in its next run)
    Saved, Profile
```

## How it uses the API

| Screen | Endpoint |
|---|---|
| Log in / sign up | `POST /api/auth/token/`, `POST /api/accounts/register/` (`{email, username, password}`); Profile changes the username with `PATCH /api/accounts/me/` |
| Onboarding | `GET /api/accounts/interests/`, `POST /api/accounts/onboarding/`, `GET /api/accounts/onboarding-link/<code>/` (QR), `GET /api/communities/groups/recommended/`, `POST …/groups/<slug>/join/` |
| Communities | `GET /api/communities/groups/`, `…/groups/recommended/`, `POST …/groups/<slug>/join/` and `…/leave/` |
| For You, Discover | `GET /api/feed/snippets/?tag=…`, `GET /api/feed/arrival/` |
| Community News | `GET /api/communities/news/` (with `translation`, `answered_by`, `like_count`, `liked`, `reply_count`, `share_count`); on `/api/communities/groups/<slug>/posts/<id>/`: `like/` (POST / DELETE), `share/`, `flag/`; replies: `GET …/posts/?parent=<id>`, `POST …/posts/ {body, parent}` |
| Create (+) | `POST /api/communities/groups/<slug>/posts/`, `POST /api/communities/contributions/` (tip/question) |
| Story | `GET /api/feed/snippets/<id>/`, `POST …/interact/` (like, bookmark, view, read_through, expand, share), `POST …/report/` |
| Saved | `GET /api/feed/snippets/bookmarks/` |
| Vote | `GET /api/agents/shortlist/`, `POST`/`DELETE /api/agents/shortlist/<id>/vote/` |

Every card already arrives in the reader's profile language (`language`), with
`original` (the Finnish text), `for_you` (what it means for their situation),
`in_your_language` (false → we show English/Finnish until the translation is approved)
and `ranking` (why it's in their feed). Full field list: `docs/GUIDE.md` §7, or
http://localhost:8000/api/docs/.

## Two kinds of content, kept visibly apart

- **For You** is journalism: AI-drafted, approved by human editors, translated and checked.
- **Community News** is written by readers and published straight away. Every post says
  "Community post · not reviewed by editors". Anyone can report a post, and it is then
  hidden until a moderator (community editor or editor) keeps or removes it in the admin
  dashboard's Community section. This follows the JSN guidelines' annex on content published by the public.
  - Posts arrive translated into the reader's language when a model is available (`translation`);
    `PostSlide` shows it with an "Auto-translated from X · Show original" toggle.
  - A question post links to the newsroom story that answers it (`answered_by`), shown as
    "Answered by the newsroom" on the slide.
- **Tips and questions** sent with "+" go privately to the newsroom and are never published as written.

## Notes for changes

- **Phone frame:** on a phone the app fills the screen. On a computer it is laid out at a real phone's size (390 x 844) and the whole phone is scaled down to fit the window (`--phone-scale`, set in `main.jsx`; `.app` in `styles.css`). Pages scroll inside `.app-scroll`, not the browser window.
- **Colours, spacing, radius:** CSS variables at the top of `styles.css`.
- **Topic icons and blurbs:** `TOPICS` in `src/lib/i18n.js` (keys are the interest slugs from the API).
- **Images:** stories have no photos yet, so cards show a gradient with the topic icon. When the API returns `image_url`, it's shown automatically.
- **App text** is English; times and dates already follow the reader's language. Translating the app's own text (buttons, headings) is a good next step.
- **QR onboarding:** `/onboarding?code=OULU-WELCOME` presets language and arrival date (codes are seeded by `manage.py seed_demo`).
- **Read aloud** uses the browser's speech synthesis in the story's language; it hides itself where unsupported.
