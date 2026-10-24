# Proposed Business Model

A revenue model for a multilingual, agent-run, community news medium under Kaleva Media.
It answers each prompt the challenge raises: willingness to pay, who benefits, where the money
comes from, the special case of language minorities, conflicts of interest, the link to Kaleva's
business, and costs.

The guiding principle: **different communities have different payers.** No single revenue stream
fits a Somali refugee family, an Oulu tech professional, a Levi seasonal worker, and a Sámi speaker.
We match each community to the party that already gains when it is well informed.

---

## 1. Who pays, per community

| Community | Can/will *they* pay? | The real payer (B2B) |
|---|---|---|
| Oulu tech professionals & families | Yes — consumer subscription | Employers (talent retention) |
| International students & researchers | Low (price-sensitive) | Universities & UAS (onboarding, retention) |
| Lapland seasonal tourism workers | No (short stay, low wage) | Tourism employers & resorts (yearly recruitment) |
| Refugee-background residents | No | Municipalities, integration services, public funding |
| Sámi speakers | No (public-good language vitality) | State / Sámi Parliament / foundations |
| Swedish speakers | Partly | Existing Kaleva/BL subscription base + foundations |

**Takeaway:** consumer subscriptions are realistic for only one or two segments. The scalable money
is **B2B licences and public/foundation funding**, because the beneficiaries of an informed newcomer
are usually institutions, not the newcomer.

---

## 2. Revenue streams

1. **B2B "onboarding" licences (primary).**
   Employers, universities and municipalities pay a per-seat or per-cohort annual fee to give their
   international hires / students / residents a localized, multilingual news + essential-info feed.
   Pitch: *"Your talent stays if they can live here. We make the city legible in their language."*

2. **Consumer freemium (secondary).**
   Free: translated headlines + core feed. Paid (~€5–8/mo): full explainers per situation, saved
   topics, audio, ask-the-newsroom priority. Targets the tech-professional segment who can and will pay.

3. **Public & foundation funding (minorities).**
   Sámi and, partly, Swedish content is a **language-vitality public good**, not a consumer product.
   Fund it like public-service media: state support, Sámi Parliament, and foundations (e.g.
   Kone Foundation, Svenska kulturfonden). This also covers the cost of **human** Sámi translators,
   which the product mandates (AI never publishes Sámi).

4. **Events & community partnerships.**
   Local info events, employer onboarding sessions, sponsored "how life works here" guides — clearly
   labelled, kept separate from news per JSN 16.

5. **Recruitment & services inventory (careful).**
   Job and housing listings relevant to newcomers. High intent, high value, but ring-fenced from editorial.

---

## 3. Who benefits (why B2B works)

An informed newcomer is worth money to parties *other than the newcomer*:
- **Employers** reduce costly early churn of relocated talent.
- **Tourism companies** re-recruit the same seasonal workers each year instead of re-training.
- **Universities** improve retention and international ranking.
- **Municipalities & service providers** cut the cost of confused, mis-served residents.

We sell to the party that already carries this cost today.

---

## 4. Guarding independence (the hard part)

If an employer or municipality pays, can we report critically on them? Rules we commit to:

- **Payers buy access and language, never coverage.** Contracts explicitly exclude editorial control.
- **The human-in-the-loop editorial layer is the firewall.** The same JSN standards, audit log and
  corrections apply to a funder as to anyone else (see `editorial` app).
- **Disclosure by default.** The product already discloses AI involvement (`ai_role_disclosed`); we add
  disclosure of the funder for any community whose feed is institutionally sponsored.
- **No single-funder capture.** A community's feed is funded by a mix (several employers + public money),
  so no one payer can pull the plug on critical coverage.

---

## 5. Willingness to pay — how we'd test it

- **Pre-sell B2B first.** Three signed letters of intent from Oulu employers / a university beat any survey.
- **Freemium conversion probe.** Ship the free tier; measure paywall click-through on explainers.
- **Price-sensitivity by segment.** Van Westendorp survey split tech-pro vs. seasonal worker to confirm
  the assumption that only the former pays.

---

## 6. Costs & break-even

An agentic newsroom is cheaper than a traditional one, but not free. Cost drivers per community/language:

- **LLM calls** — roughly `AGENT_MAX_ITEMS × ~5 calls` per shift, every `AGENT_SCHEDULE_MINUTES`.
  Tunable: fewer stories/run, cheaper models per desk (`LLM_MODEL_<AGENT>`), or the offline stub.
- **Human editors** — the dominant cost; the whole model relies on human review and Sámi translation.
- **Infra** — modest (Django + Celery + Redis + Postgres).

**Rule of thumb:** a language/community pays off when `(B2B seats + subscriptions + grants)` for it exceed
`(editor + translator time + LLM + infra)`. A low-cost language (good AI translation, light review) breaks
even on a single mid-size employer contract; Sámi will not break even and is intentionally grant-funded.

---

## 7. Link to Kaleva Media

- **New subscribers** from audiences Kaleva reaches poorly today (non-Finnish speakers).
- **New ad / recruitment inventory** aimed at a high-intent newcomer audience.
- **A new B2B revenue line** (employer/university/municipality licences) that Kaleva's consumer business
  does not currently have.
- **Reuse of the existing newsroom** as the human-in-the-loop layer — the agents scale the output, Kaleva's
  journalists supply the trust.

---

## 8. One-line summary

Consumers rarely pay for the news that helps them settle — but the employers, universities and
municipalities who *need* them to settle do. Sell B2B onboarding licences and public-good funding for
minorities, keep a strict editorial firewall, and let Kaleva's journalists remain the trust the agents
cannot manufacture.
