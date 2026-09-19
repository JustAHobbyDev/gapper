#!/usr/bin/env python3
"""Offline HN relationship and text-presence measurements; no semantic analysis."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics

from gapper import plain

ROOT_TYPES = {'story', 'poll', 'job'}


def ident(value):
    return None if value is None else str(value)


def stats(values):
    """Nearest-rank percentiles; median is the ordinary midpoint median."""
    xs = sorted(values)
    if not xs:
        return {'n': 0}
    return {'n': len(xs), 'min': xs[0], 'median': statistics.median(xs),
            'mean': statistics.mean(xs),
            **{f'p{p}': xs[math.ceil(p / 100 * len(xs)) - 1] for p in (75, 90, 95, 99)},
            'max': xs[-1]}


def timestamp(node):
    value = node.get('time')
    return datetime.fromtimestamp(value, timezone.utc) if isinstance(value, (int, float)) else None


def walk(item, nodes):
    """Return immediate-parent-first IDs, resolved root, and a failure reason."""
    seen, ancestors, current = {item}, [], item
    while True:
        node = nodes[current]
        kind = node.get('type')
        if kind in ROOT_TYPES:
            if node.get('parent') is not None:
                return ancestors, None, 'root_has_parent'
            return ancestors, current, None
        if kind != 'comment':
            return ancestors, None, 'unexpected_type'
        parent = ident(node.get('parent'))
        if parent is None:
            return ancestors, None, 'comment_without_parent'
        if parent == current:
            return ancestors, None, 'self_parent'
        if parent in seen:
            return ancestors, None, 'cycle'
        if parent not in nodes:
            return ancestors, None, 'missing_parent'
        ancestors.append(parent)
        seen.add(parent)
        current = parent


def analyze(sample, context, window):
    start, end = (datetime.fromisoformat(window[k]) for k in ('start', 'end'))
    groups = defaultdict(list)
    for scope, rows in [('sample', sample), ('context', context)]:
        for row in rows:
            if row['source'] == 'hacker_news':
                groups[str(row['native_id'])].append((scope, row))
    anomalies = defaultdict(list)
    nodes, scopes, normalized = {}, {}, {}
    for item, rows in sorted(groups.items()):
        if len(rows) > 1:
            anomalies['duplicate_record_ids'].append(item)
        if len({json.dumps(r['source_native'], sort_keys=True) for _, r in rows}) > 1:
            anomalies['conflicting_native_records'].append(item)
            continue  # Ambiguous IDs are unavailable to traversal, never silently chosen.
        scope, row = rows[0]
        node = row['source_native']
        nodes[item], scopes[item], normalized[item] = node, scope, row
        if ident(node.get('id')) != item:
            anomalies['native_id_mismatch'].append(item)
        if ident(node.get('parent')) != row.get('parent_id'):
            anomalies['normalized_parent_mismatch'].append(item)
        if node.get('type') != row.get('item_type'):
            anomalies['normalized_type_mismatch'].append(item)
        if row.get('scope') != scope:
            anomalies['scope_label_mismatch'].append(item)
        dt = timestamp(node)
        if dt is None:
            anomalies['missing_creation_time'].append(item)
        elif (start <= dt < end) != (scope == 'sample'):
            anomalies['window_membership_mismatch'].append(item)
    def time_class(item):
        dt = timestamp(nodes[item])
        return 'unknown' if dt is None else 'pre_window' if dt < start else 'in_window' if dt < end else 'post_window'
    body = {i: bool(plain(n.get('text'))) for i, n in nodes.items()}
    title = {i: bool(plain(n.get('title'))) for i, n in nodes.items()}
    paths = {i: walk(i, nodes) for i, n in nodes.items() if n.get('type') == 'comment'}
    # Audit all retained HN records, including context, independently of cached thread IDs.
    for i, n in nodes.items():
        p = ident(n.get('parent'))
        if p == i:
            anomalies['self_parent_records'].append(i)
        if p is not None and p not in nodes:
            anomalies['missing_referenced_parents'].append(i)
        if p in nodes:
            if nodes[p].get('type') not in ROOT_TYPES | {'comment'}:
                anomalies['invalid_parent_types'].append(i)
            a, b = timestamp(n), timestamp(nodes[p])
            if a is not None and b is not None and b > a:
                anomalies['parent_newer_than_child'].append(i)
        if n.get('type') in ROOT_TYPES and p is not None:
            anomalies['root_has_parent'].append(i)
        kids = [str(k) for k in n.get('kids', [])]
        if len(kids) != len(set(kids)):
            anomalies['duplicate_child_ids'].append(i)
        for k in kids:
            if k in nodes and ident(nodes[k].get('parent')) != i:
                anomalies['retained_child_parent_disagreement'].append([i, k])
        if i in paths:
            chain, root, failure = paths[i]
            if failure:
                anomalies['chain_' + failure].append(i)
            if root != normalized[i].get('thread_id'):
                anomalies['stored_root_mismatch'].append(i)
            if root is not None and len(chain) != normalized[i].get('depth'):
                anomalies['stored_depth_mismatch'].append(i)
    comments = sorted(i for i in paths if scopes[i] == 'sample')
    counts = Counter({k: 0 for k in ('direct_parent_unavailable', 'root_unavailable')})
    metrics, thread_comments = [], defaultdict(list)
    required, parent_required = set(), set()
    for i in comments:
        n = nodes[i]
        chain, root, failure = paths[i]
        p = ident(n.get('parent'))
        parent = nodes.get(p)
        external = [a for a in chain if scopes[a] == 'context']
        required.update(external)
        if p in nodes and scopes[p] == 'context':
            parent_required.add(p)
        counts['comment_records'] += 1
        counts['comment_body_available'] += body[i]
        counts['comment_deleted'] += bool(n.get('deleted'))
        counts['comment_dead'] += bool(n.get('dead'))
        counts['direct_parent_available'] += parent is not None
        counts['direct_parent_' + (scopes[p] if parent is not None else 'unavailable')] += 1
        counts['direct_parent_type_' + (parent.get('type', 'unknown') if parent is not None else 'unavailable')] += 1
        counts['direct_parent_pre_window'] += parent is not None and time_class(p) == 'pre_window'
        counts['root_available'] += root is not None
        stored_root = normalized[i].get('thread_id')
        counts['stored_root_record_available_without_proving_chain'] += stored_root in nodes and nodes[stored_root].get('type') in ROOT_TYPES
        counts['root_' + (scopes[root] if root else 'unavailable')] += 1
        counts['root_type_' + (nodes[root].get('type', 'unknown') if root else 'unavailable')] += 1
        counts['root_pre_window'] += root is not None and time_class(root) == 'pre_window'
        counts['full_ancestor_chain_available'] += failure is None
        counts['all_ancestors_in_sample'] += failure is None and not external
        counts['any_context_ancestor'] += bool(external)
        counts['any_pre_window_ancestor'] += any(time_class(a) == 'pre_window' for a in chain)
        counts['parent_body_available'] += parent is not None and body[p]
        counts['parent_comment_body_available'] += parent is not None and parent.get('type') == 'comment' and body[p]
        counts['parent_conversational_text_available'] += parent is not None and (body[p] if parent.get('type') == 'comment' else title[p])
        counts['root_title_available'] += root is not None and title[root]
        counts['root_body_available'] += root is not None and body[root]
        counts['root_without_external_url'] += root is not None and not nodes[root].get('url')
        counts['root_without_external_url_with_body'] += root is not None and not nodes[root].get('url') and body[root]
        # Root title suffices: an absent submission body is not a missing comment.
        missing_text = [a for a in chain if not (title[a] if a == root else body[a])]
        full_text = failure is None and not missing_text
        counts['all_textual_ancestors_available'] += full_text
        counts['entire_path_text_available_including_comment'] += full_text and body[i]
        counts['any_ancestor_missing_required_text'] += bool(missing_text)
        counts['any_comment_ancestor_missing_body'] += any(nodes[a].get('type') == 'comment' and not body[a] for a in chain)
        counts['any_deleted_ancestor'] += any(nodes[a].get('deleted') for a in chain)
        counts['any_dead_ancestor'] += any(nodes[a].get('dead') for a in chain)
        counts['any_flagged_ancestor_missing_text'] += any((nodes[a].get('deleted') or nodes[a].get('dead')) for a in missing_text)
        counts['all_ancestor_bodies_present_strict'] += failure is None and all(body[a] for a in chain)
        metrics.append({'id': i, 'parent_id': p, 'root_id': root, 'failure': failure,
                        'depth': len(chain) if root else None, 'ancestor_ids_parent_first': chain,
                        'context_records': len(external), 'context_ids': external,
                        'missing_text_ancestor_ids': missing_text,
                        'comment_body_available': body[i], 'full_textual_ancestry': full_text})
        if root:
            thread_comments[root].append(i)
    def ratio(value, denominator):
        return {'count': value, 'denominator': denominator, 'percent': 100 * value / denominator if denominator else None}
    total = len(comments)
    roots = sorted(thread_comments)
    threads = [{'root_id': r, 'scope': scopes[r], 'time_class': time_class(r),
                'item_type': nodes[r].get('type'), 'sample_comments': len(thread_comments[r]),
                'max_sample_depth': max(len(paths[i][0]) for i in thread_comments[r])} for r in roots]
    threads.sort(key=lambda r: (-r['sample_comments'], r['root_id']))
    sizes = [t['sample_comments'] for t in threads]
    bins = {'1': 0, '2–5': 0, '6–10': 0, '11–25': 0, '26–50': 0, '51–100': 0, '101–250': 0, '251–500': 0, '501+': 0}
    for s in sizes:
        label = next(label for label, upper in zip(bins, [1, 5, 10, 25, 50, 100, 250, 500, float('inf')]) if s <= upper)
        bins[label] += 1
    ancestors = {a for m in metrics for a in m['ancestor_ids_parent_first']}
    def inventory(ids):
        return {'records': len(ids), 'types': dict(Counter(nodes[i].get('type', 'unknown') for i in ids)),
                'time_classes': dict(Counter(time_class(i) for i in ids)),
                'body_available': sum(body[i] for i in ids),
                'title_available': sum(title[i] for i in ids),
                'deleted': sum(bool(nodes[i].get('deleted')) for i in ids),
                'dead': sum(bool(nodes[i].get('dead')) for i in ids),
                'comments_without_body': sum(nodes[i].get('type') == 'comment' and not body[i] for i in ids),
                'deleted_without_body': sum(bool(nodes[i].get('deleted')) and not body[i] for i in ids),
                'dead_without_body': sum(bool(nodes[i].get('dead')) and not body[i] for i in ids),
                'roots_without_external_url': sum(nodes[i].get('type') in ROOT_TYPES and not nodes[i].get('url') for i in ids),
                'roots_without_external_url_with_body': sum(nodes[i].get('type') in ROOT_TYPES and not nodes[i].get('url') and body[i] for i in ids),
                'roots_without_title': sum(nodes[i].get('type') in ROOT_TYPES and not title[i] for i in ids)}
    context_ids = {i for i in nodes if scopes[i] == 'context'}
    complete = [m for m in metrics if m['failure'] is None]
    deepest = sorted(complete, key=lambda m: (-m['depth'], m['id']))[:5]
    ages = [(start - timestamp(nodes[i])).total_seconds() / 86400 for i in required if time_class(i) == 'pre_window']
    deep_examples = []
    for m in deepest:
        path = list(reversed(m['ancestor_ids_parent_first'])) + [m['id']]
        times = [timestamp(nodes[i]) for i in path]
        deep_examples.append({**m, 'path_root_first': path,
                              'timestamps_nondecreasing': all(a is not None and b is not None and a <= b
                                                             for a, b in zip(times, times[1:]))})
    result = {
        'schema_version': 1, 'window': window,
        'definitions': {
            'depth': 'Parent hops to a story/poll/job root; direct reply = 1.',
            'text_available': 'Nonempty native text/title after HTML stripping and whitespace trimming; no semantic quality judgment.',
            'full_textual_ancestry': 'Complete chain, every ancestor comment body present, root title present; root body optional.',
            'percentiles': 'Nearest rank ceil(p*n); median uses midpoint average.',
            'context': 'Membership in context.jsonl; native creation time classified separately.',
            'incomplete_paths': 'Excluded from depth/context distribution statistics; retained in per-comment output.',
            'conflicting_duplicates': 'Conflicting native payloads excluded from graph and explicitly reported; identical duplicates counted once.',
        },
        'hn_sample': inventory({i for i in nodes if scopes[i] == 'sample'}),
        'hn_context': inventory(context_ids),
        'comment_measures': {k: ratio(v, total) for k, v in sorted(counts.items())},
        'depth': stats([m['depth'] for m in complete]),
        'depth_histogram': {str(d): ratio(c, total) for d, c in sorted(Counter(m['depth'] for m in complete).items())},
        'context_per_comment_complete_chains': stats([m['context_records'] for m in complete]),
        'context_per_dependent_comment': stats([m['context_records'] for m in complete if m['context_records']]),
        'context_histogram_complete_chains': dict(sorted(Counter(m['context_records'] for m in complete).items())),
        'unique_required_context': inventory(required), 'unique_ancestors': inventory(ancestors),
        'unique_ancestors_missing_required_text': inventory({a for m in metrics for a in m['missing_text_ancestor_ids']}),
        'unique_direct_context_parents': len(parent_required),
        'context_not_used_by_sample_comments': len(context_ids - required),
        'context_ancestor_occurrences': sum(m['context_records'] for m in metrics),
        'required_context_age_days_before_start': stats(ages),
        'threads': {'count': len(roots), 'root_inventory': inventory(set(roots)),
                    'sample_comments_per_root': stats(sizes), 'size_bins': bins,
                    'pre_window_roots': ratio(sum(time_class(r) == 'pre_window' for r in roots), len(roots)),
                    'top_shares': {str(k): ratio(sum(sizes[:k]), total) for k in (1, 5, 10, 20, 50)},
                    'top_10': threads[:10],
                    'sample_submissions_without_sample_comments': sum(scopes[i] == 'sample' and nodes[i].get('type') in ROOT_TYPES and i not in thread_comments for i in nodes)},
        'deepest_examples': deep_examples,
        'anomalies': dict(sorted(anomalies.items())),
        'conflicting_sample_ids_excluded': [i for i in anomalies.get('conflicting_native_records', []) if any(s == 'sample' for s, _ in groups[i])],
    }
    return result, metrics, threads


def generate(run):
    run = Path(run)
    blobs = {name: (run / name).read_bytes() for name in ['sample.jsonl', 'context.jsonl', 'manifest.json']}
    result, metrics, threads = analyze(*[[json.loads(line) for line in blobs[name].splitlines()] for name in ['sample.jsonl', 'context.jsonl']], json.loads(blobs['manifest.json'])['window'])
    result['input_sha256'] = {name: hashlib.sha256(data).hexdigest() for name, data in blobs.items()}
    result['analysis_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = run / 'conversations'
    out.mkdir(exist_ok=True)
    (out / 'summary.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    for name, rows in [('comments', metrics), ('threads', threads)]:
        (out / (name + '.jsonl')).write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    result = generate(args.run)
    print(json.dumps({k: result[k] for k in ['depth', 'context_per_comment_complete_chains', 'unique_required_context', 'anomalies']}, indent=2))
