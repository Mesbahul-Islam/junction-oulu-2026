const API = "/api";
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const results = (d) => (Array.isArray(d) ? d : d?.results ?? []);
const LANG = { fi: "Finnish", en: "English", sv: "Swedish", uk: "Ukrainian", ru: "Russian", ar: "Arabic", so: "Somali", et: "Estonian", se: "Northern Sámi", smn: "Inari Sámi", sms: "Skolt Sámi" };
const lang = (c) => LANG[c] || c;
const S = { token: stored("admin-token"), me: null, view: "overview", dash: null, readers: [], picked: [] };

function toast(msg) { const t = $("toast"); t.textContent = msg; t.style.display = "block"; clearTimeout(toast.t); toast.t = setTimeout(() => (t.style.display = "none"), 3800); }
function ago(iso) {
  if (!iso) return "–";
  const s = (Date.now() - new Date(iso)) / 1000, f = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [u, n] of [["day", 86400], ["hour", 3600], ["minute", 60]]) if (Math.abs(s) >= n) return f.format(-Math.round(s / n), u);
  return "just now";
}
const clock = (d) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
async function api(path, { method = "GET", body } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (S.token) headers.Authorization = "Bearer " + S.token;
  const res = await fetch(API + path, { cache: "no-store", method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const text = await res.text(), data = text ? JSON.parse(text) : null;
  if (res.status === 401) { logout(); throw new Error("Please log in again."); }
  if (!res.ok) throw new Error(data?.detail || (Array.isArray(data) ? data[0] : data && Object.values(data).flat()[0]) || res.statusText);
  return data;
}

// ---------- auth ----------
$("loginForm").onsubmit = async (e) => {
  e.preventDefault();
  try {
    S.token = (await api("/auth/token/", { method: "POST", body: { email: $("email").value, password: $("password").value } })).access;
    localStorage.setItem("admin-token", S.token);
    await start();
  } catch (err) { $("loginError").hidden = false; $("loginError").textContent = err.message; }
};
function logout() { $("bootState").hidden = true; clearInterval(refresher); clearTimeout(nrPoll); setMenu(false); S.token = null; localStorage.removeItem("admin-token"); $("app").hidden = true; $("login").hidden = false; }
$("logout").onclick = (e) => { e.preventDefault(); logout(); };

let refresher;
async function start() {
  try { S.me = await api("/accounts/me/"); } catch { return logout(); }
  if (!S.me.is_staff) { logout(); $("loginError").hidden = false; $("loginError").textContent = "This account isn't staff. Use an editor or admin account."; return; }
  $("bootState").hidden = true; $("login").hidden = true; $("app").hidden = false;
  $("who").textContent = S.me.email;
  try { await loadDashboard(); } catch (e) { pageError(e); }
  show(location.hash.slice(1) || "overview");
  clearInterval(refresher);
  refresher = setInterval(refreshDashboard, 30000);
}

// ---------- navigation ----------
document.querySelectorAll(".nav").forEach((b) => (b.onclick = () => { location.hash = b.dataset.view; }));
window.addEventListener("hashchange", () => show(location.hash.slice(1)));
async function show(view, { load = true } = {}) {
  if (!$("v-" + view)) view = "overview";
  if (!S.token) return;
  S.view = view;
  clearTimeout(nrPoll);
  newsroomRequest++;
  const fromDrawer = document.body.classList.contains("menu-open");
  setMenu(false);
  if (fromDrawer) $("main").focus();
  $("pageError").hidden = true;
  document.querySelectorAll(".nav").forEach((b) => {
    b.classList.toggle("on", b.dataset.view === view);
    if (b.dataset.view === view) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  document.querySelectorAll("section.view").forEach((section) => section.classList.toggle("on", section.id === "v-" + view));
  $("currentView").textContent = $("title-" + view).textContent;
  document.title = $("currentView").textContent + " · Kalevalo Admin";
  if (!load) return;
  try {
    await ({ overview: renderOverview, queue: loadQueue, moderation: loadModeration, newsroom: pollNewsroom, compare: loadReaders, settings: loadSettings }[view])();
  } catch (e) { pageError(e); }
}

// ---------- dashboard data ----------
let dashboardRequest = 0;
async function loadDashboard() {
  const request = ++dashboardRequest;
  const data = await api("/agents/dashboard/");
  if (request !== dashboardRequest || !S.token) return;
  S.dash = data;
  renderCities();
  $("pageError").hidden = true;
  $("lastUpdated").textContent = "Updated " + clock(new Date());
  $("ovRun").disabled = $("nrRun").disabled = Boolean(S.starting || S.dash.running.length);
  const c = S.dash.counts;
  const badge = (id, n) => { $(id).textContent = n || ""; n ? $(id).removeAttribute("data-zero") : $(id).setAttribute("data-zero", ""); };
  const reviews = c.editor_tasks + c.translation_tasks;
  badge("b-queue", reviews); badge("b-mod", c.flagged_posts); badge("b-run", S.dash.running.length);
  badge("qStoriesCount", c.editor_tasks); badge("qTranslationsCount", c.translation_tasks); badge("qAllCount", reviews);
  $("b-queue").title = `${c.editor_tasks} story reviews · ${c.translation_tasks} translation reviews`;
  $("b-queue").setAttribute("aria-label", $("b-queue").title);
  const sch = S.dash.schedule, next = sch.next_run_at ? new Date(sch.next_run_at) : null;
  const txt = sch.enabled === false ? "Automatic shifts are paused. You can still start a shift manually."
    : `${sch.every_minutes ? `Fetches the Kaleva RSS feed every ${sch.every_minutes} minutes` : `Scheduled: ${sch.description}`} and covers up to ${sch.max_stories_per_run} stories. ` +
      (next ? (next > new Date() ? `Next run at ${clock(next)}.` : "Next run due now.") : "Waiting for the next scheduled dispatch.");
  $("schedText").textContent = txt; $("nrSched").textContent = txt;
}

function renderOverview() {
  const d = S.dash; if (!d) return;
  const c = d.counts;
  const card = (v, l, go, cls = "") => `<button class="stat ${cls}" data-go="${go}"><span class="v">${v}</span><span class="l">${l}</span></button>`;
  $("stats").innerHTML = [
    card(c.editor_tasks, "Stories to review", "queue", c.editor_tasks ? "warn" : ""),
    card(c.translation_tasks, "Translations to review", "queue"),
    card(c.checklist_pending, "Checklist items to confirm", "queue", c.checklist_pending ? "warn" : ""),
    card(c.flagged_posts, "Reported community posts", "moderation", c.flagged_posts ? "bad" : ""),
    card(c.published_24h, "Published in 24 h", "compare"),
    card(`${c.runs_24h}${c.failed_runs_24h ? ` <span class="small danger-text">${c.failed_runs_24h} failed</span>` : ""}`, "Newsroom runs in 24 h", "newsroom"),
  ].join("");
  $("stats").querySelectorAll("[data-go]").forEach((el) => (el.onclick = () => (location.hash = el.dataset.go)));
  $("schedState").innerHTML = d.schedule.enabled === false ? `<span class="pill">Schedule paused</span>` : d.running.length ? `<span class="pill run">Running now</span>` : `<span class="pill ok">Idle</span>`;
  const modelLabels = { reporter: "Reporter (brief)", explainer: "Explainer (what it means for you)", translator: "Translation" };
  $("models").innerHTML = d.llm.map((m) => `<div class="model-row"><div><b>${esc(modelLabels[m.agent] || m.agent)}</b><div class="model-spec">${esc(m.spec)}</div></div>
    <span class="pill ${m.stub_reason ? "bad" : "ok"}">${m.stub_reason ? "Unavailable" : "Configured"}</span>
    ${m.stub_reason ? `<p class="small danger-text">${esc(m.stub_reason)}</p>` : ""}</div>`).join("");
  return api("/agents/runs/").then((r) => {
    $("ovRuns").innerHTML = runsTable(results(r).slice(0, 5), true);
    $("ovRuns").querySelectorAll("[data-run]").forEach((tr) => (tr.onclick = () => { S.nrRun = tr.dataset.run; location.hash = "newsroom"; }));
  });
}

// ---------- read-only settings ----------
async function loadSettings() {
  $("settingsContent").innerHTML = '<div class="empty" role="status">Loading settings…</div>';
  await loadDashboard();
  renderSettings();
}
function renderSettings() {
  const d = S.dash;
  if (!d?.settings) {
    $("settingsContent").innerHTML = '<div class="card empty">Settings are unavailable. Refresh to try again.</div>';
    return;
  }
  const cfg = d.settings, sch = d.schedule, source = cfg.source, ranking = cfg.ranking;
  const row = (label, value) => `<div class="setting-row"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`;
  const group = (title, intro, content) => `<section class="card settings-group"><h2>${title}</h2><p class="small muted">${intro}</p><dl>${content}</dl></section>`;
  const date = (value) => value ? new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short", timeZone: cfg.timezone }) : "Not available yet";
  const modelLabels = { reporter: "Reporter (brief)", explainer: "Explainer (what it means for you)", translator: "Translation" };
  const models = d.llm.map((m) => row(modelLabels[m.agent] || m.agent, m.spec)
    + row("Endpoint", m.base_url || "Provider default")
    + row("Configuration", m.stub_reason || "Configured; availability is not a quality assessment")).join("");
  const configured = Object.entries(cfg.credentials).filter(([, present]) => present).map(([provider]) => provider);
  $("settingsContent").innerHTML =
    group("Automatic fetching", "The current scheduler configuration; fetching runs as part of a newsroom shift.",
      row("Automatic shifts", sch.enabled ? "Enabled" : "Paused or not registered")
      + row("Frequency", sch.every_minutes ? `Every ${sch.every_minutes} minutes` : sch.description)
      + row("Stories per shift", sch.max_stories_per_run)
      + row("Last scheduled dispatch", date(sch.last_dispatched_at))
      + row("Next scheduled dispatch", sch.enabled ? date(sch.next_run_at) : "Paused")
      + row("Timezone", cfg.timezone)
      + row("Execution", cfg.tasks_eager ? "Inline tasks (no background queue)" : "Background worker"))
    + group("AI models", "Resolved model and endpoint for each newsroom role. API key values are never returned here.", models
      + row("Provider-specific credentials", configured.join(", ") || "None configured")
      + row("Shared model credential", cfg.shared_model_key_configured ? "Configured (provider not identified)" : "Not configured"))
    + group("Source and deduplication", "The newsroom currently uses one fixed Kaleva feed.",
      row("Source", source.name) + row("RSS endpoint", source.url)
      + row("Entries checked per fetch", source.max_entries)
      + row("Candidate window", `${source.candidate_hours} hours since ingestion`)
      + row("Maximum candidates", source.max_candidates)
      + row("Duplicate handling", "Same title + body hash is skipped; changed content at the same URL creates a source version."))
    + group("Jev and personalization", "Community selection and each reader’s feed use separate relevance judgments.",
      row("Jev credential", ranking.jev_configured ? "Configured" : "Missing; heuristic ranking is used")
      + row("Personal feed ranker", ranking.feed_ranker === "jev" && ranking.jev_configured ? "Jev + heuristic" : "Heuristic")
      + row("Jev model", ranking.model)
      + row("Personal feed shortlist", `${ranking.top_k} stories`)
      + row("Jev share of blended score", `${Math.round(ranking.weight * 100)}%`)
      + row("Request timeout", `${ranking.timeout_seconds} seconds`)
      + row("Score cache", `${ranking.cache_seconds / 3600} hours`))
    + group("Community and languages", "Community languages plus the preferred languages of its members.",
      row("Community", d.communities.map((c) => c.name).join(", ") || "No active community")
      + row("Target languages", cfg.languages.map(lang).join(", ") || "None configured")
      + row("Sámi", "Human translation only; excluded from machine translation"))
    + group("Review and publication", "These rules explain the current workflow; they are not editable from this tab.",
      row("Before publication", "A human must approve publication")
      + row("Normal review queue", "Editor approval plus a reviewer for each translated language")
      + row("Ready-to-send action", "Currently approves all open tasks and non-Sámi versions under the staff member who sends")
      + row("Confidence escalation threshold", cfg.confidence_threshold)
      + row("Fact checking", "Number consistency checks; not comprehensive claim verification"));
}
$("refreshSettings").onclick = () => loadSettings().catch(pageError);

// ---------- cities ----------
const num = (n) => (n == null ? "–" : Number(n).toLocaleString("en"));
function renderCities() {
  const cities = S.dash?.communities || [];
  for (const id of ["ovCity", "nrCity"]) {
    const sel = $(id), keep = sel.value;
    sel.innerHTML = cities.map((c) => `<option value="${esc(c.slug)}">${esc(c.name)}</option>`).join("") || "<option value=''>No cities</option>";
    if (cities.some((c) => c.slug === keep)) sel.value = keep;
  }
  $("cities").innerHTML = !cities.length ? '<div class="empty">No cities yet. Add one to start a shift.</div>'
    : `<table><tr><th scope="col">City</th><th scope="col">Residents</th><th scope="col">Foreign-language speakers</th><th scope="col">Largest languages</th><th scope="col">Members</th><th scope="col">Last shift</th></tr>
      ${cities.map((c) => `<tr><td><b>${esc(c.name)}</b></td><td>${num(c.facts.population)}</td>
        <td>${c.facts.share_foreign_language_speakers_pct == null ? "–" : esc(c.facts.share_foreign_language_speakers_pct) + " %"}</td>
        <td>${esc((c.facts.largest_foreign_languages || []).slice(0, 3).join(", ") || "–")}</td>
        <td>${num(c.member_count)}</td><td>${c.last_run_at ? ago(c.last_run_at) : "Never"}</td></tr>`).join("")}</table>
      <p class="small muted">${esc(cities[0]?.facts?.source || "Statistics Finland")}. Residents with a municipality of residence only.</p>`;
  loadMunicipalities();
}
let municipalities;
async function loadMunicipalities() {
  municipalities = municipalities || await api("/accounts/municipalities/");
  const covered = new Set((S.dash?.communities || []).map((c) => c.municipality_code));
  const keep = $("addCity").value;
  $("addCity").innerHTML = '<option value="">Add a city…</option>' + municipalities.filter((m) => !covered.has(m.code))
    .map((m) => `<option value="${m.code}">${esc(m.name)}</option>`).join("");
  $("addCity").value = covered.has(keep) ? "" : keep;
  $("addCityBtn").disabled = !$("addCity").value;
}
$("addCity").onchange = () => { $("addCityBtn").disabled = !$("addCity").value; };
$("addCityBtn").onclick = async () => {
  const code = $("addCity").value; if (!code) return;
  $("addCityBtn").disabled = true;
  try {
    const city = await api("/agents/cities/", { method: "POST", body: { municipality_code: code } });
    $("addCity").value = "";
    await loadDashboard();
    $("ovCity").value = $("nrCity").value = city.slug;
    toast(`${city.name} added. Start a shift to write its first stories.`);
  } catch (e) { toast(e.message); $("addCityBtn").disabled = false; }
};

// ---------- newsroom ----------
function runsTable(runs, clickable) {
  if (!runs.length) return `<div class="empty">No runs yet.</div>`;
  const badge = (s) => `<span class="pill ${s === "succeeded" ? "ok" : s === "failed" ? "bad" : "run"}">${s}</span>`;
  const dur = (r) => (r.started_at && r.finished_at ? Math.round((new Date(r.finished_at) - new Date(r.started_at)) / 1000) + " s" : "–");
  return `<table><tr><th scope="col">Run</th><th scope="col">City</th><th scope="col">Status</th><th scope="col">Stories</th><th scope="col">Ready</th><th scope="col">Needs review</th><th scope="col">Started</th><th scope="col">Took</th></tr>
    ${runs.map((r) => `<tr class="${clickable ? "click" : ""}" ><td>${clickable ? `<button class="run-link" data-run="${r.id}" aria-label="Open shift ${r.id}">#${r.id}</button>` : `#${r.id}`}</td><td>${esc(r.community_name)}</td><td>${badge(r.status)}</td>
      <td>${r.counts.stories}</td><td>${r.counts.ready}</td><td>${r.counts.needs_review}</td><td>${ago(r.started_at || r.created_at)}</td><td>${dur(r)}</td></tr>`).join("")}</table>`;
}

const STORY_DESKS = ["reporter", "explainer", "translator", "fact_checker", "standards", "copy_desk"];
let nrPoll;
let newsroomRequest = 0;
async function loadNewsroom() {
  clearTimeout(nrPoll);
  const request = ++newsroomRequest;
  const runs = results(await api("/agents/runs/"));
  if (request !== newsroomRequest || S.view !== "newsroom") return;
  $("nrPick").innerHTML = runs.slice(0, 30).map((r) => `<option value="${r.id}">Run #${r.id} · ${esc(r.community_name)} · ${esc(r.status)} · ${ago(r.created_at)}</option>`).join("");
  if (!runs.length) {
    $("nrPick").innerHTML = '<option>No shifts yet</option>';
    $("nrTitle").textContent = "Newsroom workflow";
    $("nrState").textContent = "";
    $("desks").innerHTML = '<div class="empty">No shifts yet. Start a shift to follow the work.</div>';
    $("stories").innerHTML = '<div class="empty">Stories will appear here after selection.</div>';
    $("sendAll").disabled = true;
    return;
  }
  const id = S.nrRun && runs.some((r) => String(r.id) === String(S.nrRun)) ? S.nrRun : runs[0].id;
  $("nrPick").value = id;
  const r = await api(`/agents/runs/${id}/`);
  if (request !== newsroomRequest || S.view !== "newsroom") return;
  const wasLive = S.nrLive;
  S.nrLive = ["queued", "running"].includes(r.status);
  renderRun(r);
  if (wasLive && !S.nrLive) await loadDashboard();
  if (["queued", "running"].includes(r.status) && S.view === "newsroom" && !document.hidden) nrPoll = setTimeout(pollNewsroom, 2000);
}
async function pollNewsroom() {
  try { await loadNewsroom(); }
  catch (error) {
    pageError(error);
    if (S.nrLive && S.view === "newsroom" && !document.hidden) nrPoll = setTimeout(pollNewsroom, 2000);
  }
}
$("nrPick").onchange = () => { S.nrRun = $("nrPick").value; pollNewsroom(); };
document.addEventListener("visibilitychange", () => {
  if (document.hidden) clearTimeout(nrPoll);
  else if (S.token && S.view === "newsroom" && !S.starting) pollNewsroom();
});

function renderRun(r) {
  const live = ["queued", "running"].includes(r.status);
  const w = r.state?.wire, ne = r.state?.news_editor;
  const emptyMessage = live ? "The wire desk and news editor are choosing stories…"
    : w?.errors?.length ? "The feed could not be fetched, and no eligible stored stories were selected. See the wire desk report."
    : w ? `RSS checked: ${w.fetched} items read, ${w.new} new or changed. No eligible uncovered stories remain.`
    : "No stories in this run.";
  $("nrTitle").textContent = `Run #${r.id} · ${r.community_name} · up to ${r.max_stories} stories`;
  $("nrState").innerHTML = `<span class="pill ${r.status === "failed" ? "bad" : r.status === "succeeded" ? "ok" : "run"}">${esc(r.status)}${r.status === "queued" ? " (waiting for the worker)" : ""}</span>`
    + (r.started_at ? ` <span class="small muted">${live ? "started" : "ran"} ${ago(r.started_at)}${r.finished_at ? `, took ${Math.round((new Date(r.finished_at) - new Date(r.started_at)) / 1000)} s` : ""}</span>` : "");
  const st = { done: "Done", active: "Working now", waiting: "Waiting", failed: "Failed", skipped: "Skipped · no stories" };
  const desk = (d) => `<div class="desk ${d.status}" title="${esc(d.does)}"><div class="st">${st[d.status]}</div><div class="nm">${esc(d.label)}</div><div class="who">${esc(d.who)}</div>
      <div class="pr">${d.total > 1 || !["wire", "news_editor", "community_vote"].includes(d.key) ? `${d.done} of ${d.total} stories` : ""}${d.seconds ? ` <span class="muted">· ${d.seconds} s</span>` : ""}</div>
      ${d.working_on ? `<div class="pr"><b>#${d.working_on.rank}</b> ${esc(d.working_on.title.slice(0, 50))}…${d.working_on.detail ? `<div class="muted">${esc(d.working_on.detail)}</div>` : ""}</div>` : ""}</div>`;
  const c = r.counts;
  const human = `<div class="desk human"><div class="st">${c.ready + c.needs_review ? `${c.ready + c.needs_review} waiting` : "Nothing waiting"}</div><div class="nm">Editors (people)</div>
      <div class="who">Send ready stories, review the rest</div><div class="pr">${c.ready} ready · ${c.needs_review} need review · ${c.published} published</div></div>`;
  $("desks").innerHTML = r.desks.map(desk).join('<span class="desk-arrow">→</span>') + '<span class="desk-arrow">→</span>' + human
    + (r.error ? `<div class="flag bad full-width">${esc(r.error)}</div>` : "");

  // Stories
  const stageBar = (s) => STORY_DESKS.map((k) => {
    const i = STORY_DESKS.indexOf(k), at = STORY_DESKS.indexOf(s.stage);
    const cls = s.stage === "failed" ? "bad" : s.stage === "done" || i < at ? "done" : i === at ? "now" : "";
    return `<i class="${cls}" title="${esc(k.replace("_", " "))}"></i>`;
  }).join("");
  const stageText = (s) => s.stage === "done" ? "With the editors" : s.stage === "failed" ? "Failed" : s.stage === "picked" ? "Waiting for the brief"
    : `${({ reporter: "Reporter", explainer: "Explainer" }[s.stage] || s.stage.replace("_", " "))}${s.detail ? ": " + s.detail : ""}…`;
  const verdict = (s) => {
    if (s.published_at) return `<span class="verdict published">Published</span>`;
    if (!s.verdict) return s.error ? `<span class="pill bad">failed</span><div class="small danger-text">${esc(s.error.slice(0, 160))}</div>` : `<span class="muted small">being written</span>`;
    const block = s.reasons.filter((x) => x.blocking), notes = s.reasons.filter((x) => !x.blocking);
    return `<span class="verdict ${s.verdict}">${s.verdict === "ready" ? "Ready to send" : "Needs review"}</span>
      ${block.length || notes.length ? `<ul class="reasons">${block.map((x) => `<li>${esc(x.text)}</li>`).join("")}${notes.map((x) => `<li class="note">Note: ${esc(x.text)}</li>`).join("")}</ul>` : ""}`;
  };
  const action = (s) => s.published_at ? "" : s.verdict === "ready" ? `<button class="btn accent" data-send="${s.snippet}">Send</button>`
    : s.verdict === "needs_review" ? `<a class="btn" href="#queue">Review</a>` : "";
  $("stories").innerHTML = r.stories.length ? `<table><tr><th scope="col">#</th><th scope="col">Jev</th><th scope="col">Story</th><th scope="col">Progress</th><th scope="col">Verdict</th><th scope="col"></th></tr>
    ${r.stories.map((s) => `<tr><td>${s.rank}</td>
      <td class="score-cell"><span class="jev" style="--score-width:${Math.round(Math.max(0, Math.min(s.jev_score || 0, 2)) * 40)}px"></span> <b>${(s.jev_score ?? 0).toFixed(2)}</b>
        <div class="small muted">${s.ranked_by === "jev" ? "Jev" : "heuristic"}${s.pick_reasons.length ? ": " + esc(s.pick_reasons.join(", ")) : ""}</div></td>
      <td><div dir="auto"><b>${esc(s.headline || s.title)}</b></div><div class="small muted">${s.headline ? `Kaleva: <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title.slice(0, 80))}</a>` : `<a href="${esc(s.url)}" target="_blank" rel="noopener">source</a>`} · ${esc(s.section)}${s.languages.length ? ` · ${s.languages.length} languages` : ""}</div></td>
      <td class="stage-cell"><div class="stages">${stageBar(s)}</div><div class="small muted">${esc(stageText(s))}</div></td>
      <td class="verdict-cell">${verdict(s)}</td><td>${action(s)}</td></tr>`).join("")}</table>`
    : `<div class="empty" role="status">${esc(emptyMessage)}</div>`;
  $("stories").querySelectorAll("[data-send]").forEach((b) => (b.onclick = () => sendStories(r.id, { snippets: [Number(b.dataset.send)] })));
  $("sendAll").disabled = !c.ready;
  $("sendAll").textContent = c.ready ? `Send all ${c.ready} ready` : "Send all ready";
  $("sendAll").onclick = () => sendStories(r.id, { all_ready: true });

  // Wire desk and Jev
  $("nrWire").classList.toggle("muted", !w);
  $("nrWire").innerHTML = w ? `<p class="report-intro">${w.feeds ? w.feeds + " Kaleva feeds" : "Kaleva free-articles feed"} · ${w.fetched} articles read · <b>${w.new}</b> new · <b>${w.candidates}</b> candidates</p>
    ${w.errors.length ? `<div class="flag bad">Could not fetch: ${esc(w.errors.join(", "))}</div>` : ""}
    ${w.excluded_count ? `<div class="flag warn"><b>Not news, left out (JSN 11/16): ${w.excluded_count}</b><ul>${w.excluded.slice(0, 6).map((e) => `<li>${esc(e.type)}: ${esc(e.title)}</li>`).join("")}</ul></div>` : ""}` : "–";
  $("nrJev").classList.toggle("muted", !ne);
  const cv = r.state?.community_vote;
  $("nrJev").innerHTML = ne ? `<p class="small muted report-intro">${ne.considered} articles ranked by ${ne.ranked_by === "jev" ? "Jev" : "the heuristic (no Jev key)"}, plus members' votes from the app's "What should we cover next?"; the top ${ne.picked} were covered.</p>
    <table><tr><th scope="col"></th><th scope="col">Total</th><th scope="col">Jev</th><th scope="col">Votes</th><th scope="col">Article</th></tr>${ne.top.map((t, i) => `<tr><td class="small">${i + 1}</td><td class="small"><b>${t.score.toFixed(2)}</b></td>
      <td class="small">${t.jev != null ? t.jev.toFixed(2) : "–"}</td><td class="small">${t.votes ? `<b>${t.votes}</b>` : "–"}</td>
      <td class="small">${esc(t.title)}${i < ne.picked ? ' <span class="pill ok">covered</span>' : ""}</td></tr>`).join("")}</table>
    ${cv ? `<p class="small muted report-footer">Next shortlist posted for members: <b>${cv.open}</b> stories open for votes (${cv.added} new, titles in ${cv.title_languages.map(lang).join(", ") || "Finnish"}).</p>` : ""}` : "–";
}

async function sendStories(runId, body) {
  try {
    const res = await api(`/agents/runs/${runId}/send/`, { method: "POST", body });
    toast(res.sent.length ? `Published ${res.sent.length} ${res.sent.length === 1 ? "story" : "stories"}.` : "Nothing was published.");
    await Promise.all([loadDashboard(), loadNewsroom()]);
  } catch (e) { toast(e.message); }
}

async function runNow(max, city) {
  if (S.starting) return;
  S.starting = true;
  clearTimeout(nrPoll);
  const buttons = [$("ovRun"), $("nrRun")];
  const labels = buttons.map((button) => button.textContent);
  buttons.forEach((button) => { button.disabled = true; button.textContent = "Starting…"; });
  if (S.view !== "newsroom") history.pushState(null, "", "#newsroom");
  await show("newsroom", { load: false });
  $("nrTitle").textContent = "Starting a newsroom shift…";
  $("nrState").textContent = "Submitting request…";
  $("desks").innerHTML = '<div class="empty" role="status">Starting a shift. Waiting for the worker…</div>';
  $("stories").innerHTML = '<div class="empty">Stories will appear as the newsroom selects them.</div>';
  $("nrWire").textContent = $("nrJev").textContent = "Waiting for this shift’s report…";
  $("sendAll").disabled = true;
  try {
    const run = await api("/agents/runs/", { method: "POST", body: { max_stories: Number(max), ...(city ? { community: city } : {}) } });
    S.nrRun = run.id;
    S.nrLive = true;
    $("nrTitle").textContent = `Run #${run.id} · ${run.community_name} · waiting for the worker`;
    $("nrState").textContent = run.status;
    toast(`Run #${run.id} started.`);
    await pollNewsroom();
    if (S.nrLive) await refreshDashboard();
  } catch (error) {
    S.nrLive = false;
    $("nrTitle").textContent = "Could not start the shift";
    $("nrState").textContent = error.message;
    pageError(error);
  } finally {
    S.starting = false;
    buttons.forEach((button, index) => {
      button.textContent = labels[index];
      button.disabled = Boolean(S.nrLive);
    });
  }
}
$("ovRun").onclick = () => runNow($("ovMax").value, $("ovCity").value);
$("nrRun").onclick = () => runNow($("nrMax").value, $("nrCity").value);
$("ovCity").onchange = () => { $("nrCity").value = $("ovCity").value; };
$("nrCity").onchange = () => { $("ovCity").value = $("nrCity").value; };

// ---------- editor queue ----------
const qState = { role: "editor" };
$("qType").querySelectorAll("button").forEach((b) => (b.onclick = () => { $("qType").querySelectorAll("button").forEach((x) => (x.classList.toggle("on", x === b), x.setAttribute("aria-pressed", String(x === b)))); qState.role = b.dataset.v; loadQueue(); }));
$("qReason").onchange = loadQueue;

function flagsHtml(t) {
  const f = t.flags || {}, out = [];
  (f.sources || []).forEach((s) => out.push(`<div class="small muted">Source: <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title || s.url)}</a> · ${esc(s.publisher)}</div>`));
  (f.verification || []).filter((v) => !v.passed || v.issues.length).forEach((v) => out.push(`<div class="flag ${v.passed ? "warn" : "bad"}"><b>Fact-check ${esc(lang(v.language))}: ${v.passed ? "passed with notes" : "failed"}</b> · confidence ${v.confidence}
    <ul>${v.issues.map((i) => `<li>${esc(i.kind)}${i.value ? ` “${esc(i.value)}”` : ""}: ${esc(i.issue)}</li>`).join("")}</ul></div>`));
  if (f.standards?.failed?.length) out.push(`<div class="flag bad"><b>Standards check failed</b><ul>${f.standards.failed.map((x) => `<li>${esc(x.label)}</li>`).join("")}</ul></div>`);
  if (f.checklist?.length) out.push(`<div class="flag check"><b>Editorial checklist (JSN): confirm each before approving</b>
    ${f.checklist.map((c) => `<label class="check-row"><input type="checkbox" data-check="${esc(c.key)}" ${c.confirmed ? "checked disabled" : ""}><span>${esc(c.label)} <span class="small">(clauses ${esc(c.clauses)})${c.confirmed ? ` · confirmed by ${esc(c.confirmed_by)}` : ""}</span></span></label>`).join("")}</div>`);
  return out.join("");
}

// "What this means for you": one text per reader situation (SnippetVersion.explainer).
const SITUATIONS = [["newcomer", "Newcomer"], ["seasonal_worker", "Seasonal worker"], ["student", "Student"], ["resident", "Resident"]];
function forYouHtml(explainer) {
  const rows = SITUATIONS.filter(([k]) => (explainer || {})[k]);
  if (!rows.length) return `<div class="for-you empty small muted">No "What this means for you" text for this version.</div>`;
  return `<div class="for-you"><div class="for-you-title">What this means for you <span class="small muted">· each reader sees the one for their situation</span></div>
    <dl>${rows.map(([k, label]) => `<dt>${label}</dt><dd dir="auto">${esc(explainer[k])}</dd>`).join("")}</dl></div>`;
}

async function loadQueue() {
  const box = $("queue");
  box.innerHTML = `<div class="empty">Loading…</div>`;
  const q = new URLSearchParams({ limit: 100 });
  if (qState.role) q.set("role", qState.role);
  if ($("qReason").value) q.set("reason", $("qReason").value);
  try {
    const tasks = results(await api(`/editorial/tasks/?${q}`));
    if (!tasks.length) { box.innerHTML = `<div class="card empty">The queue is empty. New stories arrive after each newsroom run.</div>`; return; }
    box.innerHTML = tasks.map((t) => {
      const v = (t.versions || [])[0] || {};
      const editLang = t.language || "fi";
      return `<div class="card task" data-id="${t.id}">
        <div class="task-head"><b>Story #${t.snippet}</b>
          <span class="pill ${esc(t.risk_tier)}">${esc(t.risk_tier)} risk</span>
          <span class="pill">${esc(t.reason.replace(/_/g, " "))}</span>
          <span class="pill">${t.language ? "Translation: " + esc(lang(t.language)) : "Story (Finnish)"}</span>
          ${t.review_level ? `<span class="verdict ${esc(t.review_level)}">${t.review_level === "ready" ? "Ready to send" : "Needs review"}</span>` : ""}
          <span class="small muted">needs ${esc(t.required_role.replace("_", " "))} · confidence ${(t.confidence ?? 0).toFixed(2)} · ${ago(t.created_at)}</span></div>
        ${!t.language && (t.review_reasons || []).some((x) => x.blocking) ? `<div class="flag warn"><b>Why the newsroom wants a person to read this</b><ul>${t.review_reasons.filter((x) => x.blocking).map((x) => `<li>${esc(x.text)}</li>`).join("")}</ul></div>` : ""}
        ${(t.language ? t.versions : (t.versions || []).filter((x) => x.language === "fi")).map((x) => `<div class="version"><span class="pill">${esc(lang(x.language))}${x.is_machine_translated ? " · machine-translated" : ""}</span>
          <div dir="auto"><b>${esc(x.headline) || "<i>Empty: write the translation with Edit text</i>"}</b></div><div class="muted" dir="auto">${esc(x.summary)}</div>
          ${(x.key_facts || []).length ? `<ul class="small">${x.key_facts.map((k) => `<li dir="auto">${esc(k)}</li>`).join("")}</ul>` : ""}
          ${forYouHtml(x.explainer)}</div>`).join("")}
        ${!t.language && t.versions.length > 1 ? `<div class="small muted">${t.versions.length - 1} translation(s) are reviewed separately by language reviewers (Translations tab).</div>` : ""}
        ${flagsHtml(t)}
        <div class="edit-box" dir="auto">
          <label for="edit-headline-${t.id}">Headline (${esc(lang(editLang))})</label><input id="edit-headline-${t.id}" data-e="headline" value="${esc(v.headline)}" class="full-width">
          <label for="edit-summary-${t.id}">Summary</label><textarea id="edit-summary-${t.id}" data-e="summary" rows="3">${esc(v.summary)}</textarea>
          <label for="edit-facts-${t.id}">Key facts (one per line)</label><textarea id="edit-facts-${t.id}" data-e="key_facts" rows="3">${esc((v.key_facts || []).join("\n"))}</textarea>
          ${SITUATIONS.map(([k, label]) => `<label for="edit-foryou-${k}-${t.id}">What this means for you: ${label}</label><textarea id="edit-foryou-${k}-${t.id}" data-for-you="${k}" rows="2">${esc((v.explainer || {})[k] || "")}</textarea>`).join("")}
        </div>
        <div class="actions">
          <button class="btn primary" data-do="approve">Approve</button>
          <button class="btn" data-do="edit">Edit text</button>
          <button class="btn" data-do="changes">Request changes</button>
          <button class="btn danger" data-do="reject">Reject</button>
        </div></div>`;
    }).join("");
    box.querySelectorAll("[data-do]").forEach((b) => (b.onclick = () => taskAction(b)));
  } catch (e) { box.innerHTML = `<div class="card empty">${esc(e.message)}</div>`; }
}

async function taskAction(b) {
  const card = b.closest(".task"), id = card.dataset.id, act = b.dataset.do;
  const editBox = card.querySelector(".edit-box");
  try {
    if (act === "edit") { editBox.classList.toggle("on"); b.textContent = editBox.classList.contains("on") ? "Cancel edit" : "Edit text"; return; }
    if (act === "approve") {
      const open = [...card.querySelectorAll("[data-check]:not(:disabled)")];
      if (open.some((c) => !c.checked)) return toast("Tick every checklist item first: the story can't be published until an editor confirms them.");
      const body = { confirm: open.map((c) => c.dataset.check) };
      if (editBox.classList.contains("on")) {
        const val = (k) => card.querySelector(`[data-e="${k}"]`).value;
        const explainer = Object.fromEntries([...card.querySelectorAll("[data-for-you]")].map((el) => [el.dataset.forYou, el.value.trim()]).filter(([, text]) => text));
        body.edits = { headline: val("headline").trim(), summary: val("summary").trim(), key_facts: val("key_facts").split("\n").map((s) => s.trim()).filter(Boolean), explainer };
      }
      await api(`/editorial/tasks/${id}/approve/`, { method: "POST", body });
      toast("Approved.");
    } else {
      const comment = await askDecision({ title: act === "reject" ? "Reject this story?" : "Request changes", description: "Your reason will be saved for the newsroom and other reviewers.", input: true, action: act === "reject" ? "Reject story" : "Request changes" });
      if (!comment) return;
      await api(`/editorial/tasks/${id}/${act === "reject" ? "reject" : "request-changes"}/`, { method: "POST", body: { comment } });
      toast(act === "reject" ? "Rejected." : "Changes requested.");
    }
    await Promise.all([loadDashboard(), loadQueue()]);
  } catch (e) { toast(e.message); }
}

$("qBatch").onclick = async () => {
  try {
  const tasks = results(await api("/editorial/tasks/?limit=200&reason=batch_low_risk"));
  if (!tasks.length) return toast("No low-risk items waiting.");
  if (!await askDecision({ title: `Approve ${tasks.length} low-risk items?`, description: "Items with an editorial checklist are skipped. Your approvals are saved in your name.", action: "Approve batch" })) return;
  const res = await api("/editorial/tasks/batch-approve/", { method: "POST", body: { task_ids: tasks.map((t) => t.id) } });
  toast(`Approved ${res.approved.length}, skipped ${res.skipped.length}.`); await Promise.all([loadDashboard(), loadQueue()]);
  } catch (e) { toast(e.message); }
};

// ---------- moderation ----------
const mState = { status: "pending" };
$("mStatus").querySelectorAll("button").forEach((b) => (b.onclick = () => { $("mStatus").querySelectorAll("button").forEach((x) => (x.classList.toggle("on", x === b), x.setAttribute("aria-pressed", String(x === b)))); mState.status = b.dataset.v; loadModeration(); }));
async function loadPhotos(box) {
  const photos = await api("/communities/photos/");
  if (!photos.length) { box.innerHTML = `<div class="card empty">No photos waiting. Faces in new photos are blurred on upload; check them here before others see them.</div>`; return; }
  box.innerHTML = photos.map((p) => `<div class="card task" data-id="${p.id}">
    <div class="task-head"><b>${esc(p.author_name)}</b><span class="muted">in ${esc(p.community_name)} · posted ${ago(p.created_at)}</span>
      <span class="pill">${p.faces_blurred} face${p.faces_blurred === 1 ? "" : "s"} blurred</span></div>
    <img src="${esc(p.image)}" alt="Photo awaiting review" style="display:block;max-width:100%;max-height:420px;border-radius:10px;margin:0 0 8px">
    ${p.notes.length ? `<div class="flag warn"><b>Check</b><ul>${p.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></div>` : ""}
    <p style="white-space:pre-wrap;margin:0 0 8px" dir="auto">${esc(p.body)}</p>
    <p class="small muted">Approve only if every face is unrecognisable and nothing else identifies a person (name tags, number plates, home addresses).</p>
    <div class="actions"><button class="btn primary" data-photo="approve">Approve photo</button><button class="btn danger" data-photo="reject">Reject photo (keep the text)</button></div>
  </div>`).join("");
  box.querySelectorAll("[data-photo]").forEach((b) => (b.onclick = async () => {
    const id = b.closest(".task").dataset.id;
    try { await api(`/communities/photos/${id}/decide/`, { method: "POST", body: { decision: b.dataset.photo } }); toast(b.dataset.photo === "approve" ? "Photo approved." : "Photo removed."); loadModeration(); }
    catch (e) { toast(e.message); }
  }));
}

async function loadModeration() {
  const box = $("modList");
  box.innerHTML = '<div class="empty" role="status">Loading community posts…</div>';
  if (mState.status === "photos") { try { await loadPhotos(box); } catch (e) { box.innerHTML = `<div class="card empty">${esc(e.message)}</div>`; } return; }
  try {
    const posts = results(await api(`/communities/moderation/?status=${mState.status}`));
    if (!posts.length) { box.innerHTML = `<div class="card empty">${{ pending: "Nothing to moderate. Reported posts appear here.", questions: "No unanswered questions. Questions members post in Community News appear here." }[mState.status] || "Nothing here yet."}</div>`; return; }
    box.innerHTML = posts.map((p) => `<div class="card task" data-id="${p.id}">
      <div class="task-head"><b>${esc(p.author_name)}</b><span class="muted">in ${esc(p.community_name)} · posted ${ago(p.created_at)}</span>
        ${p.reports.length ? `<span class="pill bad">${p.reports.length} report${p.reports.length > 1 ? "s" : ""}</span>` : ""}</div>
      <p dir="auto" class="post-body">${esc(p.body)}</p>
      ${p.reports.length ? `<div class="flag warn"><b>Reports</b><ul>${p.reports.map((r) => `<li>${esc(r.reason)}${r.note ? `: ${esc(r.note)}` : ""} <span class="small">(${esc(r.by)}, ${ago(r.at)})</span></li>`).join("")}</ul></div>` : ""}
      ${p.moderated_at ? `<div class="small muted">${p.status === "removed" ? "Removed" : "Kept"} by ${esc(p.moderated_by_name || "–")} ${ago(p.moderated_at)}${p.moderation_note ? `: “${esc(p.moderation_note)}”` : ""}</div>` : ""}
      ${mState.status === "pending" ? `<div class="actions"><button class="btn primary" data-mod="keep">Keep (restore)</button><button class="btn danger" data-mod="remove">Remove</button></div>` : ""}
      ${mState.status === "questions" ? `<div class="actions"><label class="small muted">Answered by story # <input data-answer type="number" min="1" class="story-number"></label>
        <button class="btn primary" data-link="1">Link answer</button><span class="small muted">The post then shows "Answered by the newsroom" with a link.</span></div>` : ""}
    </div>`).join("");
    box.querySelectorAll("[data-link]").forEach((b) => (b.onclick = async () => {
      const card = b.closest(".task"), story = card.querySelector("[data-answer]").value;
      if (!story) return toast("Enter the number of the story that answers this question.");
      try { await api(`/communities/news/${card.dataset.id}/answer/`, { method: "POST", body: { snippet: Number(story) } }); toast("Answer linked."); await Promise.all([loadDashboard(), loadModeration()]); }
      catch (e) { toast(e.message); }
    }));
    box.querySelectorAll("[data-mod]").forEach((b) => (b.onclick = async () => {
      const id = b.closest(".task").dataset.id;
      const note = b.dataset.mod === "remove" ? await askDecision({ title: "Remove this post?", description: "The post stays hidden. Your moderation reason will be saved in the record.", input: true, action: "Remove post" }) : "";
      if (note === null) return;
      try { await api(`/communities/moderation/${id}/decide/`, { method: "POST", body: { decision: b.dataset.mod, note } }); toast(b.dataset.mod === "keep" ? "Restored." : "Removed."); await Promise.all([loadDashboard(), loadModeration()]); }
      catch (e) { toast(e.message); }
    }));
  } catch (e) { box.innerHTML = `<div class="card empty">${esc(e.message)}</div>`; }
}

// ---------- compare feeds ----------
const SITU = { newcomer: "newcomer", student: "student", seasonal_worker: "seasonal worker", resident: "resident" };
async function loadReaders() {
  if (!S.readers.length) S.readers = results(await api("/accounts/readers/"));
  if (!S.readersInitialized) { S.readersInitialized = true; S.picked = S.readers.filter((r) => !r.is_staff).slice(0, 2).map((r) => r.id); }
  $("readers").innerHTML = S.readers.length ? S.readers.map((r) => `<label class="reader-pick ${S.picked.includes(r.id) ? "on" : ""}">
    <input type="checkbox" value="${r.id}" ${S.picked.includes(r.id) ? "checked" : ""}>
    <span><b>${esc(r.display_name || r.email)}</b><br><span class="small muted">${esc(lang(r.preferred_language))} · ${esc(SITU[r.reader_situation] || r.reader_situation)}</span></span></label>`).join("")
    : `<span class="muted">No onboarded readers yet.</span>`;
  $("readers").querySelectorAll("input").forEach((i) => (i.onchange = () => {
    const id = Number(i.value);
    S.picked = i.checked ? [...S.picked, id].slice(-3) : S.picked.filter((x) => x !== id);
    loadReaders().catch(pageError);
  }));
  renderCompare();
}
function renderCompare() {
  const cols = $("compareCols");
  if (!S.picked.length) { cols.innerHTML = `<div class="card empty">Pick readers above.</div>`; return; }
  cols.innerHTML = S.picked.map((id) => `<div class="card" id="col-${id}"><div class="empty">Loading…</div></div>`).join("");
  const meter = (l, v, max = 1) => `<div class="meter"><span>${l}</span><i><b style="--meter-width:${Math.round(Math.max(0, Math.min(v / max, 1)) * 100)}%"></b></i><span>${Math.round(v * 100)}%</span></div>`;
  for (const id of S.picked) {
    const r = S.readers.find((x) => x.id === id);
    api(`/feed/snippets/?as_user=${id}&limit=8`).then((d) => {
      const cards = results(d);
      $(`col-${id}`).innerHTML = `<h2 class="flush">${esc(r.display_name || r.email)}</h2>
        <div class="small muted">${esc(lang(r.preferred_language))} · ${esc(SITU[r.reader_situation] || "")}${r.arrival_date ? ` · arrived ${esc(r.arrival_date)}` : ""}</div>
        <div class="row small interest-tags">${(r.profile?.interests || []).map((t) => `<span class="pill">${esc(t)}</span>`).join("")}</div>
        ${cards.length ? cards.map((c, i) => `<div class="feed-card" dir="auto">
          <div class="row small muted"><b>#${i + 1}</b><span class="pill">${esc(lang(c.language))}</span>${c.in_your_language ? "" : `<span class="pill bad">not yet in ${esc(lang(c.requested_language))}</span>`}
            <span>score ${c.ranking?.score?.toFixed(2) ?? "–"} · ${esc(c.ranking?.ranker || "")}</span></div>
          <h4>${esc(c.headline)}</h4>
          ${c.for_you ? `<div class="small muted">For you: ${esc(c.for_you.slice(0, 140))}</div>` : ""}
          ${c.ranking?.jev ? meter("Affects them", c.ranking.jev.affects_reader) + meter("Interests", c.ranking.jev.matches_interests) + meter("Action", c.ranking.jev.needs_action) : ""}
        </div>`).join("") : `<div class="empty">No published stories in their languages yet.</div>`}`;
    }).catch((e) => ($(`col-${id}`).innerHTML = `<div class="empty">${esc(e.message)}</div>`));
  }
}

// ---------- workspace controls ----------
function stored(key) { try { return localStorage.getItem(key); } catch { return null; } }
function pageError(error) {
  if (!S.token) return;
  $("pageErrorText").textContent = error.message || "Something went wrong. Try again.";
  $("pageError").hidden = false;
}
async function refreshDashboard() {
  if (!S.token) return;
  try { await loadDashboard(); if (S.view === "overview") await renderOverview(); else if (S.view === "settings") renderSettings(); }
  catch (e) { pageError(e); }
}
$("refreshDashboard").onclick = refreshDashboard;
$("retryPage").onclick = async () => { await refreshDashboard(); if (S.view !== "overview") await show(S.view); };

function setMenu(open) {
  const desktop = window.matchMedia("(min-width: 1024px)").matches;
  if (desktop) { if (open) document.body.classList.remove("sidebar-collapsed"); return; }
  document.body.classList.toggle("menu-open", open);
  $("menuBackdrop").hidden = !open;
  $("openMenu").setAttribute("aria-expanded", String(open));
  $("sidebar").setAttribute("role", open ? "dialog" : "complementary");
  if (open) {
    $("sidebar").setAttribute("aria-modal", "true");
    document.querySelector(".workspace").inert = true;
    $("closeMenu").focus();
  } else {
    $("sidebar").removeAttribute("aria-modal");
    document.querySelector(".workspace").inert = false;
  }
}
$("openMenu").onclick = () => setMenu(true);
$("closeMenu").onclick = $("menuBackdrop").onclick = () => { setMenu(false); $("openMenu").focus(); };
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.code === "Backslash" && window.matchMedia("(min-width: 1024px)").matches) {
    e.preventDefault(); document.body.classList.toggle("sidebar-collapsed");
  }
  if (!document.body.classList.contains("menu-open")) return;
  if (e.key === "Escape") { setMenu(false); $("openMenu").focus(); }
  if (e.key === "Tab") {
    const items = [...$("sidebar").querySelectorAll("a,button")];
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
});
window.matchMedia("(min-width: 1024px)").addEventListener("change", () => {
  document.body.classList.remove("menu-open");
  $("menuBackdrop").hidden = true;
  $("sidebar").removeAttribute("aria-modal");
  $("sidebar").setAttribute("role", "complementary");
  document.querySelector(".workspace").inert = false;
  $("openMenu").setAttribute("aria-expanded", "false");
});
const savedTheme = stored("newsroom-theme");
if (["light", "dark"].includes(savedTheme)) { document.documentElement.dataset.theme = savedTheme; $("theme").value = savedTheme; }
$("theme").onchange = () => {
  const theme = $("theme").value;
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("newsroom-theme", theme); } catch {}
};
function askDecision({ title, description, input = false, action = "Continue" }) {
  return new Promise((resolve) => {
    const dialog = $("actionDialog");
    $("dialogTitle").textContent = title;
    $("dialogDescription").textContent = description;
    $("dialogField").hidden = !input;
    $("dialogComment").required = input;
    $("dialogComment").value = "";
    $("dialogSubmit").textContent = action;
    dialog.returnValue = "";
    $("actionForm").onsubmit = (event) => { event.preventDefault(); dialog.close("submit"); };
    $("dialogCancel").onclick = () => dialog.close();
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "submit" ? (input ? $("dialogComment").value.trim() : true) : null), { once: true });
    dialog.showModal();
    (input ? $("dialogComment") : $("dialogCancel")).focus();
  });
}

// ---------- start ----------
if (location.hash.includes("token=")) {
  const t = new URLSearchParams(location.hash.slice(1)).get("token");
  if (t) {
    S.token = t;
    try { localStorage.setItem("admin-token", t); } catch {}
    history.replaceState(null, "", location.pathname);
  }
}
if (S.token) start(); else { $("bootState").hidden = true; $("login").hidden = false; }
