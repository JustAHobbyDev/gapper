/* Local, source-only review. No AI access, network, or label commitment. */
'use strict';
const data = JSON.parse(document.getElementById('review-data').textContent);
const el = id => document.getElementById(id);
const key = 'gapper-review-v2:' + data.packet_id + ':' + JSON.stringify(data.region);
let state = {draft: JSON.stringify(data.form, null, 2), outcome: '', sufficiency: '',
  expanded: [], contextOpened: false, seconds: 0, external: false, allRead: false};
try {
  const saved = localStorage.getItem(key);
  if (saved) state = {...state, ...JSON.parse(saved)};
  el('storage-status').textContent = 'Draft and expansion history are saved locally in this browser when storage is available.';
} catch (_) {
  el('storage-status').textContent = 'Browser storage unavailable. Download your draft before closing; otherwise timing and expansion history may be lost.';
}
el('annotation').value = state.draft;
el('outcome').value = state.outcome;
el('sufficiency').value = state.sufficiency;
el('external').checked = state.external;
el('all-read').checked = state.allRead;
let last = performance.now();
let wasVisible = !document.hidden;
function tick() {
  const t = performance.now();
  if (wasVisible) state.seconds += (t - last) / 1000;
  last = t;
  wasVisible = !document.hidden;
}
function save() {
  tick();
  state.draft = el('annotation').value;
  state.outcome = el('outcome').value;
  state.sufficiency = el('sufficiency').value;
  state.external = el('external').checked;
  state.allRead = el('all-read').checked;
  try { localStorage.setItem(key, JSON.stringify(state)); }
  catch (_) { el('storage-status').textContent = 'Cannot save to browser storage. Download before closing.'; }
  el('burden').textContent = 'Extra context ever opened: ' + (state.contextOpened || state.expanded.length > 0 || state.external ? 'yes' : 'no') +
    '; expanded records: ' + state.expanded.length + '; visible-page seconds: ' + Math.round(state.seconds);
}
el('secondary-context').addEventListener('toggle', () => {
  if (el('secondary-context').open) state.contextOpened = true;
  save();
});
document.querySelectorAll('details[data-record]').forEach(node => {
  node.addEventListener('toggle', () => {
    if (node.open && !state.expanded.includes(node.dataset.record)) state.expanded.push(node.dataset.record);
    save();
  });
});
['annotation', 'outcome', 'sufficiency', 'external', 'all-read'].forEach(id => el(id).addEventListener('input', save));
document.addEventListener('visibilitychange', save);
window.addEventListener('pagehide', save);
setInterval(save, 5000);
el('download').addEventListener('click', () => {
  try {
    if (el('secondary-context').open) state.contextOpened = true;
    // Include open details even if their queued toggle events have not run yet.
    document.querySelectorAll('details[data-record]').forEach(node => {
      if (node.open && !state.expanded.includes(node.dataset.record)) state.expanded.push(node.dataset.record);
    });
    save();
    const row = JSON.parse(state.draft);
    if (row.packet_id !== data.packet_id) throw Error('Do not change the packet ID.');
    if (!row.reviewer_id || !state.outcome || !state.sufficiency) throw Error('Enter reviewer_id, outcome, and context sufficiency.');
    if (!Array.isArray(row.episodes)) throw Error('episodes must be an array.');
    if (state.outcome === 'has_candidate' && !row.episodes.length) throw Error('Add the candidate episodes before downloading.');
    if (['no_candidate', 'insufficient_evidence'].includes(state.outcome) && row.episodes.length) throw Error('This outcome requires an empty episodes list.');
    const extra = state.contextOpened || state.expanded.length > 0 || state.external;
    if (state.sufficiency === 'needed_extra' && !extra) throw Error('Disclose or open the extra context used.');
    const expandable = [...data.region.secondary_record_ids, ...data.region.clipped_record_ids];
    if (state.allRead && expandable.some(id => !state.expanded.includes(id))) throw Error('Some retained text has not been expanded. Leave all-retained review unchecked or record external review manually in the downloaded form.');
    row.status = 'reviewed';
    row.reviewer_kind = row.reviewer_kind || 'human_independent';
    row.thread_label = state.outcome;
    row.review_burden = {...data.form.review_burden, extra_context_opened: extra,
      expanded_record_ids: [...state.expanded].sort(), context_sufficiency: state.sufficiency,
      visible_page_seconds: Math.round(state.seconds), measurement_method: 'browser_visible_time',
      review_scope: state.allRead ? 'all_retained' : extra ? 'expanded_partial' : 'primary_only'};
    const blob = new Blob([JSON.stringify(row, null, 2) + '\n'], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = data.packet_id + '.json';
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    el('error').textContent = 'Downloaded. Validate and commit this file with the CLI; no AI result has been revealed.';
  } catch (error) { el('error').textContent = error.message; }
});
save();
