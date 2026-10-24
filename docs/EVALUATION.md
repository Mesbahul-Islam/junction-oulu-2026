# Evaluation against the Kaleva brief (multilingual community news)

Status of `master` on Sat 24 Oct, checked in the code and in the running app's data.

**Overall:** the newsroom machinery is strong, especially the human in the loop, the JSN checks and the safe handling of Sámi. The weak points are the ones the judges weigh most: the **community's part in the newsroom**, **explaining with context from outside the story**, and **one clearly chosen community**. All three can be improved before the deadline.

| What Kaleva values | Status | In one line |
|---|---|---|
| Community at the core | Partial | Members vote on coverage and write notes, but their tips and questions no longer reach the newsroom |
| Responsible journalism, human in the loop | Strong | Nothing is published without a named person. JSN checks are listed for the editor. |
| Agentic operating model and distribution | Partial | Real newsroom desks with a live dashboard. The only channel is the app. |
| Reliability and error handling, small languages | Partial | Facts checked against the source, Sámi left to people. Translations are thin in the data, and there are no tests. |
| Business model | Not in the product | Only Lämäri's sponsors. Needs to be argued in the pitch. |
| Prototype and demo | Strong, with risks | The flow works end to end. Without a working AI model, the demo shows the plain fallback. |

---

## 1. Community at the core: Partial

**What works**
- **"What should we cover next?":** stories the newsroom didn't pick go on a shortlist, members vote, and the next run adds the votes to the ranking (`newsroom/shortlist.py`, `news_editor.community_votes`). Members see their vote turn into a story.
- **Community Notes:** members add context with sources. Others rate them, and a note shows on the story only when raters from different communities find it helpful.
- **Community boards and Community News,** with flagging.
- **Reports:** a reader report takes a story back to the editors.
- **Contributions:** questions, tips, topic ideas and "bridge stories" can be sent to the newsroom.

**Gaps**
- **Contributions don't reach the newsroom any more.** The old scout read open tips and questions and boosted matching stories. The rewritten newsroom (`newsroom/runner.py`, `wire.py`) only reads the Kaleva feed. The 8 contributions in the database go nowhere. Fixing this is the strongest single improvement for this criterion.
- **No trusted voices.** The brief asks who they are and how they take part. There is a community editor role, but nothing gives it a part in the daily work (for example approving what their community sees, or co-signing corrections).
- **The community doesn't evaluate the medium.** There's a feedback prompt model, but no visible "was this useful / what's missing" loop in the app.

## 2. Responsible journalism and human in the loop: Strong

- **No auto-publishing.** Every story is filed as "Ready to send" or "Needs review". A person publishes, and their name is recorded in the audit log (`agents/services.send_story`).
- **High-risk topics need a full review:** residence permits, health, work, legal and safety. A failed fact-check also blocks one-click sending.
- **JSN checks** (`desks.standards`) list what an editor must confirm, including privacy, minors and crime. Sensational headlines are flagged.
- **AI disclosure** on every card: which desks worked on it, who reviewed it, whether it is machine-translated.
- **Public corrections log** (`editorial.Correction`), plus expiry and review-by dates.

**To watch**
- "Ready to send" approves **all machine translations at once** when the editor clicks. For low and medium risk that is defensible, since the card says it is machine-translated. But the judges may ask who checked the Arabic. Say that per-language reviewers are required for high-risk stories, and that other languages carry the machine-translation label.
- The corrections log is **empty** (0 corrections). Demo one correction live.

## 3. Agentic operating model: Strong. Distribution: Partial

**Operating model**
- The desks follow a real newsroom: wire desk, news editor (Jev scoring with the readership, plus member votes), reporter, explainer, translator, fact-checker, standards editor, copy desk, then human editors.
- A live dashboard shows what each desk did.
- Each story serves a Kaleva reader need, set by `heuristic_reader_needs`.

**Distribution**
- Only the web app, plus the newcomer arrival sequence and read-aloud audio (`ListenPlayer`).
- There are no messaging channels (WhatsApp, Telegram), notifications or newsletters, although the brief stresses "channels where communities already are". For seasonal workers especially, a weekly digest in a messaging app would reach them more easily than an app install.
- **Bridge in the other direction:** "bridge story" exists as a contribution type, but nothing produces stories for Finnish readers.

## 4. Reliability and errors: Partial

**What works**
- **Fact-checker** (`desks.fact_checker`): every number in the Finnish draft must appear in the source article.
- **Reporter** writes "from the source only".
- **Translator** uses the glossary terms.
- **Sámi is never machine-translated.** A human translator writes it (`SAMI_LANGUAGES`).
- **Model failures fall back safely** and are noted for the editor.

**Gaps**
- **The explainer uses only the news itself.** The brief says context "may need to come from outside the story", for example what Kela or Waltti is. The reviewed context library (`ContextEntry`, 3 entries) and the glossary are **not used** by the new explainer. Feeding reviewed context into the explainer is the right fix, and it's also the best answer to "how do you avoid made-up facts".
- **Translation coverage is thin in the current data:** 28 Finnish versions, but only 5 English, 8 Arabic, 4 Ukrainian and 2 Swedish, and no Sámi. Most runs today happened without a reachable AI model.
- **The source is two lines long.** Kaleva's RSS gives 36 to 260 characters per article, so there is little to explain from. Ask Kaleva for full text.
- **No tests or reliability measure** (0 test files on `master`). The brief asks how reliability is tested. Even a small script that runs the fact-checker over past stories and reports a pass rate would answer that.

## 5. Business model: not in the product (argue it in the pitch)

The app has no B2B accounts, licences or subscriber tiers. That's acceptable for a prototype, but the pitch must cover it:
- **Payers:** employers and universities (licences), the city and the wellbeing services county (outreach), foundations and public funding (Sámi and Swedish), brands (Lämäri's native prizes).
- **Readers:** essential news stays free.
- **Independence:** payers fund access, not content. Editors decide, funding is disclosed, corrections are public.
- **Kaleva:** a new audience, new B2B income, and Lämäri ad inventory.

## 6. Prototype and demo: Strong, with risks

- It works end to end: RSS, desks, review queue, publish, feed in the reader's language, notes and reports. Lämäri adds a strong second channel and the brand-revenue story.
- **Risks for the live demo:**
  - The AI model (remote Ollama) was unreachable most of the day, so output came from the fallback. Use a working model such as Gemini for the demo.
  - Only 3 stories are published. Approve a few more, in several languages, before demoing.
  - The demo database is spread over 7 communities. Pick one.

---

## Choose the community

The brief asks to choose one or more communities and justify the choice. The app seeds seven, which dilutes the story. Suggested:
- **Primary: international students and new arrivals in Oulu.** The data is Oulu, the universities are a natural payer, and the arrival sequence and student situation already exist.
- **Second: seasonal workers in Lapland.** A strong story for short-life-cycle reach, but it needs Kaleva's `pohjois-suomi` feed and a messaging channel to be credible.

## What to do before submission, in order of impact

1. **Feed members' questions and tips into the news editor's ranking,** so the community decides coverage visibly.
2. **Give the explainer the reviewed context library and glossary,** with the background shown separately on the card.
3. **Add Kaleva's local feeds** (`oulun-seutu`, `pohjois-pohjanmaa`, and `pohjois-suomi` for Lapland) and use a working AI model for the demo.
4. **Run a reliability check script** (fact-check pass rate over the stories so far) and put the number on a slide.
5. **Demo one correction** and one community note from start to finish.
6. **Pitch slides:** the community choice and why, the payers and independence, and the cost of one language.
