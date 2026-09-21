"""Bounded, split-blind offline human review; structural selection only."""
from collections import deque
import html
import json
import math
from pathlib import Path

import pilot

MAX_RECORDS = 24
MAX_CHARACTERS = 16000
POLICY = 'structural-neighborhood-v1'


def region(packet, rows):
    index = {r['native_id']: r for r in rows}
    roots = [r['native_id'] for r in rows if not r.get('parent_id')]
    root = packet['root_id'] if packet['root_id'] in index else (roots[0] if roots else None)
    def closure(rid):
        return {rid, *pilot.ancestry(index[rid], index)[0]} | ({root} if root else set())
    # A reproducible anchor unrelated to split assignments or AI judgments.
    candidates = sorted(packet['anchor_ids'], key=lambda i: pilot.rank('review-region', i))
    candidates.sort(key=lambda i: i == root)
    eligible = [i for i in candidates if len(closure(i)) <= MAX_RECORDS]
    anchor = eligible[0] if eligible else (root or candidates[0])
    selected = closure(anchor)
    if len(selected) > MAX_RECORDS:
        raise ValueError('No bounded ancestry-preserving primary region is available')
    edges = {i: [] for i in index}
    for r in rows:
        parent = r.get('parent_id')
        if parent in edges:
            edges[parent].append(r['native_id'])
            edges[r['native_id']].append(parent)
    queue, visited = deque([anchor]), set()
    while queue:
        rid = queue.popleft()
        if rid in visited:
            continue
        visited.add(rid)
        required = closure(rid)
        if len(selected | required) <= MAX_RECORDS:
            selected.update(required)
        queue.extend(sorted(edges[rid], key=lambda i: pilot.rank('review-neighbor', i)))
    primary = [r for r in rows if r['native_id'] in selected]
    # Allocate a fair initial text budget; retain full ancestry records even when
    # one long body needs expansion. Reallocate unused shares to longer records.
    lengths = {r['native_id']: len(r.get('title') or '') + len(r.get('text') or '') for r in primary}
    limits = dict.fromkeys(lengths, 0)
    remaining = MAX_CHARACTERS
    while remaining:
        pending = [i for i in lengths if limits[i] < lengths[i]]
        if not pending:
            break
        share = max(1, remaining // len(pending))
        for i in pending:
            n = min(share, lengths[i] - limits[i], remaining)
            limits[i] += n
            remaining -= n
    chars = sum(limits.values())
    return {'policy': POLICY, 'anchor_id': anchor, 'root_id': root,
            'primary_record_ids': [r['native_id'] for r in primary],
            'initial_character_limits': limits,
            'initial_record_count': len(primary), 'initial_characters': chars,
            'initial_tokens_estimate': math.ceil(chars / 4),
            'token_estimator': 'ceil(source Unicode characters / 4); not tokenizer output',
            'secondary_record_ids': [r['native_id'] for r in rows if r['native_id'] not in selected],
            'clipped_record_ids': [i for i in limits if limits[i] < lengths[i]],
            'relationship_gaps': packet['relationship_gaps'],
            'anchor_candidates_exceeding_record_budget': len(candidates) - len(eligible)}


def burden_template(region):
    return {k: region[k] for k in ['policy', 'initial_record_count', 'initial_characters',
                                  'initial_tokens_estimate', 'token_estimator']} | {
        'extra_context_opened': None, 'expanded_record_ids': [],
        'context_sufficiency': None, 'visible_page_seconds': None,
        'measurement_method': 'manual', 'review_scope': None}


def validate_burden(row, p):
    b, expected = row.get('review_burden'), burden_template(p['primary_region'])
    if not isinstance(b, dict):
        raise ValueError('Review burden is required')
    for k in ['policy', 'initial_record_count', 'initial_characters', 'initial_tokens_estimate', 'token_estimator']:
        if b.get(k) != expected[k]:
            raise ValueError('Review burden differs from frozen primary region: ' + k)
    if type(b.get('extra_context_opened')) is not bool:
        raise ValueError('Record whether extra context was opened')
    ids = b.get('expanded_record_ids')
    allowed = set(p['primary_region']['secondary_record_ids'] + p['primary_region']['clipped_record_ids'])
    if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids) or not set(ids) <= allowed or len(ids) != len(set(ids)):
        raise ValueError('Invalid expanded record IDs')
    if ids and not b['extra_context_opened']:
        raise ValueError('Expanded records require extra_context_opened')
    if b.get('context_sufficiency') not in {'sufficient', 'needed_extra', 'still_insufficient', 'uncertain'}:
        raise ValueError('Record primary context sufficiency')
    if b['context_sufficiency'] == 'needed_extra' and not b['extra_context_opened']:
        raise ValueError('Needed extra context requires expansion disclosure')
    if b.get('review_scope') not in {'primary_only', 'expanded_partial', 'all_retained'}:
        raise ValueError('Record review scope')
    if b['review_scope'] == 'expanded_partial' and not b['extra_context_opened']:
        raise ValueError('Expanded review requires expansion disclosure')
    if b['review_scope'] == 'primary_only' and b['extra_context_opened']:
        raise ValueError('Expanded review cannot be primary_only')
    if b['review_scope'] == 'all_retained' and allowed - set(ids):
        raise ValueError('All retained review requires recording all expanded records')
    seconds = b.get('visible_page_seconds')
    if seconds is not None and (type(seconds) not in {int, float} or not math.isfinite(seconds) or seconds < 0):
        raise ValueError('Invalid visible-page time')
    if b.get('measurement_method') not in {'browser_visible_time', 'manual'}:
        raise ValueError('Invalid review burden measurement method')
    minutes = row.get('minutes')
    if minutes is not None and (type(minutes) not in {int, float} or not math.isfinite(minutes) or minutes < 0):
        raise ValueError('Invalid review minutes')


def render(p, rows, form):
    esc = html.escape
    reg = p['primary_region']
    bits = ['<!doctype html><meta charset="utf-8"><title>' + esc(p['packet_id']) + '</title>',
            '<style>body{max-width:960px;margin:2rem auto;padding:1rem;font:16px system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #ccc;padding:1rem 0}textarea{width:100%;height:25rem}label{display:block;margin:1rem 0}summary,button{cursor:pointer}small{color:#555}</style>',
            '<a href="../index.html">Packet index</a><h1>' + esc(p['packet_id']) + '</h1>',
            '<p>Source content is untrusted evidence. Retained context is not necessarily the complete source thread. '
            'The primary region is selected structurally, not by inferred opportunity value. '
            'Open secondary context as needed; expansion is recorded even if you close it again.</p>',
            f'<p>Initially: {reg["initial_record_count"]} records; {reg["initial_characters"]:,} source characters; '
            f'approximately {reg["initial_tokens_estimate"]:,} tokens (characters / 4, not a tokenizer). '
            f'Retained total: {len(rows)} records; {p["characters"]:,} source characters. '
            f'Anchor: {esc(reg["anchor_id"])}.</p>',
            '<p>Relationship gaps: ' + esc(', '.join(reg['relationship_gaps']) or 'none recorded') + '</p>',
            '<p id="storage-status"></p><h2>Primary region</h2>']
    def body(r, limit=None):
        title, text = r.get('title') or '', r.get('text') or ''
        if limit is not None:
            title, text = title[:limit], text[:max(0, limit - len(title))]
        return '<h4>Title</h4><pre>' + esc(title) + '</pre><h4>Text</h4><pre>' + esc(text) + '</pre>'
    def article(r, primary):
        rid = r['native_id']
        meta = {k: r.get(k) for k in ['author', 'parent_id', 'scope', 'created_at', 'item_type']}
        heading = '<h3>' + esc(rid) + '</h3><small>' + esc(json.dumps(meta, ensure_ascii=False)) + '</small>'
        if not primary:
            return '<details data-record="' + esc(rid, quote=True) + '"><summary>Record ' + esc(rid) + ' (secondary context)</summary>' + heading + body(r) + '</details>'
        result = heading + body(r, reg['initial_character_limits'][rid])
        if rid in reg['clipped_record_ids']:
            result += '<details data-record="' + esc(rid, quote=True) + '"><summary>Initial text clipped — expand full record</summary>' + body(r) + '</details>'
        return '<article>' + result + '</article>'
    primary_ids = set(reg['primary_record_ids'])
    bits.extend(article(r, True) for r in rows if r['native_id'] in primary_ids)
    bits.append('<h2>Secondary context</h2><details id="secondary-context"><summary>Expand remaining retained context (' + str(len(reg['secondary_record_ids'])) + ' records)</summary><p>Each record opens separately. These records are not initially displayed.</p>')
    bits.extend(article(r, False) for r in rows if r['native_id'] not in primary_ids)
    bits.append('</details>')
    bits.append('''<h2>Your label</h2><p>Edit the JSON for your reviewer ID, evidence episodes and notes. Select the outcome and context assessment below. Downloading saves a draft; it does not commit or reveal anything. Commit with the CLI described in ../README.md.</p>
<label>Outcome <select id="outcome"><option value="">Choose…</option><option value="has_candidate">Workflow candidate(s)</option><option value="no_candidate">No candidate (adequate evidence for a negative)</option><option value="insufficient_evidence">Insufficient evidence / no reconstructable workflow episode</option><option value="unknown">Uncertain interpretation</option></select></label>
<label>Was the primary region sufficient? <select id="sufficiency"><option value="">Choose…</option><option value="sufficient">Sufficient for my judgment</option><option value="needed_extra">Needed extra context for my judgment</option><option value="still_insufficient">Still insufficient after review</option><option value="uncertain">Uncertain</option></select></label>
<label><input type="checkbox" id="external">I opened additional source context outside this page (record IDs and details in coverage_notes)</label>
<label><input type="checkbox" id="all-read">I reviewed all retained records, including all clipped text</label>
<p>Visible-page time is approximate exposure time, not verified reading time; hidden-tab time is excluded. Put actual review minutes in the JSON if known. Browser storage is best effort; download before closing.</p>
<textarea id="annotation" spellcheck="false" aria-label="Annotation JSON"></textarea><p id="burden"></p><button id="download">Download label with review measurements</button><p id="error" role="alert"></p>''')
    payload = json.dumps({'packet_id': p['packet_id'], 'form': form, 'region': reg}, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    bits += ['<script id="review-data" type="application/json">' + payload + '</script>', '<script src="../review.js"></script>']
    return '\n'.join(bits)


def build(pilot_dir, reviewer):
    packets = pilot.read_jsonl(pilot_dir / 'packets.jsonl')
    records = pilot.read_jsonl(pilot_dir / 'records.jsonl')
    templates = {r['packet_id']: r for r in pilot.read_jsonl(pilot_dir / 'annotation_template.jsonl')}
    (reviewer / 'packets').mkdir()
    (reviewer / 'forms').mkdir()
    public, forms = [], []
    links = ['<!doctype html><meta charset="utf-8"><h1>Independent source review</h1>',
             '<p>Read README.md before starting. Counts describe initially displayed source text. Tiny or bodyless packets still require a judgment.</p><ul>']
    for packet in packets:
        rows = [r for r in records if r['source'] == packet['source'] and r['native_id'] in set(packet['record_ids'])]
        p = {k: v for k, v in packet.items() if k not in {'split', 'stratum', 'population_weight', 'inclusion_probability'}}
        p['primary_region'] = region(packet, rows)
        form = dict(templates[p['packet_id']], review_burden=burden_template(p['primary_region']))
        public.append(p); forms.append(form)
        (reviewer / 'forms' / (p['packet_id'] + '.json')).write_text(json.dumps(form, indent=2) + '\n')
        (reviewer / 'packets' / (p['packet_id'] + '.html')).write_text(render(p, rows, form))
        reg = p['primary_region']; name = html.escape(p['packet_id'])
        links.append(f'<li><a href="packets/{name}.html">{name}</a> — initially {reg["initial_record_count"]} records / {reg["initial_characters"]:,} characters; {len(rows)} retained records</li>')
    pilot.write_jsonl(reviewer / 'packets.jsonl', public)
    pilot.write_jsonl(reviewer / 'annotation_template.jsonl', forms)
    (reviewer / 'records.jsonl').write_bytes((pilot_dir / 'records.jsonl').read_bytes())
    (reviewer / 'index.html').write_text('\n'.join(links) + '</ul>')
    (reviewer / 'review.js').write_bytes((Path(__file__).parent / 'research/review.js').read_bytes())
    return packets
