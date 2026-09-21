/* Exercise the offline UI event protocol in a minimal DOM; not a visual browser test. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('research/review.js', 'utf8');
function setup(storage = new Map()) {
  let time = 0, interval, output;
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {value: '', textContent: '', checked: false, open: false,
      listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; }});
    return elements.get(id);
  }
  const data = {packet_id: 'p', form: {packet_id: 'p', reviewer_id: null, episodes: [],
    review_burden: {initial_record_count: 1, initial_characters: 12}},
    region: {secondary_record_ids: ['2'], clipped_record_ids: ['1']}};
  element('review-data').textContent = JSON.stringify(data);
  const details = ['1', '2'].map(id => ({...element('record' + id), dataset: {record: id}}));
  const document = {hidden: false, getElementById: element, querySelectorAll: () => details,
    listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; },
    createElement: () => ({click() {}})};
  class FakeBlob { constructor(parts) { output = JSON.parse(parts.join('')); } }
  const context = vm.createContext({document, window: {addEventListener() {}},
    performance: {now: () => time}, localStorage: {getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v)},
    Blob: FakeBlob, URL: {createObjectURL: () => 'local', revokeObjectURL() {}},
    setTimeout: fn => fn(), setInterval: fn => { interval = fn; }});
  vm.runInContext(source, context);
  return {element, document, details, storage, advance(ms) { time += ms; interval(); },
    download() { element('download').listeners.click(); return output; }};
}
let page = setup();
let row = JSON.parse(page.element('annotation').value);
row.reviewer_id = 'human'; page.element('annotation').value = JSON.stringify(row);
page.element('outcome').value = 'insufficient_evidence';
page.element('sufficiency').value = 'still_insufficient';
page.advance(10000);
page.document.hidden = true; page.document.listeners.visibilitychange();
page.advance(90000);
page.document.hidden = false; page.document.listeners.visibilitychange();
page.advance(5000);
page.element('secondary-context').open = true;
page.element('secondary-context').listeners.toggle();
page.element('secondary-context').open = false;
page.element('secondary-context').listeners.toggle();
page.details[1].open = true; page.details[1].listeners.toggle();
page.details[1].open = false; page.details[1].listeners.toggle();
let result = page.download();
assert.equal(result.thread_label, 'insufficient_evidence');
assert.equal(result.review_burden.visible_page_seconds, 15);
assert.equal(result.review_burden.extra_context_opened, true);
assert.deepEqual(result.review_burden.expanded_record_ids, ['2']);
assert.equal(result.review_burden.review_scope, 'expanded_partial');
page = setup(page.storage);
page.advance(2000);
result = page.download();
assert.equal(result.review_burden.visible_page_seconds, 17);
assert.deepEqual(result.review_burden.expanded_record_ids, ['2']);
page.element('all-read').checked = true;
page.download();
assert.match(page.element('error').textContent, /has not been expanded/);
page.details[0].open = true; // Must count even before the toggle callback runs.
result = page.download();
assert.equal(result.review_burden.review_scope, 'all_retained');
assert.deepEqual(result.review_burden.expanded_record_ids, ['1', '2']);
assert.equal(result.status, 'reviewed');
assert.equal(result.reviewer_kind, 'human_independent');
console.log('Offline review events passed: expansion persistence, reload, timing, download, coverage.');
