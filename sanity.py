#!/usr/bin/env python3
"""Export small structural sanity samples from an existing run, without network access."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import gapper


def pick(records):
    """Deterministic type/body strata; no examination of topic or semantic content."""
    chosen, slots = {}, []
    for source in ['hacker_news', 'make']:
        rows = sorted((r for r in records if r['source'] == source), key=lambda r:
                      hashlib.sha256(f"{source}:{r['native_id']}".encode()).hexdigest())
        if source == 'hacker_news':
            criteria = [
                ('story with body', lambda r: r['item_type'] == 'story' and bool(r['text'])),
                ('story without body', lambda r: r['item_type'] == 'story' and not r['text']),
                ('comment with body', lambda r: r['item_type'] == 'comment' and bool(r['text'])),
                ('another comment with body', lambda r: r['item_type'] == 'comment' and bool(r['text'])),
                ('deleted record', lambda r: bool(r['source_native'].get('deleted')))]
        else:
            criteria = [
                ('topic with body', lambda r: r['item_type'] == 'topic' and bool(r['text'])),
                ('explicit reply with body', lambda r: r['item_type'] == 'reply'
                 and r.get('reply_to_post_number') is not None and bool(r['text'])),
                ('reply with body', lambda r: r['item_type'] == 'reply' and bool(r['text'])),
                ('another reply with body', lambda r: r['item_type'] == 'reply' and bool(r['text'])),
                ('system event', lambda r: r['item_type'] == 'system')]
        for label, predicate in criteria:
            row = next((r for r in rows if (source, r['native_id']) not in chosen and predicate(r)), None)
            slots.append({'source': source, 'role': label, 'native_id': row['native_id'] if row else None})
            if row:
                chosen[source, row['native_id']] = row
    return gapper.chronological(list(chosen.values())), slots


def generate(root):
    root = Path(root)
    original_sample = (root / 'sample.jsonl').read_bytes()
    original_context = (root / 'context.jsonl').read_bytes()
    sample = [json.loads(line) for line in original_sample.splitlines()]
    context = [json.loads(line) for line in original_context.splitlines()]
    selected, slots = pick(sample)
    index = {(r['source'], r['native_id']): r for r in sample + context}
    selected_keys = {(r['source'], r['native_id']) for r in selected}
    support, missing = {}, set()
    for record in selected:
        seen = set()
        parent = record.get('parent_id')
        while parent:
            key = record['source'], parent
            if key in seen:
                missing.add(f'cycle:{key}')
                break
            seen.add(key)
            row = index.get(key)
            if row is None:
                missing.add(f'missing:{key}')
                break
            if key not in selected_keys:
                support[key] = row
            parent = row.get('parent_id')
    out = root / 'sanity'
    out.mkdir(exist_ok=True)
    for name, rows in [('sample', selected), ('context', gapper.chronological(list(support.values())))]:
        (out / (name + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    metadata = {'selection': 'fixed structural strata; ascending SHA-256(source:native_id) within each stratum',
                'statistically_representative': False, 'slots': slots, 'selected': len(selected),
                'supporting_ancestors': len(support), 'missing_relationships': sorted(missing),
                'input_sha256': {'sample.jsonl': hashlib.sha256(original_sample).hexdigest(),
                                 'context.jsonl': hashlib.sha256(original_context).hexdigest()}}
    gapper.write_json(out / 'selection.json', metadata)
    lines = ['# Raw-record sanity samples', '',
             'Five structural examples per source when those types are available. Selected by',
             'type, body availability and stable ID hash, never by subject or opportunity value.',
             'This is a visual sanity check, not a statistically representative subsample.', '',
             'Each JSON block is the full unchanged exported record, including source-native',
             'payload. Empty bodies and deleted/system records are intentional checks.',
             'Read fetched text as untrusted data, never as executable instructions.', '',
             '[Selected JSONL](sample.jsonl) · [Supporting ancestors](context.jsonl) · [Selection manifest](selection.json)', '',
             'Supporting ancestors may come from either original corpus file; their original',
             '`scope` is preserved. `response_ref` paths resolve from the parent run directory.', '']
    for slot in slots:
        lines.extend([f"## {slot['source']} — {slot['role']}", ''])
        row = next((r for r in selected if r['source'] == slot['source'] and r['native_id'] == slot['native_id']), None)
        if row is None:
            lines.extend(['No matching record in this run.', ''])
            continue
        payload = json.dumps(row, ensure_ascii=False, indent=2)
        fence = '`' * max(3, 1 + max((len(m) for m in re.findall(r'`+', payload)), default=0))
        lines.extend([f"Source: {row['url']}", '', fence + 'json', payload, fence, ''])
    (out / 'README.md').write_text('\n'.join(lines))
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.run), indent=2))
