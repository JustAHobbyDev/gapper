/* Gapper pilot review app. Source text is untrusted: it only ever reaches the DOM as text nodes. */
'use strict';

const OUTCOMES = [
  ['has_candidate', 'Concrete workflow episode', 'At least one reconstructable, evidence-backed episode.'],
  ['unknown', 'Possible workflow / insufficient evidence', 'Something may be there; interpretation stays uncertain.'],
  ['no_candidate', 'No workflow opportunity observed', 'Enough text for a negative judgment in what you reviewed.'],
  ['insufficient_evidence', 'Insufficient textual evidence', 'Bodyless, marker-only or too little text to judge.']];
const SUFFICIENCY = [['sufficient', 'Sufficient'], ['needed_extra', 'Needed extra context'],
  ['still_insufficient', 'Still insufficient'], ['uncertain', 'Uncertain']];
const ROLES = [['task', 'Workflow / task'], ['pain', 'Pain'], ['burden', 'Burden'], ['workaround', 'Workaround'],
  ['ai_attempt', 'Attempted AI / tool use'], ['failure', 'Failure'], ['constraint', 'Constraint'],
  ['solution', 'Suggested solution'], ['feasibility', 'Feasibility evidence'], ['buying', 'Buying signal'],
  ['resolution', 'Resolution'], ['actor', 'Actor / role'], ['step', 'Workflow step'], ['input', 'Input / artifact'],
  ['output', 'Output / artifact'], ['system', 'System / tool']];
const BASES = [['firsthand_report', 'Firsthand report'], ['secondhand_report', 'Secondhand report'],
  ['suggestion', 'Suggestion'], ['question', 'Question'], ['hypothetical', 'Hypothetical']];
const RELATIONS = [['supports', 'Supporting'], ['contradicts', 'Contradicting'], ['corrects', 'Correcting'],
  ['supersedes', 'Superseding'], ['qualifies', 'Qualifying']];
const NEED = [['none', 'None'], ['possible', 'Possible'], ['concrete', 'Concrete'], ['unknown', 'Unknown']];
const ADOPTION = [['unknown', 'Unknown'], ['not_stated', 'Not stated'], ['attempted_failed', 'Attempted, failed'],
  ['unrealized_value', 'Unrealized value'], ['attempted_succeeded', 'Attempted, succeeded'], ['mixed', 'Mixed']];
const RESOLUTION = [['unknown', 'Unknown'], ['unresolved', 'Unresolved'], ['partially_solved', 'Partially solved'],
  ['reportedly_solved', 'Reportedly solved'], ['disputed', 'Disputed']];
const GAPS = [['education', 'Education'], ['prompting', 'Prompting'], ['configuration', 'Configuration'],
  ['integration', 'Integration'], ['workflow_automation', 'Workflow automation'],
  ['custom_software', 'Custom software opportunity'], ['unsuitable_ai', 'Unsuitable AI use case'],
  ['insufficient_evidence', 'Insufficient evidence']];
const CONSTRAINTS = [['verification', 'Verification'], ['approval', 'Approval'], ['privacy', 'Privacy / confidentiality'],
  ['deterministic', 'Deterministic result required'], ['format', 'Format requirements'],
  ['access', 'Access / permissions'], ['audit', 'Audit / provenance'], ['deployment', 'Deployment constraint'], ['other', 'Other']];
const COMMERCIAL = [['tool_recommendation_requested', 'Tool recommendation requested'], ['vendor_evaluation', 'Vendor evaluation'],
  ['hiring_intent', 'Hiring intent'], ['explicit_budget', 'Explicit budget'], ['willingness_to_pay', 'Willingness to pay'],
  ['none_stated', 'No commercial signal stated']];
const STATUS = {not_reviewed: 'Not reviewed', in_progress: 'In progress', committed: 'Human review committed',
  ai_comparison_available: 'AI comparison available', adjudicated: 'Adjudicated', insufficient_evidence: 'Insufficient evidence'};
const DECISIONS = [['accept_human', 'Accept human'], ['accept_ai', 'Accept AI'], ['merged', 'Merged'], ['unresolved', 'Unresolved']];
const label = (pairs, key) => (pairs.find(p => p[0] === key) || [key, key || '—'])[1];

const S = {state: null, pid: null, view: null, draft: null, editable: false, compare: null, adj: null,
  contextOpen: false, shown: new Set(), collapsed: new Set(), fullText: new Set(), focus: null,
  active: 0, pending: null, open: new Set(['0:workflow', '0:assessment']), query: '', errors: [],
  dirty: false, saveTimer: null, savedAt: null, confirm: null, tree: null};
const T = {visible: 0, active: 0, viewed: new Set(), sentViewed: new Set(), last: Date.now(), timers: new Map(), observer: null};

/* ---------- helpers ---------- */
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k in el && k !== 'list') el[k] = v;
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : String(kid));
  return el;
}
const $ = sel => document.querySelector(sel);
async function api(method, path, body, keepalive) {
  const r = await fetch(path, {method, keepalive: !!keepalive, headers: {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await r.json();
  if (!r.ok) throw Object.assign(new Error((data.errors || ['Request failed']).join('\n')), {errors: data.errors || [], status: r.status});
  return data;
}
function toast(text) {
  const t = $('#toast'); t.textContent = text; t.classList.add('on');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => t.classList.remove('on'), 3500);
}
const fmt = n => Number(n).toLocaleString('en-US');
const when = s => s ? s.replace('T', ' ').slice(0, 16) + ' UTC' : '';
const typing = () => /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement && document.activeElement.tagName);
/* Python offsets count code points; DOM offsets count UTF-16 units. */
const astral = s => /[\ud800-\udfff]/.test(s);
const toCp = (s, u) => astral(s) ? [...s.slice(0, u)].length : u;
const toU16 = (s, cp) => astral(s) ? [...s].slice(0, cp).join('').length : cp;
const cpLength = s => astral(s) ? [...s].length : s.length;
const cpSlice = (s, n) => astral(s) ? [...s].slice(0, n).join('') : s.slice(0, n);
const lines = v => Array.isArray(v) ? v.join('\n') : v || '';

/* ---------- routing ---------- */
window.addEventListener('hashchange', route);
async function route() {
  await leavePacket();
  S.state = await api('GET', '/api/state');
  const parts = location.hash.replace(/^#\/?/, '').split('/');
  if (!S.state.reviewer_id || parts[0] === 'settings') return renderTop(), renderSettings();
  if (parts[0] === 'p' && parts[1]) return openPacket(decodeURIComponent(parts[1]), parts[2] === 'compare');
  renderTop(); renderQueue();
}
const go = hash => { if (location.hash === hash) route(); else location.hash = hash; };
function neighbor(step) {
  const i = S.state.order.indexOf(S.pid);
  const next = S.state.order[i + step];
  if (next) go('#/p/' + encodeURIComponent(next)); else toast(step > 0 ? 'Last packet.' : 'First packet.');
}

function renderTop() {
  const st = S.state, top = $('#top');
  top.replaceChildren();
  if (!st.reviewer_id) return top.append(h('strong', null, 'Gapper review'));
  const jump = h('input', {class: 'jump', placeholder: 'Jump to packet…', list: 'packet-ids', 'aria-label': 'Jump to packet',
    onchange: e => { const v = e.target.value.trim(); const hit = st.order.find(p => p === v) || st.order.find(p => p.includes(v)); if (hit) go('#/p/' + encodeURIComponent(hit)); else toast('No such packet.'); }});
  top.append(h('a', {class: 'brand', href: '#/queue'}, 'Gapper review'),
    h('div', {class: 'progress', title: 'Packets with a committed human review'},
      h('span', null, `${st.reviewed} / ${st.total} packets reviewed`),
      h('progress', {max: st.total, value: st.reviewed})),
    h('nav', null,
      h('a', {class: 'btn', href: '#/queue'}, 'Queue'),
      h('button', {class: 'btn', disabled: !S.pid, onclick: () => neighbor(-1), title: 'Previous packet (p)'}, '← Prev'),
      jump, h('datalist', {id: 'packet-ids'}, st.order.map(p => h('option', {value: p}))),
      h('button', {class: 'btn', disabled: !S.pid, onclick: () => neighbor(1), title: 'Next packet (n)'}, 'Next →'),
      h('button', {class: 'btn', disabled: !st.resume, onclick: () => go('#/p/' + encodeURIComponent(st.resume)), title: 'Most recent unfinished packet, else the first unreviewed one'}, 'Resume'),
      h('button', {class: 'btn', onclick: exportAll}, 'Export'),
      h('button', {class: 'btn ghost', onclick: toggleHelp, title: 'Keyboard shortcuts (?)'}, '?'),
      h('a', {class: 'who', href: '#/settings', title: 'Change reviewer'}, st.reviewer_id)));
}
async function exportAll() {
  try { const r = await api('POST', '/api/export'); toast(`Exported ${r.files.length} files to ${r.directory}`); }
  catch (e) { toast(e.message); }
}

/* ---------- settings ---------- */
function renderSettings() {
  S.pid = null;
  const st = S.state;
  let exposure = st.exposure;
  const id = h('input', {value: st.reviewer_id || '', placeholder: 'e.g. reviewer-a', maxLength: 40, autofocus: true});
  const error = h('p', {class: 'error', role: 'alert'});
  const form = h('form', {class: 'card narrow', onsubmit: async e => {
    e.preventDefault();
    try { await api('POST', '/api/reviewer', {reviewer_id: id.value, exposure}); go('#/queue'); }
    catch (err) { error.textContent = err.message; }
  }},
    h('h1', null, st.reviewer_id ? 'Reviewer' : 'Who is reviewing?'),
    h('p', {class: 'muted'}, 'Stored locally and written into every review record and export. You will not be asked again.'),
    h('label', {class: 'field'}, h('span', null, 'Reviewer ID'), id),
    h('fieldset', null, h('legend', null, 'Before this review, have you seen AI findings about this corpus?'),
      [['none', 'No'], ['prior_summary', 'Yes — general summaries, not per-packet AI annotations']].map(([v, text]) =>
        h('label', {class: 'radio'}, h('input', {type: 'radio', name: 'exposure', checked: exposure === v, onchange: () => { exposure = v; }}), text))),
    error, h('button', {class: 'btn primary'}, 'Save'));
  $('#main').replaceChildren(form);
  id.focus();
}

/* ---------- queue ---------- */
async function renderQueue() {
  S.pid = null;
  const rows = await api('GET', '/api/queue');
  let filter = new Set();  // empty = all statuses
  try { filter = new Set(JSON.parse(sessionStorage.getItem('queue-filters') || '[]').filter(k => k in STATUS)); } catch (_) { /* unfiltered */ }
  const counts = {}; rows.forEach(r => { counts[r.status] = (counts[r.status] || 0) + 1; });
  const chips = h('div', {class: 'seg', role: 'group', 'aria-label': 'Filter by status'});
  const drawChips = () => chips.replaceChildren(
    h('button', {type: 'button', class: filter.size ? '' : 'on', 'aria-pressed': !filter.size, onclick: () => pick(null)}, `All statuses (${rows.length})`),
    ...Object.entries(STATUS).map(([k, v]) => h('button', {type: 'button', class: filter.has(k) ? 'on' : '', 'aria-pressed': filter.has(k), onclick: () => pick(k)}, `${v} (${counts[k] || 0})`)));
  const pick = k => {
    if (k === null) filter.clear(); else if (!filter.delete(k)) filter.add(k);
    if (filter.size === Object.keys(STATUS).length) filter.clear();
    sessionStorage.setItem('queue-filters', JSON.stringify([...filter])); drawChips(); draw();
  };
  const body = h('tbody');
  const draw = () => body.replaceChildren(...rows.map((r, i) => ({r, i})).filter(({r}) => !filter.size || filter.has(r.status)).map(({r, i}) => h('tr', {
    onclick: () => go('#/p/' + encodeURIComponent(r.packet_id))},
    h('td', {class: 'num'}, i + 1),
    h('td', null, h('a', {href: '#/p/' + encodeURIComponent(r.packet_id)}, r.packet_id)),
    h('td', null, h('span', {class: 'status ' + r.status}, STATUS[r.status]), r.open_revision && h('span', {class: 'status in_progress'}, 'Revision open')),
    h('td', null, r.outcome ? label(OUTCOMES, r.outcome) : '—'),
    h('td', {class: 'num'}, r.outcome ? r.episodes : '—'),
    h('td', {class: 'num'}, `${r.initial_record_count} / ${fmt(r.retained_records)}`),
    h('td', {class: 'num'}, `${fmt(r.initial_characters)} / ${fmt(r.characters)}`),
    h('td', {class: 'num'}, `~${fmt(r.initial_tokens_estimate)} / ~${fmt(r.tokens_estimate)}`),
    h('td', null, r.context_opened ? 'Yes' : r.status === 'not_reviewed' ? '—' : 'No'))));
  drawChips(); draw();
  $('#main').replaceChildren(h('section', {class: 'pad'},
    h('div', {class: 'row'}, h('h1', null, 'Review queue'),
      chips),
    h('table', {class: 'queue'}, h('thead', null, h('tr', null,
      ['#', 'Packet', 'Status', 'Outcome', 'Episodes', 'Records shown / retained', 'Characters shown / retained', 'Tokens shown / retained (chars ÷ 4)', 'Extra context opened'].map(t => h('th', null, t)))), body)));
}

/* ---------- packet load / leave ---------- */
async function openPacket(pid, compare) {
  try { S.view = await api('GET', '/api/packets/' + encodeURIComponent(pid)); }
  catch (e) { renderTop(); return $('#main').replaceChildren(h('p', {class: 'pad error'}, e.message)); }
  S.pid = pid; S.compare = null; S.adj = null; S.errors = []; S.pending = null; S.confirm = null; S.query = '';
  S.shown = new Set(); S.collapsed = new Set(); S.fullText = new Set(); S.focus = null; S.active = 0;
  S.open = new Set(['0:workflow', '0:assessment']);
  adoptView();
  S.contextOpen = !!(S.editable && S.view.telemetry && S.view.telemetry.context_opened);
  buildTree();
  if (compare && S.view.comparison && S.view.comparison.revealed) {
    try { S.compare = await api('GET', `/api/packets/${encodeURIComponent(pid)}/comparison`); } catch (e) { toast(e.message); }
  }
  renderTop(); renderPacket();
  const y = +sessionStorage.getItem('scroll:' + pid);
  if (y) $('#thread').scrollTop = y;
}
function adoptView() {
  const v = S.view;
  S.editable = !v.commits.length || !!v.draft;
  S.draft = v.draft || (v.commits.length ? null : {thread_label: null, context_sufficiency: null, coverage_notes: '', episodes: []});
  S.savedAt = v.draft_saved_at; S.dirty = false;
}
async function leavePacket() {
  if (!S.pid) return;
  await saveNow(); await flushTelemetry();
  if (T.observer) T.observer.disconnect();
  T.timers.forEach(clearTimeout); T.timers.clear(); T.viewed.clear(); T.sentViewed.clear();
}

/* ---------- autosave ---------- */
function changed() {
  S.dirty = true; S.confirm = null; S.errors = [];  // stale once the draft changes
  clearTimeout(S.saveTimer); S.saveTimer = setTimeout(saveNow, 600);
  const s = $('#save-state'); if (s) s.textContent = 'Saving…';
}
async function saveNow(keepalive) {
  clearTimeout(S.saveTimer);
  if (!S.dirty || !S.editable || !S.pid) return;
  S.dirty = false;
  try {
    const r = await api('PUT', `/api/packets/${encodeURIComponent(S.pid)}/draft`, S.draft, keepalive);
    S.savedAt = r.saved_at;
    if (S.view.status === 'not_reviewed') { S.view.status = 'in_progress'; const chip = $('.thread-head .status'); if (chip) { chip.className = 'status in_progress'; chip.textContent = STATUS.in_progress; } }
    const s = $('#save-state'); if (s) s.textContent = 'Draft saved ' + new Date(r.saved_at).toLocaleTimeString();
  } catch (e) { S.dirty = true; const s = $('#save-state'); if (s) s.textContent = 'NOT SAVED: ' + e.message; }
}

/* ---------- telemetry: coarse counters only, no interaction log ---------- */
['keydown', 'pointerdown', 'wheel', 'pointermove'].forEach(t => window.addEventListener(t, () => { T.last = Date.now(); }, {passive: true, capture: true}));
setInterval(() => {
  if (!S.pid || !S.editable || document.hidden) return;
  T.visible += 1;
  if (Date.now() - T.last < 60000) T.active += 1;
}, 1000);
setInterval(flushTelemetry, 10000);
async function flushTelemetry(keepalive) {
  if (!S.pid || !S.editable) { T.visible = T.active = 0; return; }
  const viewed = [...T.viewed].filter(i => !T.sentViewed.has(i));
  if (!T.visible && !viewed.length && !S.contextOpen) return;
  const body = {visible_seconds: T.visible, active_seconds: T.active, viewed, context_opened: S.contextOpen};
  T.visible = T.active = 0; viewed.forEach(i => T.sentViewed.add(i));
  try { await api('POST', `/api/packets/${encodeURIComponent(S.pid)}/telemetry`, body, keepalive); } catch (_) { /* burden stays a lower bound */ }
}
document.addEventListener('visibilitychange', () => { if (document.hidden) { saveNow(true); flushTelemetry(true); } });
window.addEventListener('pagehide', () => { saveNow(true); flushTelemetry(true); });
function watchViewed() {
  if (T.observer) T.observer.disconnect();
  T.timers.forEach(clearTimeout); T.timers.clear();
  if (!S.editable) return;
  // A supplemental record counts as viewed after a second on screen, not on a fast scroll past it.
  T.observer = new IntersectionObserver(entries => entries.forEach(en => {
    const id = en.target.dataset.id;
    if (en.isIntersecting && !T.viewed.has(id)) T.timers.set(id, setTimeout(() => T.viewed.add(id), 1000));
    else { clearTimeout(T.timers.get(id)); T.timers.delete(id); }
  }), {root: $('#thread'), threshold: 0.25});
  document.querySelectorAll('#thread article.supplemental').forEach(el => T.observer.observe(el));
}

/* ---------- thread model ---------- */
function buildTree() {
  const recs = S.view.records, reg = S.view.packet.primary_region;
  const byId = new Map(recs.map(r => [r.native_id, r])), kids = new Map(), tops = [];
  const order = (a, b) => (a.created_at || '').localeCompare(b.created_at || '') || a.native_id.localeCompare(b.native_id);
  for (const r of [...recs].sort(order)) {
    if (r.parent_id && byId.has(r.parent_id)) (kids.get(r.parent_id) || kids.set(r.parent_id, []).get(r.parent_id)).push(r.native_id);
    else tops.push(r.native_id);
  }
  const ancestors = new Set();
  for (let r = byId.get(reg.anchor_id), seen = new Set(); r && r.parent_id && !seen.has(r.parent_id); r = byId.get(r.parent_id)) { seen.add(r.parent_id); ancestors.add(r.parent_id); }
  const replies = new Set(), stack = [...(kids.get(reg.anchor_id) || [])];
  while (stack.length) { const i = stack.pop(); if (!replies.has(i)) { replies.add(i); stack.push(...(kids.get(i) || [])); } }
  const size = new Map();
  const count = id => { let n = 1; for (const k of kids.get(id) || []) n += count(k); size.set(id, n); return n; };
  try { tops.forEach(count); } catch (_) { /* extreme depth: sizes are cosmetic */ }
  S.tree = {byId, kids, tops, ancestors, replies, size, primary: new Set(reg.primary_record_ids),
    clipped: new Set(reg.clipped_record_ids), limits: reg.initial_character_limits, reg};
}
const visible = id => S.tree.primary.has(id) || (S.contextOpen && S.shown.has(id));
function roleOf(id) {
  const t = S.tree;
  return id === t.reg.root_id ? 'root' : id === t.reg.anchor_id ? 'anchor' : t.ancestors.has(id) ? 'ancestor' : t.replies.has(id) ? 'reply' : 'other';
}
function reveal(id) {  // make a record and its ancestry visible
  const t = S.tree;
  for (let r = t.byId.get(id), n = 0; r && n < 2000; r = t.byId.get(r.parent_id), n++) {
    if (!t.primary.has(r.native_id)) { S.shown.add(r.native_id); S.contextOpen = true; }
    S.collapsed.delete(r.parent_id);
  }
}
function revealBranch(ids, deep) {
  S.contextOpen = true;
  const stack = [...ids]; let n = 0;
  while (stack.length && n < 300) { const i = stack.shift(); if (!S.tree.primary.has(i) && !S.shown.has(i)) { S.shown.add(i); n++; } if (deep) stack.push(...(S.tree.kids.get(i) || [])); }
  if (stack.length) toast('Opened 300 records; expand further branches as needed.');
}
function jumpTo(id) {
  reveal(id); S.focus = id; renderThread();
  const el = document.querySelector(`#thread article[data-id="${CSS.escape(id)}"]`);
  if (el) { el.scrollIntoView({block: 'center'}); el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 1500); }
}

/* ---------- claims shown in the thread ---------- */
function shownClaims() {
  const out = [];
  const add = (ann, side) => { if (!ann) return;
    (ann.episodes || []).forEach((e, i) => (e.claims || []).forEach(c => out.push({c, side, n: (isHistorical(e) ? 'H' : 'E') + (i + 1)})));
    (ann.historical_episodes || []).forEach((e, i) => (e.claims || []).forEach(c => out.push({c, side, n: 'H' + (i + 1)}))); };
  if (S.compare) { add(S.compare.human.annotation, 'human'); add(S.compare.reveal.ai_result.annotation, 'ai'); }
  else add(S.draft || (S.view.commits.length && S.view.commits[S.view.commits.length - 1].annotation), 'human');
  return out;
}
function segments(text, spans) {
  const cuts = new Set([0, text.length]);
  spans.forEach(s => { cuts.add(Math.min(s.a, text.length)); cuts.add(Math.min(s.b, text.length)); });
  const pts = [...cuts].sort((x, y) => x - y), out = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const cover = spans.filter(s => s.a <= pts[i] && s.b >= pts[i + 1]), piece = text.slice(pts[i], pts[i + 1]);
    out.push(cover.length ? h('mark', {class: [...new Set(cover.map(s => s.side))].join(' '), title: cover.map(s => s.title).join('\n')}, piece) : piece);
  }
  return out;
}

/* ---------- thread rendering ---------- */
function renderPacket() {
  const p = S.view.packet, reg = p.primary_region;
  const search = h('input', {id: 'search', type: 'search', placeholder: 'Search this thread ( / )', value: S.query,
    oninput: e => { S.query = e.target.value; renderHits(); }});
  $('#main').replaceChildren(h('div', {class: 'split' + (S.compare ? ' comparing' : '')},
    h('section', {id: 'thread-pane'},
      h('div', {class: 'thread-head'},
        h('div', {class: 'row'}, h('h1', null, p.packet_id), h('span', {class: 'status ' + S.view.status}, STATUS[S.view.status]), search),
        h('p', {class: 'muted small'}, `Showing ${reg.initial_record_count} of ${fmt(p.retained_records)} retained records · ${fmt(reg.initial_characters)} of ${fmt(p.characters)} characters (~${fmt(reg.initial_tokens_estimate)} tokens). `,
          'The region is chosen by thread structure, not relevance: being displayed does not make a comment evidence. Retained context may not be the complete source thread.',
          reg.relationship_gaps.length ? ` Relationship gaps: ${reg.relationship_gaps.join(', ')}.` : ''),
        h('div', {id: 'hits'})),
      h('div', {id: 'thread', onscroll: e => sessionStorage.setItem('scroll:' + S.pid, e.target.scrollTop)})),
    h('section', {id: 'panel'})));
  renderThread(); renderPanel();
}
function renderThread() {
  const box = $('#thread'), y = box.scrollTop, t = S.tree, claims = shownClaims();
  const secondary = t.reg.secondary_record_ids.length;
  const nodes = [];
  if (secondary) nodes.push(h('div', {class: 'context-bar'}, S.contextOpen
    ? h('span', null, `Additional context open: ${S.shown.size} of ${fmt(secondary)} supplemental records expanded. Expand branches below as needed. `,
        h('button', {class: 'link', onclick: () => { revealBranch(t.tops, true); renderThread(); }}, 'Expand more'))
    : h('button', {class: 'btn', onclick: openContext, title: 'Shortcut: x'}, `Show additional thread context (${fmt(secondary)} more records)`)));
  nodes.push(level(t.tops, claims));
  box.replaceChildren(...nodes);
  box.scrollTop = y;
  watchViewed();
}
function openContext() { S.contextOpen = true; flushTelemetry(); renderThread(); }
function level(ids, claims) {
  const out = h('div', {class: 'level'}), hidden = ids.filter(i => !visible(i));
  ids.filter(visible).forEach(i => out.append(comment(i, claims)));
  if (S.contextOpen && hidden.length) {
    const total = hidden.reduce((n, i) => n + (S.tree.size.get(i) || 1), 0);
    out.append(h('div', {class: 'stub'}, h('button', {class: 'link', onclick: () => { revealBranch(hidden, false); renderThread(); }},
      `▸ ${hidden.length} more ${hidden.length === 1 ? 'reply' : 'replies'} (supplemental)`),
      total > hidden.length && h('button', {class: 'link', onclick: () => { revealBranch(hidden, true); renderThread(); }}, `expand all ${total} in these branches`)));
  }
  return out;
}
function comment(id, claims) {
  const t = S.tree, r = t.byId.get(id), role = roleOf(id), primary = t.primary.has(id), kids = t.kids.get(id) || [];
  const clip = t.clipped.has(id) && !S.fullText.has(id), limit = t.limits[id];
  let title = r.title || '', text = r.text || '';
  const fullLength = cpLength(title) + cpLength(text);
  if (clip) { title = cpSlice(title, limit); text = cpSlice(text, Math.max(0, limit - cpLength(title))); }
  const showTitle = title && !(r.parent_id && t.byId.has(r.parent_id));
  const mine = claims.filter(x => x.c.record_id === id);
  const spans = field => mine.filter(x => x.c.text_field === field && x.c.span_kind !== 'record' && !(x.c.start === 0 && x.c.end >= cpLength(r[field] || '')))
    .map(x => ({a: toU16(r[field] || '', x.c.start), b: toU16(r[field] || '', x.c.end), side: x.side,
      title: `${x.side === 'ai' ? 'AI' : 'Human'} · ${x.n} · ${label(ROLES, x.c.field)} · ${label(RELATIONS, x.c.polarity)}`}));
  const collapsed = S.collapsed.has(id);
  const badges = [role !== 'other' && h('span', {class: 'badge ' + role, title: {root: 'Thread root', anchor: 'Structural anchor of the displayed region; chosen by ID hash, not relevance', ancestor: 'Ancestor of the anchor', reply: 'Reply beneath the anchor'}[role]}, role),
    !primary && h('span', {class: 'badge supp'}, 'supplemental context'),
    h('span', {class: 'badge scope', title: r.scope === 'sample' ? 'Created inside the sampling window' : 'Older supporting context, outside the sampling window'}, r.scope === 'sample' ? 'in window' : 'earlier context'),
    !['comment', 'reply'].includes(r.item_type) && h('span', {class: 'badge scope'}, r.item_type)];
  const el = h('article', {class: `c ${role} ${primary ? '' : 'supplemental'} ${S.focus === id ? 'focus' : ''}`, dataset: {id}, tabIndex: -1,
    onclick: () => { if (S.focus !== id) { document.querySelectorAll('#thread article.focus').forEach(a => a.classList.remove('focus')); S.focus = id; el.classList.add('focus'); } }},
    h('header', null, h('span', {class: 'author'}, r.author || '[no author]'), h('span', {class: 'time'}, when(r.created_at)), badges,
      h('span', {class: 'grow'}),
      kids.length > 0 && h('button', {class: 'link', onclick: e => { e.stopPropagation(); collapsed ? S.collapsed.delete(id) : S.collapsed.add(id); renderThread(); }}, collapsed ? `▸ ${t.size.get(id) - 1} hidden` : '▾'),
      S.editable && h('button', {class: 'btn tiny', disabled: !(r.text || r.title), title: 'Link this comment as evidence (e)', onclick: e => { e.stopPropagation(); startEvidence(id); }}, '+ Evidence')),
    showTitle && h('h3', {class: 'title', dataset: {field: 'title'}}, segments(title, spans('title'))),
    text ? h('div', {class: 'body', dataset: {field: 'text'}}, segments(text, spans('text')))
      : !showTitle && h('p', {class: 'muted small'}, '(no text retained for this record)'),
    clip && h('button', {class: 'link', onclick: e => { e.stopPropagation(); S.fullText.add(id); T.viewed.add(id); renderThread(); }}, `… show full text (+${fmt(fullLength - limit)} characters)`),
    mine.length > 0 && h('div', {class: 'chips'}, mine.map(x => h('span', {class: 'chip ' + x.side + ' ' + x.c.polarity},
      `${x.side === 'ai' ? 'AI ' : ''}${x.n} · ${label(ROLES, x.c.field)}${x.c.polarity !== 'supports' ? ' · ' + label(RELATIONS, x.c.polarity).toLowerCase() : ''}`))));
  const wrap = h('div', {class: 'node'}, el);
  if (kids.length && !collapsed) wrap.append(level(kids, claims));
  return wrap;
}
function renderHits() {
  const box = $('#hits'), q = S.query.trim().toLowerCase();
  if (q.length < 2) return box.replaceChildren();
  const hits = S.view.records.filter(r => ((r.text || '') + '\n' + (r.title || '') + '\n' + (r.author || '')).toLowerCase().includes(q));
  const inView = hits.filter(r => visible(r.native_id)), outside = hits.length - inView.length;
  // Snippets of undisplayed records would be unrecorded exposure, so only their count is shown.
  const list = (S.contextOpen ? hits : inView).slice(0, 40);
  box.replaceChildren(h('div', {class: 'hits'},
    h('p', {class: 'small muted'}, `${hits.length} matching records`, !S.contextOpen && outside ? ` · ${outside} in additional context ` : '',
      !S.contextOpen && outside ? h('button', {class: 'link', onclick: () => { openContext(); renderHits(); }}, 'open it to see them') : ''),
    list.map(r => { const s = (r.text || r.title || ''), at = Math.max(0, s.toLowerCase().indexOf(q));
      return h('button', {class: 'hit', onclick: () => jumpTo(r.native_id)}, h('b', null, r.author || '—'), ' ', s.slice(Math.max(0, at - 40), at + 80)); })));
}

/* ---------- evidence ---------- */
function episode() { return S.draft.episodes[S.active]; }
/* Derived, never chosen: an episode with evidence but none from an in-window record. */
function isHistorical(e) {
  const fresh = new Set(S.view.packet.anchor_ids);
  return (e.claims || []).length > 0 && !e.claims.some(c => fresh.has(c.record_id));
}
function addEpisode() {
  const ids = new Set(S.draft.episodes.map(e => e.episode_id)); let n = S.draft.episodes.length + 1;
  while (ids.has('episode-' + n)) n++;
  S.draft.episodes.push({episode_id: 'episode-' + n, actor_ref: '', workflow: '', need_status: null, adoption_status: null,
    resolution: null, gap_labels: [], claims: [], hypotheses: '', open_questions: '', details: {burden: {}, constraints: [], commercial_signals: []}});
  S.active = S.draft.episodes.length - 1;
  S.open.add(S.active + ':workflow'); S.open.add(S.active + ':assessment');
  if (!S.draft.thread_label) S.draft.thread_label = 'unknown';
  changed();
}
function startEvidence(id, span) {
  if (!S.editable) return;
  const r = S.tree.byId.get(id), field = span ? span.field : (r.text ? 'text' : 'title');
  if (!S.draft.episodes.length) addEpisode();
  S.pending = {record_id: id, text_field: field, start: span ? span.start : 0, end: span ? span.end : cpLength(r[field] || ''),
    span_kind: span ? 'span' : 'record', field: 'pain', basis: 'firsthand_report', polarity: 'supports', summary: '', relates_to: null};
  hideSelectionButton(); renderPanel();
  const input = $('#evidence-summary'); if (input) { input.scrollIntoView({block: 'center'}); input.focus(); }
}
function commitEvidence() {
  const p = S.pending, e = episode();
  if (!p.summary.trim()) return toast('Add a one-line summary of what this evidence says.');
  let n = e.claims.length + 1; const ids = new Set(e.claims.map(c => c.claim_id));
  while (ids.has('c' + n)) n++;
  e.claims.push({claim_id: 'c' + n, ...p, summary: p.summary.trim(), in_minimum_set: true});
  S.pending = null; changed(); renderPanel(); renderThread();
}
const selectionButton = h('button', {class: 'btn primary floating', onmousedown: e => e.preventDefault(), onclick: () => { if (selectionButton.span) startEvidence(selectionButton.span.id, selectionButton.span); }}, '+ Add selection as evidence');
document.body.append(selectionButton);
function hideSelectionButton() { selectionButton.classList.remove('on'); selectionButton.span = null; }
function offsetIn(root, node, offset) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let total = 0;
  for (let n = walker.nextNode(); n; n = walker.nextNode()) { if (n === node) return total + offset; total += n.data.length; }
  return null;
}
document.addEventListener('selectionchange', () => {
  const sel = getSelection();
  if (!S.editable || !sel.rangeCount || sel.isCollapsed) return hideSelectionButton();
  const range = sel.getRangeAt(0);
  const holder = n => (n.nodeType === 1 ? n : n.parentElement).closest('[data-field]');
  const a = holder(range.startContainer), b = holder(range.endContainer);
  if (!a || a !== b || range.startContainer.nodeType !== 3 || range.endContainer.nodeType !== 3) return hideSelectionButton();
  const id = a.closest('article').dataset.id, field = a.dataset.field, text = S.tree.byId.get(id)[field] || '';
  const s = offsetIn(a, range.startContainer, range.startOffset), e = offsetIn(a, range.endContainer, range.endOffset);
  if (s == null || e == null || e <= s) return hideSelectionButton();
  selectionButton.span = {id, field, start: toCp(text, s), end: toCp(text, e)};
  const box = range.getBoundingClientRect();
  selectionButton.style.top = Math.max(8, box.top - 40) + 'px';
  selectionButton.style.left = Math.max(8, Math.min(box.left, innerWidth - 260)) + 'px';
  selectionButton.classList.add('on');
});

/* ---------- form controls ---------- */
function field(text, control, hint) { return h('label', {class: 'field'}, h('span', null, text, hint && h('em', null, ' ' + hint)), control); }
function input(obj, key, props) { return h('input', {value: obj[key] || '', oninput: e => { obj[key] = e.target.value; changed(); }, ...props}); }
function area(obj, key, props) { return h('textarea', {rows: 2, value: lines(obj[key]), oninput: e => { obj[key] = e.target.value; changed(); }, ...props}); }
function select(obj, key, options, after) {
  return h('select', {onchange: e => { obj[key] = e.target.value || null; changed(); if (after) after(); }},
    h('option', {value: ''}, '—'), options.map(([v, t]) => h('option', {value: v, selected: obj[key] === v}, t)));
}
function checks(obj, key, options) {
  if (!Array.isArray(obj[key])) obj[key] = [];
  return h('div', {class: 'checks'}, options.map(([v, t]) => h('label', {class: 'check'},
    h('input', {type: 'checkbox', checked: obj[key].includes(v), onchange: e => { obj[key] = e.target.checked ? [...obj[key], v] : obj[key].filter(x => x !== v); changed(); }}), t)));
}
function segmented(value, options, pick) {
  return h('div', {class: 'seg'}, options.map(([v, t]) => h('button', {type: 'button', class: value === v ? 'on' : '', 'aria-pressed': value === v, onclick: () => pick(v)}, t)));
}
function group(key, title, filled, ...content) {
  const id = S.active + ':' + key;
  return h('details', {open: S.open.has(id), ontoggle: e => { e.target.open ? S.open.add(id) : S.open.delete(id); }},
    h('summary', null, title, filled > 0 && h('span', {class: 'count'}, filled)), ...content);
}
const filledIn = (obj, keys) => keys.filter(k => obj && (Array.isArray(obj[k]) ? obj[k].length : obj[k] && typeof obj[k] === 'object' ? Object.values(obj[k]).some(Boolean) : obj[k])).length;
function twoStep(key, text, confirmText, run, props) {
  return S.confirm === key
    ? h('span', {class: 'confirm'}, h('button', {class: 'btn danger', id: 'confirm-go', onclick: run}, confirmText), h('button', {class: 'btn', onclick: () => { S.confirm = null; renderPanel(); }}, 'Cancel'))
    : h('button', {class: 'btn primary', ...props, onclick: () => { S.confirm = key; renderPanel(); const b = $('#confirm-go'); if (b) b.focus(); }}, text);
}

/* ---------- annotation panel ---------- */
function renderPanel() {
  const panel = $('#panel'); if (!panel) return;
  const y = panel.scrollTop;
  panel.replaceChildren(...(S.compare ? comparePanel() : S.editable ? editPanel() : committedPanel()).flat().filter(Boolean));
  panel.scrollTop = y;
}
function setOutcome(v) { S.draft.thread_label = v; changed(); renderPanel(); }
function editPanel() {
  const d = S.draft, revising = S.view.commits.length > 0;
  const authors = [...new Set(S.view.records.map(r => r.author).filter(Boolean))];
  const out = [h('datalist', {id: 'authors'}, authors.slice(0, 400).map(a => h('option', {value: a})), h('option', {value: 'unresolved'})),
    h('div', {class: 'commit-bar'}, h('span', {id: 'save-state', class: 'muted small'}, S.dirty ? 'Saving…' : S.savedAt ? 'Draft saved ' + new Date(S.savedAt).toLocaleTimeString() : 'Nothing to save yet'),
      twoStep('commit', revising ? 'Commit revision' : 'Commit human review', 'Confirm: commit as immutable record', commitReview, {title: 'Ctrl+Enter'})),
    S.errors.length > 0 && h('ul', {class: 'error', role: 'alert'}, S.errors.map(e => h('li', null, e)))];
  if (revising) out.push(h('div', {class: 'notice'}, h('strong', null, `Revising committed review (revision ${S.view.commits.length} stays unchanged). `),
    S.view.comparison.revealed ? 'The AI annotation has been revealed, so this revision is recorded as AI-assisted. ' : '',
    field('Reason for revision', input(d, 'revision_note', {placeholder: 'What changed and why'})),
    h('button', {class: 'link', onclick: async () => { S.dirty = false; S.view = await api('POST', `/api/packets/${encodeURIComponent(S.pid)}/discard-revision`); adoptView(); renderPacket(); }}, 'Discard this revision draft')));
  out.push(h('h2', null, 'Outcome'), h('div', {class: 'outcomes'}, OUTCOMES.map(([v, t, hint], i) =>
    h('button', {class: 'outcome' + (d.thread_label === v ? ' on' : ''), 'aria-pressed': d.thread_label === v, onclick: () => setOutcome(v)},
      h('kbd', null, i + 1), h('span', null, h('b', null, t), h('small', null, hint))))));
  if (d.thread_label !== 'insufficient_evidence' || d.episodes.length) {
    out.push(h('div', {class: 'row'}, h('h2', null, `Workflow episodes (${d.episodes.length})`),
      h('button', {class: 'btn', onclick: () => { addEpisode(); renderPanel(); }, title: 'Shortcut: a'}, '+ Add episode')));
    if (!d.episodes.length) out.push(h('p', {class: 'muted small'}, 'Add an episode, or press “+ Evidence” on a comment to start one. A thread can hold several independent episodes.'));
    d.episodes.forEach((e, i) => out.push(i === S.active ? episodeCard(e, i) : h('button', {class: 'episode-tab', onclick: () => { S.active = i; S.pending = null; renderPanel(); }},
      h('b', null, `${isHistorical(e) ? 'H' : 'E'}${i + 1}`), ' ', e.workflow || '(no description yet)', isHistorical(e) && h('span', {class: 'badge'}, 'historical'), h('span', {class: 'count'}, `${e.claims.length} evidence`))));
  }
  out.push(h('h2', null, 'Context'),
    h('p', {class: 'muted small'}, 'Was the initially shown region enough for your judgment?'),
    segmented(d.context_sufficiency, SUFFICIENCY, v => { d.context_sufficiency = v; changed(); renderPanel(); }),
    field('Coverage notes', area(d, 'coverage_notes', {placeholder: 'Optional. One note per line, e.g. context read outside this app.'}), 'optional'));
  return out;
}
function episodeCard(e, i) {
  if (!e.details) e.details = {};
  const x = e.details; if (!x.burden || typeof x.burden !== 'object') x.burden = {};
  const rerender = () => renderPanel();
  return h('div', {class: 'episode'},
    h('div', {class: 'row'}, h('h3', null, `Episode ${i + 1}`),
      isHistorical(e) && h('span', {class: 'badge anchor', title: 'None of this episode’s evidence cites an in-window record, so it is recorded as historical: kept, but not counted as new demand. Linking evidence from an in-window comment makes it a new episode.'}, 'historical · not counted as new'),
      h('span', {class: 'grow'}),
      h('button', {class: 'link danger', onclick: () => { if (e.claims.length && S.confirm !== 'del' + i) { S.confirm = 'del' + i; toast('Press remove again to delete this episode and its evidence links.'); return; } S.draft.episodes.splice(i, 1); S.active = Math.max(0, i - 1); S.pending = null; changed(); renderPanel(); renderThread(); }}, 'Remove episode')),
    group('workflow', 'Actor and workflow', 0,
      field('Workflow / task', input(e, 'workflow', {placeholder: 'Short, supported description of the work'})),
      field('Desired outcome', input(x, 'desired_outcome'), 'optional'),
      h('div', {class: 'cols'}, field('Actor / speaker', input(e, 'actor_ref', {list: 'authors', placeholder: 'source account, or unresolved'})),
        field('Role / domain', input(x, 'actor_role', {placeholder: 'only if explicitly stated'}), 'optional'))),
    h('div', {class: 'evidence'}, h('h4', null, `Evidence (${e.claims.length})`),
      S.pending ? evidenceForm(e) : h('p', {class: 'muted small'}, 'Press “+ Evidence” on a comment, or select text inside one, to link it here. Source IDs and offsets are stored automatically.'),
      e.claims.map((c, n) => { const r = S.tree.byId.get(c.record_id) || {};
        return h('div', {class: 'claim ' + c.polarity},
          h('div', {class: 'row'}, h('span', {class: 'chip human ' + c.polarity}, label(ROLES, c.field)),
            h('select', {class: 'mini', 'aria-label': 'Relation', onchange: ev => { c.polarity = ev.target.value; changed(); renderPanel(); renderThread(); }}, RELATIONS.map(([v, t]) => h('option', {value: v, selected: c.polarity === v}, t))),
            h('button', {class: 'link', onclick: () => jumpTo(c.record_id), title: 'Show in thread'}, `${r.author || '—'} · ${c.record_id}${c.span_kind === 'span' ? ` [${c.start}–${c.end}]` : ''}`),
            h('span', {class: 'grow'}),
            h('label', {class: 'check small', title: 'Part of the smallest set of records needed to support this episode'}, h('input', {type: 'checkbox', checked: c.in_minimum_set !== false, onchange: ev => { c.in_minimum_set = ev.target.checked; changed(); }}), 'minimum set'),
            h('button', {class: 'link danger', 'aria-label': 'Remove evidence', onclick: () => { e.claims.splice(n, 1); changed(); renderPanel(); renderThread(); }}, '×')),
          input(c, 'summary', {placeholder: 'What this evidence says (one line)'})); })),
    group('assessment', 'Gap assessment', 0,
      h('span', {class: 'lbl'}, 'Need status'), segmented(e.need_status, NEED, v => { e.need_status = v; changed(); rerender(); }),
      h('div', {class: 'cols'}, field('Adoption status', select(e, 'adoption_status', ADOPTION)), field('Resolution', select(e, 'resolution', RESOLUTION))),
      h('span', {class: 'lbl'}, 'Provisional gap labels (may overlap)'), checks(e, 'gap_labels', GAPS)),
    group('details', 'Workflow details', filledIn(x, ['steps', 'inputs', 'outputs', 'systems']),
      field('Steps, where reconstructable', area(x, 'steps', {placeholder: 'One per line'})),
      h('div', {class: 'cols'}, field('Inputs / artifacts', area(x, 'inputs')), field('Outputs / artifacts', area(x, 'outputs'))),
      field('Systems / tools involved', area(x, 'systems'))),
    group('friction', 'Friction and burden', filledIn(x, ['pain', 'residual_manual_work', 'burden']),
      field('Pain / problem', area(x, 'pain')), field('Residual manual work', area(x, 'residual_manual_work')),
      h('span', {class: 'lbl'}, 'Burden — only values stated in the discussion'),
      h('div', {class: 'cols'}, ['time', 'frequency', 'volume', 'cost', 'other'].map(k => field(k[0].toUpperCase() + k.slice(1), input(x.burden, k))))),
    group('approach', 'Current approach', filledIn(x, ['workaround', 'tool_attempted', 'failure_mode', 'consequence']),
      field('Workaround / current process', area(x, 'workaround')), field('AI / tool attempted', input(x, 'tool_attempted')),
      field('Reported failure mode', area(x, 'failure_mode')), field('Reported consequence', area(x, 'consequence'))),
    group('constraints', 'Constraints', filledIn(x, ['constraints', 'constraints_note']), checks(x, 'constraints', CONSTRAINTS), field('Notes', area(x, 'constraints_note'))),
    group('commercial', 'Commercial evidence (separate from workflow existence)', filledIn(x, ['commercial_signals', 'commercial_note']),
      checks(x, 'commercial_signals', COMMERCIAL), field('Notes', area(x, 'commercial_note'))),
    group('notes', 'Reviewer notes', filledIn({n: x.note, q: lines(e.open_questions), y: lines(e.hypotheses)}, ['n', 'q', 'y']),
      field('Note', area(x, 'note')), field('Open questions', area(e, 'open_questions', {placeholder: 'One per line'})),
      field('Hypotheses (inference, not evidence)', area(e, 'hypotheses', {placeholder: 'One per line'}))));
}
function evidenceForm(e) {
  const p = S.pending, r = S.tree.byId.get(p.record_id), src = r[p.text_field] || '';
  const quote = src.slice(toU16(src, p.start), toU16(src, p.end));
  const done = ev => { if (ev.key === 'Enter') { ev.preventDefault(); commitEvidence(); } if (ev.key === 'Escape') { S.pending = null; renderPanel(); } };
  return h('div', {class: 'pending'},
    h('p', {class: 'small'}, h('b', null, p.span_kind === 'span' ? 'Selected text' : 'Whole comment'), ` · ${r.author || '—'} · ${p.record_id}`),
    h('blockquote', null, quote.length > 240 ? quote.slice(0, 240) + '…' : quote),
    h('div', {class: 'cols'}, field('Evidence role', select(p, 'field', ROLES)), field('Basis', select(p, 'basis', BASES)),
      field('Relation', select(p, 'polarity', RELATIONS, () => renderPanel()))),
    p.polarity !== 'supports' && e.claims.length > 0 && field('Relates to', select(p, 'relates_to', e.claims.map(c => [c.claim_id, `${label(ROLES, c.field)}: ${c.summary.slice(0, 50)}`])), 'optional'),
    field('Summary', h('input', {id: 'evidence-summary', value: p.summary, placeholder: 'What this says, in one line — Enter to add', oninput: ev => { p.summary = ev.target.value; }, onkeydown: done})),
    h('div', {class: 'row'}, h('button', {class: 'btn primary', onclick: commitEvidence}, 'Add evidence'), h('button', {class: 'btn', onclick: () => { S.pending = null; renderPanel(); }}, 'Cancel')));
}
async function commitReview() {
  try {
    S.dirty = true; await saveNow(); await flushTelemetry();
    S.view = await api('POST', `/api/packets/${encodeURIComponent(S.pid)}/commit`);
    S.errors = []; S.confirm = null; adoptView();
    S.state = await api('GET', '/api/state');
    renderTop(); renderPacket(); toast('Human review committed and exported.');
  } catch (e) { S.errors = e.errors && e.errors.length ? e.errors : [e.message]; S.confirm = null; renderPanel(); $('#panel').scrollTop = 0; }
}

/* ---------- committed (read-only) ---------- */
function episodeSummary(e, i, side, pair) {
  const diff = k => pair && pair.labels[k].disagrees ? ' diff' : '';
  const only = pair ? new Set(pair.evidence_records[side + '_only']) : new Set();
  const gapOnly = pair ? new Set(pair.gap_labels[side + '_only']) : new Set();
  const x = e.details || {};
  const extra = [['Desired outcome', x.desired_outcome], ['Role / domain', x.actor_role], ['Steps', lines(x.steps)], ['Inputs', lines(x.inputs)], ['Outputs', lines(x.outputs)],
    ['Systems', lines(x.systems)], ['Pain', x.pain], ['Residual manual work', x.residual_manual_work], ['Burden', Object.entries(x.burden || {}).map(([k, v]) => `${k}: ${v}`).join('; ')],
    ['Workaround', x.workaround], ['Tool attempted', x.tool_attempted], ['Failure mode', x.failure_mode], ['Consequence', x.consequence],
    ['Constraints', [(x.constraints || []).map(c => label(CONSTRAINTS, c)).join(', '), x.constraints_note].filter(Boolean).join(' — ')],
    ['Commercial', [(x.commercial_signals || []).map(c => label(COMMERCIAL, c)).join(', '), x.commercial_note].filter(Boolean).join(' — ')],
    ['Note', x.note], ['Open questions', lines(e.open_questions)]].filter(r => r[1]);
  return h('div', {class: 'episode summary ' + side},
    h('h4', null, `${side === 'ai' ? 'AI' : 'Human'} ${e.historical ? 'H' : 'E'}${i + 1}: `, e.workflow, e.historical && h('span', {class: 'badge'}, 'historical · not counted as new')), h('p', {class: 'small muted'}, `Actor: ${e.actor_ref} · id ${e.episode_id}`),
    h('p', {class: 'small'}, h('span', {class: 'kv' + diff('need_status')}, 'Need: ' + label(NEED, e.need_status)), h('span', {class: 'kv' + diff('adoption_status')}, 'Adoption: ' + label(ADOPTION, e.adoption_status)),
      h('span', {class: 'kv' + diff('resolution')}, 'Resolution: ' + label(RESOLUTION, e.resolution))),
    h('p', {class: 'small'}, 'Gaps: ', (e.gap_labels || []).length ? e.gap_labels.map(g => h('span', {class: 'chip' + (gapOnly.has(g) ? ' diff' : '')}, label(GAPS, g))) : '—'),
    h('ul', {class: 'claims'}, e.claims.map(c => h('li', {class: only.has(c.record_id) ? 'diff' : ''},
      h('span', {class: `chip ${side} ${c.polarity}`}, label(ROLES, c.field)), ' ', h('em', null, `${label(RELATIONS, c.polarity).toLowerCase()}, ${label(BASES, c.basis).toLowerCase()}`), ' ',
      h('button', {class: 'link', onclick: () => jumpTo(c.record_id)}, c.record_id), ' — ', c.summary, only.has(c.record_id) && h('span', {class: 'tag'}, side === 'ai' ? 'record not cited by human' : 'record not cited by AI')))),
    extra.length > 0 && h('dl', {class: 'small'}, extra.map(([k, v]) => [h('dt', null, k), h('dd', null, v)])),
    side === 'ai' && (e.hypotheses || []).length > 0 && h('p', {class: 'small inferred'}, h('b', null, 'AI inference, not supported by the human review: '), e.hypotheses.join(' · ')),
    side === 'ai' && pair && pair.ai_unsupported_by_human.claim_fields.length > 0 && h('p', {class: 'small inferred'}, 'Evidence roles only the AI populated: ', pair.ai_unsupported_by_human.claim_fields.map(f => label(ROLES, f)).join(', ')));
}
function committedPanel() {
  const commits = S.view.commits, last = commits[commits.length - 1], a = last.annotation, b = a.review_burden, cmp = S.view.comparison;
  const act = async (path, after) => { try { const r = await api('POST', `/api/packets/${encodeURIComponent(S.pid)}/${path}`); after(r); } catch (e) { S.confirm = null; toast(e.message); renderPanel(); } };
  return [h('div', {class: 'commit-bar'},
      h('button', {class: 'btn', onclick: () => act('revise', r => { S.view = r; adoptView(); renderPacket(); })}, `Revise (creates revision ${last.revision + 1})`),
      cmp.revealed ? h('a', {class: 'btn primary', href: `#/p/${encodeURIComponent(S.pid)}/compare`}, 'Open AI comparison')
        : cmp.available ? twoStep('reveal', 'Compare with AI annotation', 'Confirm: reveal AI (later revisions become AI-assisted)', () => act('reveal', () => go(`#/p/${encodeURIComponent(S.pid)}/compare`)))
          : h('span', {class: 'muted small'}, 'No AI annotation was sealed for this packet.'),
      h('button', {class: 'btn', onclick: () => neighbor(1)}, 'Next packet →')),
    h('div', {class: 'notice ok'}, h('strong', null, `Human review committed — revision ${last.revision}`), h('br'),
      `${when(last.committed_at)} · ${a.reviewer_id} · ${a.reviewer_kind.replace('_', ' ')}`),
    h('h2', null, 'Outcome'), h('p', null, h('b', null, label(OUTCOMES, a.thread_label))),
    a.episodes.map((e, i) => episodeSummary(e, i, 'human')),
    (a.historical_episodes || []).map((e, i) => episodeSummary(e, i, 'human')),
    h('p', {class: 'small muted'}, `Context: ${label(SUFFICIENCY, b.context_sufficiency)} · scope ${b.review_scope.replace('_', ' ')} · extra context ${b.extra_context_opened ? `opened (${b.expanded_record_ids.length} records viewed)` : 'not opened'} · active ${Math.round(b.active_seconds / 6) / 10} min`),
    a.coverage_notes.length > 0 && h('p', {class: 'small'}, 'Coverage notes: ', a.coverage_notes.join(' · ')),
    commits.length > 1 && h('details', null, h('summary', null, `Revision history (${commits.length})`), h('ul', {class: 'small'}, commits.map(c => h('li', null, `r${c.revision} · ${when(c.committed_at)} · ${label(OUTCOMES, c.annotation.thread_label)} · ${c.annotation.episodes.length} episodes${c.revision_note ? ' — ' + c.revision_note : ''}`))))];
}

/* ---------- comparison and adjudication ---------- */
function adjState() {
  if (S.adj) return S.adj;
  const d = S.compare.reveal.differences;
  const rows = d.suggested_pairs.map(p => ({...p})).concat(d.human_only_episode_ids.map(i => ({human_episode_id: i, ai_episode_id: null})),
    d.ai_only_episode_ids.map(i => ({human_episode_id: null, ai_episode_id: i})));
  return S.adj = {rationale: '', thread_label: {decision: null, value: null, rationale: ''}, episodes: rows.map(r => ({...r, decision: null, rationale: '', merged: {}}))};
}
function realign(row, aiId) {  // the reviewer, not overlap arithmetic, decides which episodes correspond
  const adj = adjState();
  if (row.ai_episode_id) adj.episodes.push({human_episode_id: null, ai_episode_id: row.ai_episode_id, decision: null, rationale: '', merged: {}});
  adj.episodes = adj.episodes.filter(r => !(r.human_episode_id === null && r.ai_episode_id === aiId));
  adj.episodes.forEach(r => { if (r !== row && r.ai_episode_id === aiId) r.ai_episode_id = null; });
  row.ai_episode_id = aiId || null;
  renderPanel();
}
function comparePanel() {
  const {reveal, human, adjudications} = S.compare, d = reveal.differences, H = human.annotation, A = reveal.ai_result.annotation, adj = adjState();
  const he = new Map(H.episodes.map((e, i) => [e.episode_id, [e, i]])), ae = new Map(A.episodes.map((e, i) => [e.episode_id, [e, i]]));
  const pairOf = r => d.pairs.find(p => p.human_episode_id === r.human_episode_id && p.ai_episode_id === r.ai_episode_id);
  const latest = adjudications[adjudications.length - 1];
  const out = [h('div', {class: 'row'}, h('h2', null, 'Human and AI annotation'), h('a', {class: 'btn', href: '#/p/' + encodeURIComponent(S.pid)}, '← Back to review')),
    h('p', {class: 'small muted'}, `Comparing committed human revision ${reveal.human_revision} with the AI annotation sealed before it. Both originals stay unchanged; adjudication is a third record. `,
      'Highlighted items differ. Episode pairing is a suggestion from shared evidence records — correct it if wrong.'),
    h('div', {class: 'pair head'}, h('div', {class: d.thread_label.disagrees ? 'diff' : ''}, h('b', null, 'Human: '), label(OUTCOMES, H.thread_label)),
      h('div', {class: d.thread_label.disagrees ? 'diff' : ''}, h('b', null, 'AI: '), label(OUTCOMES, A.thread_label))),
    d.thread_label.disagrees && h('div', {class: 'decide'}, h('span', {class: 'lbl'}, 'Outcome disagreement'),
      segmented(adj.thread_label.decision, DECISIONS, v => { adj.thread_label.decision = v; renderPanel(); }),
      adj.thread_label.decision === 'merged' && h('select', {onchange: e => { adj.thread_label.value = e.target.value; }}, h('option', {value: ''}, 'Adjudicated outcome…'), OUTCOMES.map(([v, t]) => h('option', {value: v, selected: adj.thread_label.value === v}, t))),
      h('input', {placeholder: 'Rationale', value: adj.thread_label.rationale, oninput: e => { adj.thread_label.rationale = e.target.value; }}))];
  out.splice(0, 0, h('div', {class: 'commit-bar'}, twoStep('adjudicate', latest ? 'Record new adjudication version' : 'Record adjudication', 'Confirm: record adjudication', async () => {
      try {
        const clean = r => r.decision === 'merged' ? r : {...r, merged: undefined};
        S.compare = await api('POST', `/api/packets/${encodeURIComponent(S.pid)}/adjudicate`, {...adj, episodes: adj.episodes.map(clean)});
        S.errors = []; S.confirm = null; S.view.status = 'adjudicated'; renderPacket(); toast('Adjudication recorded and exported. Originals unchanged.');
      } catch (e) { S.errors = e.errors && e.errors.length ? e.errors : [e.message]; S.confirm = null; renderPanel(); $('#panel').scrollTop = 0; }
    })),
    S.errors.length > 0 && h('ul', {class: 'error', role: 'alert'}, S.errors.map(e => h('li', null, e))));
  adj.episodes.forEach(row => {
    const hh = he.get(row.human_episode_id), aa = ae.get(row.ai_episode_id), pair = pairOf(row);
    const kind = hh && aa ? (pair.classification_disagrees || pair.evidence_disagrees ? 'Matched — with differences' : 'Matched — labels and evidence records agree') : hh ? 'Human-only episode' : 'AI-only episode';
    out.push(h('div', {class: 'match ' + (hh && aa ? 'both' : hh ? 'honly' : 'aonly')},
      h('div', {class: 'row'}, h('b', null, kind), h('span', {class: 'grow'}),
        hh && h('label', {class: 'small'}, 'Corresponds to AI episode ', h('select', {class: 'mini', onchange: e => realign(row, e.target.value)}, h('option', {value: ''}, 'none'),
          A.episodes.map((e, i) => h('option', {value: e.episode_id, selected: row.ai_episode_id === e.episode_id}, `E${i + 1}: ${e.workflow.slice(0, 40)}`))))),
      h('div', {class: 'pair'}, hh ? episodeSummary(hh[0], hh[1], 'human', pair) : h('div', {class: 'muted small'}, 'No corresponding human episode.'),
        aa ? episodeSummary(aa[0], aa[1], 'ai', pair) : h('div', {class: 'muted small'}, 'No corresponding AI episode.')),
      h('div', {class: 'decide'}, segmented(row.decision, DECISIONS, v => { row.decision = v; renderPanel(); }),
        h('input', {placeholder: 'Rationale (optional)', value: row.rationale, oninput: e => { row.rationale = e.target.value; }}),
        row.decision === 'merged' && h('div', {class: 'merged'}, h('p', {class: 'small muted'}, 'Merged episode: evidence from both sides is kept and tagged by origin. Set the adjudicated labels:'),
          field('Workflow', input(row.merged, 'workflow', {placeholder: (hh || aa)[0].workflow})),
          h('div', {class: 'cols'}, field('Need', select(row.merged, 'need_status', NEED)), field('Adoption', select(row.merged, 'adoption_status', ADOPTION)), field('Resolution', select(row.merged, 'resolution', RESOLUTION))),
          checks(row.merged, 'gap_labels', GAPS), field('Merge note', input(row.merged, 'note'))))));
  });
  if (!adj.episodes.length) out.push(h('p', {class: 'muted'}, 'Neither side recorded a new episode.'));
  if ((H.historical_episodes || []).length) out.push(h('h2', null, 'Human historical episodes'),
    h('p', {class: 'small muted'}, 'Recorded from earlier context only and not counted as new, so they are not paired or adjudicated. Compare them by eye with any AI episode built on the same records.'),
    H.historical_episodes.map((e, i) => episodeSummary(e, i, 'human')));
  out.push(h('h2', null, 'Adjudication'),
    latest && h('div', {class: 'notice ok'}, `Adjudication v${latest.version} recorded ${when(latest.recorded_at)}: ${latest.decision.rationale} `, h('span', {class: 'muted'}, 'Recording again adds a new version; earlier ones are kept.')),
    field('Overall rationale', h('textarea', {rows: 2, value: adj.rationale, oninput: e => { adj.rationale = e.target.value; }})));
  return out;
}

/* ---------- keyboard ---------- */
const HELP = [['j / k', 'Next / previous comment'], ['e', 'Link focused comment as evidence'], ['c', 'Collapse or expand focused branch'],
  ['x', 'Show additional thread context'], ['/', 'Search this thread'], ['a', 'Add episode'], ['1 – 4', 'Choose outcome'],
  ['Ctrl+Enter', 'Commit (press again to confirm)'], ['n / p', 'Next / previous packet'], ['q', 'Queue'], ['Esc', 'Leave a field / cancel'], ['?', 'This help']];
function toggleHelp() {
  const old = $('#help'); if (old) return old.remove();
  document.body.append(h('div', {id: 'help', class: 'card', onclick: toggleHelp}, h('h2', null, 'Keyboard shortcuts'),
    h('dl', null, HELP.map(([k, t]) => [h('dt', null, h('kbd', null, k)), h('dd', null, t)])), h('p', {class: 'small muted'}, 'Shortcuts are inactive while typing in a field.')));
}
function moveFocus(step) {
  const all = [...document.querySelectorAll('#thread article')]; if (!all.length) return;
  const i = all.findIndex(a => a.dataset.id === S.focus), next = all[Math.max(0, Math.min(all.length - 1, i < 0 ? 0 : i + step))];
  all.forEach(a => a.classList.remove('focus')); S.focus = next.dataset.id; next.classList.add('focus'); next.scrollIntoView({block: 'nearest'});
}
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { if ($('#help')) return toggleHelp(); if (S.pending) { S.pending = null; return renderPanel(); } if (S.confirm) { S.confirm = null; return renderPanel(); } if (typing()) document.activeElement.blur(); return; }
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && S.pid && S.editable && !S.compare) {
    e.preventDefault();
    if (S.confirm === 'commit') return commitReview();
    S.confirm = 'commit'; renderPanel(); const b = $('#confirm-go'); if (b) b.scrollIntoView({block: 'nearest'}); return;
  }
  if (typing() || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === '?') return toggleHelp();
  if (e.key === 'q') return go('#/queue');
  if (!S.pid) return;
  const k = e.key;
  if (k === 'n') neighbor(1); else if (k === 'p') neighbor(-1);
  else if (k === 'j') moveFocus(1); else if (k === 'k') moveFocus(-1);
  else if (k === '/') { e.preventDefault(); $('#search').focus(); }
  else if (k === 'x' && !S.contextOpen && S.tree.reg.secondary_record_ids.length) openContext();
  else if (k === 'c' && S.focus) { S.collapsed.has(S.focus) ? S.collapsed.delete(S.focus) : S.collapsed.add(S.focus); renderThread(); }
  else if (!S.editable || S.compare) return;
  else if (k === 'e' && S.focus) { const r = S.tree.byId.get(S.focus); if (r.text || r.title) { e.preventDefault(); startEvidence(S.focus); } }
  else if (k === 'a') { e.preventDefault(); addEpisode(); renderPanel(); }
  else if (/^[1-4]$/.test(k)) setOutcome(OUTCOMES[k - 1][0]);
});

route().catch(e => { $('#main').replaceChildren(h('p', {class: 'pad error'}, e.message)); });
