#!/usr/bin/env python3
"""Offline integrity checks of an acquired run; does not claim source completeness."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import gapper


def verify(root):
    root = Path(root)
    report = json.loads((root / 'report.json').read_text())
    start, end = (gapper.parse_time(report['window'][k]) for k in ['start', 'end'])
    all_records, errors, archives = {}, [], {}
    counts = {}
    for scope in ['sample', 'context']:
        path = root / (scope + '.jsonl')
        records = [json.loads(line) for line in path.read_text().splitlines()]
        counts[scope] = len(records)
        if records != gapper.chronological(records):
            errors.append(f'{scope}: unsorted or duplicate records')
        if hashlib.sha256(path.read_bytes()).hexdigest() != report['artifacts'][path.name]['sha256']:
            errors.append(f'{scope}: artifact checksum mismatch')
        for r in records:
            key = r['source'], r['native_id']
            if key in all_records:
                errors.append(f'{key}: duplicated across scopes')
            all_records[key] = r
            if r['scope'] != scope:
                errors.append(f'{key}: scope label mismatch')
            inside = gapper.in_window(r['created_at'], start, end)
            if inside != (scope == 'sample'):
                errors.append(f'{key}: wrong time window')
            ref = r['response_ref']
            if ref not in archives:
                with gzip.open(root / ref, 'rt') as f:
                    archives[ref] = json.load(f)
            envelope = archives[ref]
            if not envelope['ok'] or r['retrieved_at'] != envelope['retrieved_at']:
                errors.append(f'{key}: retrieval provenance mismatch')
            payload = envelope['payload']
            if r['source'] == 'hacker_news':
                original = payload
            else:
                posts = payload.get('latest_posts', payload.get('post_stream', {}).get('posts', []))
                original = next((p for p in posts if str(p['id']) == r['native_id']), None)
            if original != r['source_native']:
                errors.append(f'{key}: native payload mismatch')
    missing_parents = [key for key, r in all_records.items() if r.get('parent_id')
                       and (r['source'], r['parent_id']) not in all_records]
    for source, info in report['sources'].items():
        for scope in ['sample', 'context']:
            records = [r for r in all_records.values() if r['source'] == source and r['scope'] == scope]
            if gapper.summary(records) != info[scope]:
                errors.append(f'{source}/{scope}: report counts mismatch')
    return {'counts': counts, 'verified_response_archives': len(archives),
            'missing_referenced_parents': missing_parents, 'integrity_errors': errors}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    result = verify(args.run)
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result['integrity_errors']))
