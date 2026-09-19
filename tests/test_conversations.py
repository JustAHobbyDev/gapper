import json
from pathlib import Path
import tempfile
import unittest

import conversations as c

WINDOW = {'start': '2026-09-18T08:00:00+00:00', 'end': '2026-09-19T08:00:00+00:00'}


def row(i, parent=None, scope='sample', **native):
    node = {'id': i, 'type': 'story' if parent is None else 'comment',
            'time': 1789718400 if scope == 'sample' else 1789632000,
            'text': 'body', 'title': 'title' if parent is None else None, **native}
    if parent is not None:
        node['parent'] = parent
    return {'source': 'hacker_news', 'native_id': str(i), 'scope': scope,
            'item_type': node['type'], 'parent_id': c.ident(parent),
            'thread_id': '1', 'depth': 0 if parent is None else i - 1,
            'source_native': node}


class Conversations(unittest.TestCase):
    def test_shared_history_and_missing_text_are_distinct(self):
        root = row(1, scope='context', text=None)
        parent = row(2, 1, scope='context', text=None, deleted=True)
        sample = [row(3, 2), row(4, 2)]
        result, comments, threads = c.analyze(sample, [root, parent], WINDOW)
        counts = result['comment_measures']
        self.assertEqual(counts['full_ancestor_chain_available']['count'], 2)
        self.assertEqual(counts['all_textual_ancestors_available']['count'], 0)
        self.assertEqual(result['unique_required_context']['records'], 2)
        self.assertEqual(result['context_ancestor_occurrences'], 4)
        self.assertEqual(result['depth']['max'], 2)
        self.assertEqual(threads[0]['sample_comments'], 2)
        self.assertEqual(comments[0]['missing_text_ancestor_ids'], ['2'])

    def test_root_title_suffices_and_dead_text_is_retained(self):
        result, _, _ = c.analyze([row(1, text=None), row(2, 1, dead=True), row(3, 2)], [], WINDOW)
        counts = result['comment_measures']
        self.assertEqual(counts['all_textual_ancestors_available']['count'], 2)
        self.assertEqual(counts['root_body_available']['count'], 0)
        self.assertEqual(counts['any_dead_ancestor']['count'], 1)
        self.assertEqual(result['anomalies'], {})

    def test_missing_intermediate_is_not_fixed_by_cached_root(self):
        result, comments, _ = c.analyze([row(1), row(3, 2), row(4, 3)], [], WINDOW)
        counts = result['comment_measures']
        self.assertEqual(counts['direct_parent_available']['count'], 1)
        self.assertEqual(counts['stored_root_record_available_without_proving_chain']['count'], 2)
        self.assertEqual(counts['root_available']['count'], 0)
        self.assertEqual(counts['full_ancestor_chain_available']['count'], 0)
        self.assertEqual(comments[1]['failure'], 'missing_parent')

    def test_pathologies_terminate(self):
        cases = [({1: {'type': 'comment', 'parent': 1}}, 'self_parent'),
                 ({1: {'type': 'comment', 'parent': 2}, 2: {'type': 'comment', 'parent': 1}}, 'cycle'),
                 ({1: {'type': 'comment', 'parent': 2}, 2: {'type': 'pollopt'}}, 'unexpected_type'),
                 ({1: {'type': 'comment'}}, 'comment_without_parent'),
                 ({1: {'type': 'comment', 'parent': 2}, 2: {'type': 'story', 'parent': 3}}, 'root_has_parent')]
        for nodes, reason in cases:
            with self.subTest(reason=reason):
                _, root, failure = c.walk('1', {str(k): v for k, v in nodes.items()})
                self.assertIsNone(root)
                self.assertEqual(failure, reason)

    def test_duplicate_and_conflicting_records(self):
        result, _, _ = c.analyze([row(1), row(1), row(2, 1)], [], WINDOW)
        self.assertEqual(result['anomalies']['duplicate_record_ids'], ['1'])
        result, comments, _ = c.analyze([row(1), row(1, text='different'), row(2, 1)], [], WINDOW)
        self.assertEqual(result['anomalies']['conflicting_native_records'], ['1'])
        self.assertEqual(comments[0]['failure'], 'missing_parent')

    def test_percentiles_and_empty_corpus(self):
        self.assertEqual(c.stats([1, 2, 3, 20])['p75'], 3)
        self.assertEqual(c.stats([1, 2, 3, 20])['median'], 2.5)
        result, _, _ = c.analyze([], [], WINDOW)
        self.assertEqual(result['depth'], {'n': 0})
        self.assertIsNone(result['threads']['pre_window_roots']['percent'])

    def test_export_is_deterministic_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / 'sample.jsonl').write_text(json.dumps(row(2, 1)) + '\n')
            (p / 'context.jsonl').write_text(json.dumps(row(1, scope='context')) + '\n')
            (p / 'manifest.json').write_text(json.dumps({'window': WINDOW}))
            before = {f.name: f.read_bytes() for f in p.iterdir()}
            c.generate(p)
            exported = {f.name: f.read_bytes() for f in (p / 'conversations').iterdir()}
            c.generate(p)
            self.assertEqual(exported, {f.name: f.read_bytes() for f in (p / 'conversations').iterdir()})
            self.assertEqual(before, {f.name: f.read_bytes() for f in p.iterdir() if f.is_file()})


if __name__ == '__main__':
    unittest.main()
