#!/usr/bin/env python3
"""Offline source-only review, immutable labels, gated AI reveal and adjudication."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import shutil
import tempfile

import pilot
import review_ui


def now():
    return datetime.now(timezone.utc).isoformat()


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')


@contextmanager
def lock(root):
    with (root / '.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def packet(root, pid):
    ps = pilot.read_jsonl(root / 'reviewer/packets.jsonl')
    found = [p for p in ps if p['packet_id'] == pid]
    if not found:
        raise ValueError('Unknown packet ID')
    return found[0]


def verify(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    for name, expected in manifest['source_files'].items():
        if pilot.digest((root / 'reviewer' / name).read_bytes()) != expected:
            raise ValueError(f'Reviewer source changed: {name}')
    if 'experiment_packets_sha256' in manifest and pilot.digest((root / 'private/experiment_packets.jsonl').read_bytes()) != manifest['experiment_packets_sha256']:
        raise ValueError('Experiment assignments changed')
    return manifest


def initialize(pilot_dir, root):
    pilot_dir, root = Path(pilot_dir), Path(root)
    original = json.loads((pilot_dir / 'manifest.json').read_text())
    for name, expected in original['output_sha256'].items():
        if pilot.digest((pilot_dir / name).read_bytes()) != expected:
            raise ValueError(f'Pilot artifact changed: {name}')
    root.mkdir(parents=True, exist_ok=False)
    reviewer = root / 'reviewer'
    reviewer.mkdir()
    # Regenerate only source-derived UI, never copy AI material or split metadata.
    experiment_packets = review_ui.build(pilot_dir, reviewer)
    forms = reviewer / 'forms'
    shutil.copyfile(Path(__file__).parent / 'research/HUMAN_REVIEW.md', reviewer / 'README.md')
    shutil.copyfile(Path(__file__).parent / 'research/HUMAN_REVIEW.md', reviewer / 'ANNOTATION_GUIDE.md')
    for name in ['private/ai', 'private/legacy', 'commits', 'comparisons', 'adjudications']:
        (root / name).mkdir(parents=True)
    pilot.write_jsonl(root / 'private/experiment_packets.jsonl', experiment_packets)
    files = {str(p.relative_to(reviewer)): pilot.digest(p.read_bytes())
             for p in reviewer.rglob('*') if p.is_file() and forms not in p.parents}
    manifest = {'protocol': 'blind-review-v2', 'created_at': now(),
                'pilot_manifest_sha256': pilot.digest((pilot_dir / 'manifest.json').read_bytes()),
                'experiment_assignments': {p['packet_id']: p['split'] for p in experiment_packets},
                'experiment_packets_sha256': pilot.digest((root / 'private/experiment_packets.jsonl').read_bytes()),
                'selector': {'policy': review_ui.POLICY, 'max_records': review_ui.MAX_RECORDS,
                             'max_source_characters': review_ui.MAX_CHARACTERS},
                'source_files': files, 'reference_status': 'single_reviewer_exploratory',
                'human_inter_annotator_agreement': 'not_established',
                'blinding': 'workflow separation, not an OS access-control boundary'}
    save_new(root / 'manifest.json', manifest)
    return {'reviewer_bundle': str(reviewer), 'packets': len(list(forms.iterdir()))}


def upgrade(pilot_dir, previous_root, root):
    """Create a fresh presentation version; never overwrite prior review work."""
    previous_root, root = Path(previous_root), Path(root)
    with lock(previous_root):
        old = verify(previous_root)
        if any((previous_root / 'commits').iterdir()):
            raise ValueError('Existing human commitments require a separate experiment, not migration')
        if old['pilot_manifest_sha256'] != pilot.digest((Path(pilot_dir) / 'manifest.json').read_bytes()):
            raise ValueError('Migration must use the same frozen pilot')
        blanks = {r['packet_id']: r for r in pilot.read_jsonl(previous_root / 'reviewer/annotation_template.jsonl')}
        for form in (previous_root / 'reviewer/forms').glob('*.json'):
            row = json.loads(form.read_text())
            if row != blanks.get(form.stem):
                raise ValueError('Human review work exists; preserve it in a separate experiment')
        result = initialize(pilot_dir, root)
        seals = {}
        for src in (previous_root / 'private/ai').glob('*.json'):
            row = json.loads(src.read_text())['annotation']
            checked_annotation(root, row, 'ai_provisional')
            shutil.copyfile(src, root / 'private/ai' / src.name)
            seals[src.name] = pilot.digest(src.read_bytes())
        save_new(root / 'private/migration.json', {
            'previous_manifest_sha256': pilot.digest((previous_root / 'manifest.json').read_bytes()),
            'sealed_ai_sha256': seals, 'human_labels_migrated': 0,
            'ai_context': 'Original full-retained-thread drafts, not bounded-region model runs',
            'created_at': now()})
        return dict(result, preserved_ai_seals=len(seals))


def checked_annotation(root, row, kind):
    if not isinstance(row, dict):
        raise ValueError('Annotation must be a JSON object')
    packet(root, row.get('packet_id'))
    if row.get('status') != 'reviewed' or row.get('reviewer_kind') != kind:
        raise ValueError(f'Expected completed {kind} annotation')
    # Existing schema/span checks; no semantics or labels are generated here.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'row.jsonl'
        pilot.write_jsonl(path, [row])
        result = pilot.validate(root / 'reviewer', path,
                                packet_metadata=root / 'private/experiment_packets.jsonl'
                                if (root / 'private/experiment_packets.jsonl').exists() else None)
    if not result['valid']:
        raise ValueError('; '.join(result['errors']))


def seal_ai(root, annotations, provenance):
    root = Path(root)
    rows = pilot.read_jsonl(annotations)
    meta = json.loads(Path(provenance).read_text())
    if not isinstance(meta, dict) or not meta:
        raise ValueError('Nonempty AI provenance is required')
    with lock(root):
        verify(root)
        ids = set()
        for row in rows:
            checked_annotation(root, row, 'ai_provisional')
            pid = row['packet_id']
            if pid in ids or (root / 'private/ai' / (pid + '.json')).exists():
                raise ValueError('Duplicate/already sealed AI packet')
            if (root / 'commits' / (pid + '.json')).exists():
                raise ValueError('AI result must be sealed before human commitment for a blind comparison')
            ids.add(pid)
        for row in rows:
            save_new(root / 'private/ai' / (row['packet_id'] + '.json'),
                     {'sealed_at': now(), 'annotation': row, 'provenance': meta})
    return {'sealed_packets': len(rows)}


def commit(root, annotation, exposure):
    root = Path(root)
    row = json.loads(Path(annotation).read_text())
    if exposure not in {'none', 'prior_summary', 'ai_annotation'}:
        raise ValueError('Explicit exposure disclosure required')
    with lock(root):
        verify(root)
        kind = 'human_assisted' if exposure == 'ai_annotation' else 'human_independent'
        checked_annotation(root, row, kind)
        pid = row['packet_id']
        if verify(root)['protocol'] == 'blind-review-v2':
            review_ui.validate_burden(row, packet(root, pid))
        if (root / 'comparisons' / (pid + '.json')).exists():
            raise ValueError('Comparison already revealed; initial label cannot be recommitted')
        ai = root / 'private/ai' / (pid + '.json')
        result = {'committed_at': now(), 'annotation': row, 'exposure_disclosure': exposure,
                  'reference_status': 'single_reviewer_exploratory',
                  'ai_sha256_at_commit': pilot.digest(ai.read_bytes()) if ai.exists() else None,
                  'source_manifest_sha256': pilot.digest((root / 'manifest.json').read_bytes()),
                  'independence': 'self_reported_no_prior_ai_exposure' if exposure == 'none'
                  else 'prior_exposure_disclosed'}
        save_new(root / 'commits' / (pid + '.json'), result)
    return {'packet_id': pid, 'committed': True, 'ai_revealed': False,
            'reference_status': 'single_reviewer_exploratory'}


def reveal(root, pid):
    root = Path(root)
    with lock(root):
        verify(root)
        packet(root, pid)
        human_path = root / 'commits' / (pid + '.json')
        if not human_path.exists():
            raise ValueError('Commit the human label before revealing AI')
        human = json.loads(human_path.read_text())
        ai_path = root / 'private/ai' / (pid + '.json')
        if not human['ai_sha256_at_commit']:
            raise ValueError('No AI result was sealed at commitment; no blind paired comparison is available')
        if pilot.digest(ai_path.read_bytes()) != human['ai_sha256_at_commit']:
            raise ValueError('Sealed AI annotation changed')
        ai = json.loads(ai_path.read_text())
        dest = root / 'comparisons' / (pid + '.json')
        if dest.exists():
            existing = json.loads(dest.read_text())
            if existing['human_commit_sha256'] != pilot.digest(human_path.read_bytes()):
                raise ValueError('Human commitment changed after reveal')
            return existing
        h, a = human['annotation'], ai['annotation']
        result = {'packet_id': pid, 'revealed_at': now(), 'human_commit': human, 'ai_result': ai,
                  'human_commit_sha256': pilot.digest(human_path.read_bytes()),
                  'ai_sha256': pilot.digest(ai_path.read_bytes()),
                  'differences': {'thread_label': {'human': h['thread_label'], 'ai': a['thread_label'],
                                                  'disagrees': h['thread_label'] != a['thread_label']},
                                  'episode_count': {'human': len(h['episodes']), 'ai': len(a['episodes'])},
                                  'episode_alignment': 'requires_explicit_review_not_positional_matching'},
                  'adjudication_status': 'pending', 'reference_status': 'single_reviewer_exploratory'}
        save_new(dest, result)
        return result


def adjudicate(root, pid, decision):
    root = Path(root)
    data = json.loads(Path(decision).read_text())
    if not isinstance(data, dict) or not data.get('reviewer_id') or not data.get('rationale'):
        raise ValueError('Adjudication requires reviewer_id and rationale')
    if not isinstance(data.get('disagreements'), list):
        raise ValueError('Adjudication requires an explicit disagreements list (empty if none)')
    for item in data['disagreements']:
        if not isinstance(item, dict) or not all(k in item for k in ['dimension', 'human', 'ai', 'decision', 'rationale']):
            raise ValueError('Each disagreement needs dimension, human, ai, decision, rationale')
    with lock(root):
        verify(root)
        packet(root, pid)
        comparison = root / 'comparisons' / (pid + '.json')
        if not comparison.exists():
            raise ValueError('Reveal the comparison before adjudicating')
        reveal_data = json.loads(comparison.read_text())
        if reveal_data['differences']['thread_label']['disagrees'] and not any(
                x['dimension'] == 'thread_label' for x in data['disagreements']):
            raise ValueError('Record the observed thread-label disagreement')
        if not isinstance(data.get('episode_alignment'), list):
            raise ValueError('Explicit episode_alignment list required, including unmatched episodes')
        result = {'packet_id': pid, 'recorded_at': now(), 'decision': data,
                  'comparison_sha256': pilot.digest(comparison.read_bytes()),
                  'originals_preserved': True, 'reference_status': 'single_reviewer_exploratory'}
        save_new(root / 'adjudications' / (pid + '.json'), result)
    return {'packet_id': pid, 'adjudication_recorded': True, 'originals_preserved': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('init'); p.add_argument('pilot_dir'); p.add_argument('root')
    p = sub.add_parser('upgrade'); p.add_argument('pilot_dir'); p.add_argument('previous_root'); p.add_argument('root')
    p = sub.add_parser('seal-ai'); p.add_argument('root'); p.add_argument('annotations'); p.add_argument('provenance')
    p = sub.add_parser('commit'); p.add_argument('root'); p.add_argument('annotation')
    p.add_argument('--exposure', required=True, choices=['none', 'prior_summary', 'ai_annotation'])
    p = sub.add_parser('reveal'); p.add_argument('root'); p.add_argument('pid')
    p = sub.add_parser('adjudicate'); p.add_argument('root'); p.add_argument('pid'); p.add_argument('decision')
    args = vars(parser.parse_args()); command = args.pop('command')
    function = {'init': initialize, 'upgrade': upgrade, 'seal-ai': seal_ai, 'commit': commit, 'reveal': reveal, 'adjudicate': adjudicate}[command]
    try:
        print(json.dumps(function(**args), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    main()
