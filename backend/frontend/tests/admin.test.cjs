// Run with: node --test frontend/tests/admin.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function workspace() {
  const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
  const elements = new Map([...html.matchAll(/\bid="([^"]+)"/g)].map((m) => [m[1], {
    hidden: false, innerHTML: '', textContent: '', value: '', dataset: {}, attributes: {}, style: {},
    classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
    setAttribute(k, v) { this.attributes[k] = v; }, removeAttribute(k) { delete this.attributes[k]; },
    querySelectorAll() { return []; }, focus() { this.focused = true; },
    addEventListener(name, cb) { this[name] = cb; },
    showModal() { this.open = true; }, close(value = '') { this.open = false; this.returnValue = value; this.closeEvent?.(); },
  }]));
  const classes = new Set();
  const body = { classList: {
    toggle(name, value) { if (value ?? !classes.has(name)) classes.add(name); else classes.delete(name); },
    contains(name) { return classes.has(name); }, remove(name) { classes.delete(name); },
  }};
  const events = {};
  const document = { body, documentElement: { dataset: {} },
    getElementById(id) { assert.ok(elements.has(id), `Missing HTML element: ${id}`); return elements.get(id); },
    querySelectorAll() { return []; }, querySelector() { return this.main ||= {}; }, addEventListener(name, callback) { events[name] = callback; },
  };
  const ctx = vm.createContext({ document, window: { matchMedia() { return { matches: false, addEventListener() {} }; }, addEventListener() {} },
    localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
    location: { hash: '', pathname: '/' }, history: {pushState() {}}, URLSearchParams, Intl, Date,
    setTimeout, clearTimeout, setInterval, clearInterval,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/newsroom/admin.js'), 'utf8'), ctx);
  return { ctx, document, elements, events, run: (code) => vm.runInContext(code, ctx) };
}

test('logged-out startup, theme selection and drawer state use existing HTML elements', () => {
  const w = workspace();
  assert.equal(w.elements.get('login').hidden, false);
  w.elements.get('theme').value = 'dark';
  w.elements.get('theme').onchange();
  assert.equal(w.document.documentElement.dataset.theme, 'dark');
  w.run('setMenu(true)');
  assert.equal(w.elements.get('openMenu').attributes['aria-expanded'], 'true');
  assert.equal(w.document.main.inert, true);
  w.run('setMenu(false)');
  assert.equal(w.document.main.inert, false);
});

test('confirmation dialog resolves cancellation and a submitted reason', async () => {
  const w = workspace();
  const dialog = w.elements.get('actionDialog');
  dialog.addEventListener = (_, cb) => { dialog.closeEvent = cb; };
  const cancel = w.run('askDecision({title:"Reject story?",description:"Saved in record",input:true})');
  assert.equal(w.elements.get('dialogComment').required, true);
  w.elements.get('dialogCancel').onclick();
  assert.equal(await cancel, null);
  const submit = w.run('askDecision({title:"Request changes",description:"Saved",input:true})');
  w.elements.get('dialogComment').value = '  Please check the source.  ';
  w.elements.get('actionForm').onsubmit({ preventDefault() {} });
  assert.equal(await submit, 'Please check the source.');
});

test('shift rendering escapes source content and follows the merged pipeline', () => {
  const w = workspace();
  w.ctx.shift = { id: 3, status: 'succeeded', max_stories: 1, desks: [],
    counts: { ready: 0, needs_review: 1, published: 0 }, state: {},
    stories: [{ rank: 1, title: '<script>bad()</script>', headline: '', url: 'https://example.com',
      section: 'Kaleva', languages: ['fi'], stage: 'done', verdict: 'needs_review',
      reasons: [{ blocking: true, text: '<img src=x>' }], pick_reasons: [], jev_score: .8 }],
  };
  w.run('renderRun(shift)');
  const output = w.elements.get('stories').innerHTML;
  assert.ok(output.includes('&lt;script&gt;'));
  assert.ok(output.includes('&lt;img src=x&gt;'));
  assert.equal((output.match(/title="(?:explainer|translator|fact checker|standards|copy desk)"/g) || []).length, 5);
  assert.ok(!output.includes('reporter'));
  assert.ok(output.includes('href="#queue"'));
  assert.equal(w.elements.get('sendAll').disabled, true);
});

test('recent shifts expose keyboard-operable links and static markup has separate assets', () => {
  const w = workspace();
  w.ctx.runs = [{ id: 2, status: 'failed', counts: { stories: 1, ready: 0, needs_review: 1 } }];
  assert.ok(w.run('runsTable(runs,true)').includes('<button class="run-link"'));
  const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
  assert.ok(!html.includes('<style>'));
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('/static/newsroom/admin.css'));
  assert.ok(html.includes('/static/newsroom/admin.js'));
});

test('settings show current values, credential presence and escaped model metadata', () => {
  const w = workspace();
  w.ctx.dashboard = {
    schedule: { enabled: true, every_minutes: 120, max_stories_per_run: 4 },
    llm: [{agent:'explainer',spec:'ollama:granite4.1:3b',base_url:'https://example.com/<script>',stub_reason:''}],
    communities: [{name:'Oulu'}],
    settings: { source:{name:'Kaleva',url:'https://example.com/rss',max_entries:25,candidate_hours:48,max_candidates:120},
      credentials:{groq:true,openai:false},shared_model_key_configured:false,timezone:'Europe/Helsinki',
      confidence_threshold:0.7,tasks_eager:false,languages:['fi','uk','ar'],
      ranking:{jev_configured:true,feed_ranker:'jev',model:'jev-latest',top_k:30,weight:0.6,timeout_seconds:2,cache_seconds:21600}},
  };
  w.run('S.dash = dashboard; renderSettings()');
  const html = w.elements.get('settingsContent').innerHTML;
  assert.ok(html.includes('Every 120 minutes'));
  assert.ok(html.includes('granite4.1:3b'));
  assert.ok(html.includes('Ukrainian'));
  assert.ok(html.includes('60%'));
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('<script>'));
  w.run('S.dash = null; renderSettings()');
  assert.ok(w.elements.get('settingsContent').innerHTML.includes('Settings are unavailable'));
});

test('sidebar and review-tab counts clear at zero and ignore older refresh responses', async () => {
  const w = workspace();
  const pending = [];
  w.ctx.fetch = () => new Promise((resolve) => pending.push(resolve));
  w.run('S.token = "test-token"');
  const payload = (stories, translations) => ({counts:{editor_tasks:stories,translation_tasks:translations,flagged_posts:0},
    running:[],schedule:{enabled:true,every_minutes:120,max_stories_per_run:4}});
  const respond = (resolve, data) => resolve({status:200,ok:true,text:async()=>JSON.stringify(data)});
  const older = w.run('loadDashboard()');
  const newer = w.run('loadDashboard()');
  respond(pending[1], payload(0, 2));
  await newer;
  assert.equal(w.elements.get('b-queue').textContent, 2);
  assert.ok('data-zero' in w.elements.get('qStoriesCount').attributes);
  assert.equal(w.elements.get('qTranslationsCount').textContent, 2);
  assert.equal(w.elements.get('b-queue').title, '0 story reviews · 2 translation reviews');
  respond(pending[0], payload(9, 9));
  await older;
  assert.equal(w.elements.get('b-queue').textContent, 2);
  const cleared = w.run('loadDashboard()');
  respond(pending[2], payload(0, 0));
  await cleared;
  for (const id of ['b-queue','b-mod','b-run','qStoriesCount','qTranslationsCount','qAllCount']) {
    assert.equal(w.elements.get(id).textContent, '');
    assert.ok('data-zero' in w.elements.get(id).attributes);
  }
});

test('approving a task refreshes both badges and the queue immediately', async () => {
  const w = workspace();
  const calls = [];
  w.ctx.fetch = async (url) => {
    calls.push(url);
    let data = {};
    if (url.includes('/dashboard/')) data = {counts:{editor_tasks:0,translation_tasks:0,flagged_posts:0},running:[],schedule:{enabled:true,every_minutes:120,max_stories_per_run:4}};
    else if (url.includes('/editorial/tasks/?')) data = {results:[]};
    return {status:200,ok:true,text:async()=>JSON.stringify(data)};
  };
  w.run('S.token = "test-token"');
  w.ctx.button = {dataset:{do:'approve'},closest:()=>({dataset:{id:'12'},querySelectorAll:()=>[],
    querySelector:()=>({classList:{contains:()=>false}})})};
  try {
    await w.run('taskAction(button)');
    assert.ok(calls.includes('/api/editorial/tasks/12/approve/'));
    assert.ok(calls.includes('/api/agents/dashboard/'));
    assert.ok(calls.some((url)=>url.includes('/api/editorial/tasks/?')));
    assert.ok('data-zero' in w.elements.get('b-queue').attributes);
    assert.ok(w.elements.get('queue').innerHTML.includes('queue is empty'));
  } finally { w.run('clearTimeout(toast.t)'); }
});

test('empty shifts distinguish a successful RSS check from a fetch failure', () => {
  const w = workspace();
  w.ctx.shift = {id:11,status:'succeeded',max_stories:4,desks:[],stories:[],
    counts:{ready:0,needs_review:0,published:0},
    state:{wire:{fetched:25,new:0,candidates:0,errors:[],excluded_count:3,excluded:[]}}};
  w.run('renderRun(shift)');
  assert.ok(w.elements.get('stories').innerHTML.includes('RSS checked: 25 items read, 0 new or changed'));
  assert.ok(w.elements.get('stories').innerHTML.includes('No eligible uncovered stories remain'));
  w.run('shift.state.wire.errors = ["ConnectionError"]; shift.state.wire.fetched = 0; renderRun(shift)');
  assert.ok(w.elements.get('stories').innerHTML.includes('feed could not be fetched'));
  assert.ok(!w.elements.get('stories').innerHTML.includes('RSS checked:'));
});

test('Run opens the live view before dashboard checks and shows a fast shift completing', async () => {
  const w = workspace();
  const calls = [];
  let finishStart, finishDashboard;
  w.ctx.fetch = (url, options) => {
    calls.push([url,options.method]);
    const response = (data) => ({status:200,ok:true,text:async()=>JSON.stringify(data)});
    if (url === '/api/agents/runs/' && options.method === 'POST') return new Promise((resolve)=>{finishStart=()=>resolve(response({id:12,status:'queued'}));});
    if (url === '/api/agents/runs/') return Promise.resolve(response([{id:12,status:'succeeded'}]));
    if (url === '/api/agents/runs/12/') return Promise.resolve(response({id:12,status:'succeeded',max_stories:4,stories:[],desks:[],counts:{ready:0,needs_review:0,published:0},state:{wire:{fetched:25,new:0,candidates:0,errors:[],excluded_count:0}}}));
    if (url === '/api/agents/dashboard/') return new Promise((resolve)=>{finishDashboard=()=>resolve(response({counts:{editor_tasks:0,translation_tasks:0,flagged_posts:0},running:[],schedule:{enabled:true,every_minutes:120,max_stories_per_run:4}}));});
    throw new Error(`Unexpected request ${url}`);
  };
  w.run('S.token="test-token"');
  const started = w.run('runNow(4)');
  await new Promise(setImmediate);
  assert.equal(w.run('S.view'), 'newsroom');
  assert.ok(w.elements.get('desks').innerHTML.includes('Starting a shift'));
  assert.equal(w.elements.get('nrRun').disabled, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][1], 'POST');
  await w.run('runNow(4)'); // repeated clicks must not create another shift
  assert.equal(calls.length, 1);
  finishStart();
  await new Promise(setImmediate);
  assert.ok(w.elements.get('nrState').innerHTML.includes('succeeded'));
  assert.ok(w.elements.get('stories').innerHTML.includes('RSS checked: 25'));
  // The completed live view is visible even while the dashboard request is waiting.
  assert.ok(finishDashboard);
  finishDashboard();
  await started;
  assert.equal(w.elements.get('nrRun').disabled, false);
  w.run('clearTimeout(toast.t); clearTimeout(nrPoll)');
});

test('returning to the tab resumes polling and displays the current active desk', async () => {
  const w = workspace();
  const calls = [];
  w.ctx.fetch = async (url) => {
    calls.push(url);
    const data = url.endsWith('/runs/') ? [{id:8,status:'running'}]
      : {id:8,status:'running',max_stories:4,stories:[],counts:{ready:0,needs_review:0,published:0},state:{},
         desks:[{key:'wire',label:'Wire desk',status:'active',does:'Fetch RSS',who:'Kaleva',done:0,total:1}]};
    return {status:200,ok:true,text:async()=>JSON.stringify(data)};
  };
  w.run('S.token="test-token"; S.view="newsroom"; S.nrLive=true');
  w.document.hidden = false;
  w.events.visibilitychange();
  await new Promise(setImmediate);
  assert.ok(calls.includes('/api/agents/runs/8/'));
  assert.ok(w.elements.get('desks').innerHTML.includes('Working now'));
  assert.ok(w.elements.get('desks').innerHTML.includes('Wire desk'));
  assert.ok(w.run('Boolean(nrPoll)'));
  w.document.hidden = true;
  w.events.visibilitychange();
  w.run('clearTimeout(nrPoll)');
});

test('a transient progress fetch failure shows an error and schedules another poll', async () => {
  const w = workspace();
  w.ctx.fetch = async () => { throw new Error('Temporary network failure'); };
  w.run('S.token="test-token"; S.view="newsroom"; S.nrLive=true');
  try {
    await w.run('pollNewsroom()');
    assert.equal(w.elements.get('pageError').hidden, false);
    assert.equal(w.elements.get('pageErrorText').textContent, 'Temporary network failure');
    assert.ok(w.run('Boolean(nrPoll)'));
  } finally { w.run('clearTimeout(nrPoll)'); }
});
