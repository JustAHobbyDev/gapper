import json
from pathlib import Path
import tempfile
import unittest

import pilot


def record(i, root='1', parent=None, scope='sample', source='hacker_news', kind=None, text='Example text'):
    return {'source': source, 'native_id': str(i), 'thread_id': root,
            'parent_id': str(parent) if parent is not None else None, 'scope': scope,
            'item_type': kind or ('comment' if parent is not None else 'story'),
            'text': text, 'title': 'Example title' if parent is None else None,
            'created_at': '2026-09-18T12:00:00+00:00', 'author': 'speaker'}


class PilotTests(unittest.TestCase):
    def test_selection_probabilities_and_semantic_independence(self):
        records = [record(i, root=str(i)) for i in range(1, 21)]
        records += [record(101, root='100', source='make', kind='system')]
        records += [record(201, root='200', source='make', kind='reply')]
        selected, strata = pilot.select(pilot.group_records(records), 6)
        altered = [dict(r, text='Different topic', title='Changed title') for r in reversed(records)]
        other, _ = pilot.select(pilot.group_records(altered), 6)
        self.assertEqual([r['packet_id'] for r in selected], [r['packet_id'] for r in other])
        hn = [p for p in selected if p['source'] == 'hacker_news']
        self.assertEqual(len(hn), 6)
        self.assertTrue(all(p['inclusion_probability'] == 6 / 20 for p in hn))
        self.assertEqual(sum(p['split'] == 'calibration' for p in hn), 3)
        self.assertEqual([p['root_id'] for p in selected if p['source'] == 'make'], ['200'])

    def test_arms_preserve_ancestry_and_exclude_sibling(self):
        rows = [record(1, scope='context'), record(2, parent=1, scope='context'),
                record(3, parent=2), record(4, parent=3), record(5, parent=2)]
        p = pilot.describe('hacker_news', '1', rows)
        p['split'] = 'calibration'
        arms = {a['arm']: a for a in pilot.context_arms(p, rows) if a['anchor_id'] == '3' or a['arm'] == 'B5'}
        self.assertEqual(arms['B0']['record_ids'], ['3'])
        self.assertEqual(arms['B1']['record_ids'], ['2', '3'])
        self.assertEqual(arms['B2']['record_ids'], ['1', '2', '3'])
        self.assertEqual(arms['B3']['record_ids'], ['1', '2', '3', '4'])
        self.assertEqual(arms['B5']['record_ids'], ['1', '2', '3', '4', '5'])
        self.assertTrue(p['needs_history'])

    def test_make_topic_reply_is_not_previous_post(self):
        rows = [record(100, root='9', source='make', kind='topic', scope='context'),
                record(101, root='9', source='make', kind='reply', parent=100, scope='context'),
                record(102, root='9', source='make', kind='reply', parent=100)]
        p = pilot.describe('make', '9', rows)
        p['split'] = 'source_transfer'
        b2 = next(a for a in pilot.context_arms(p, rows) if a['arm'] == 'B2')
        self.assertEqual(b2['record_ids'], ['100', '102'])

    def test_missing_parent_cycles_and_duplicates(self):
        row = record(3, parent=2)
        self.assertEqual(pilot.ancestry(row, {'3': row}), ([], ['missing_parent:2']))
        parent = record(2, parent=3)
        self.assertEqual(pilot.ancestry(row, {'3': row, '2': parent}), (['2'], ['cycle:3']))
        with self.assertRaises(ValueError):
            pilot.group_records([row, row])

    def test_packets_escape_untrusted_html(self):
        rendered = pilot.render_packet({'packet_id': 'example'}, [record(1, text='<script>alert(1)</script>')])
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)

    def test_prepare_is_reproducible_and_preserves_existing_review(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pilot.write_jsonl(root / 'sample.jsonl', [record(i, root=str(i)) for i in range(1, 5)])
            pilot.write_jsonl(root / 'context.jsonl', [])
            (root / 'manifest.json').write_text(json.dumps({'window': {'start': 'x', 'end': 'y'}}))
            first, second = root / 'first', root / 'second'
            a = pilot.prepare(root, first, 4)
            b = pilot.prepare(root, second, 4)
            self.assertEqual(a, b)
            self.assertEqual({p.relative_to(first): p.read_bytes() for p in first.rglob('*') if p.is_file()},
                             {p.relative_to(second): p.read_bytes() for p in second.rglob('*') if p.is_file()})
            annotation = first / 'annotation_template.jsonl'
            blank = pilot.validate(first, annotation)
            self.assertTrue(blank['valid'])
            self.assertEqual(blank['unreviewed_or_absent'], 4)
            annotation.write_text('existing reviewer work')
            with self.assertRaises(FileExistsError):
                pilot.prepare(root, first, 4)
            self.assertEqual(annotation.read_text(), 'existing reviewer work')

    def test_validation_rejects_bad_evidence_and_held_out_ai_drafts(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            rows = [record(1)]
            p = pilot.describe('hacker_news', '1', rows)
            p['split'] = 'held_out'
            pilot.write_jsonl(out / 'packets.jsonl', [p])
            pilot.write_jsonl(out / 'records.jsonl', rows)
            row = {'packet_id': p['packet_id'], 'status': 'reviewed', 'reviewer_id': 'draft',
                   'reviewer_kind': 'ai_provisional', 'thread_label': 'has_candidate',
                   'episodes': [{'episode_id': 'e1', 'actor_ref': 'speaker', 'workflow': 'task',
                                 'need_status': 'concrete', 'adoption_status': 'not_stated',
                                 'resolution': 'unknown', 'gap_labels': ['integration'],
                                 'anchor_ids': ['1'], 'minimum_record_ids': ['1'],
                                 'claims': [{'record_id': '1', 'text_field': 'text', 'start': 0,
                                             'end': 999, 'basis': 'firsthand_report', 'polarity': 'supports',
                                             'field': 'task', 'summary': 'task'}]}]}
            pilot.write_jsonl(out / 'review.jsonl', [row])
            result = pilot.validate(out, out / 'review.jsonl')
            self.assertFalse(result['valid'])
            self.assertTrue(any('span bounds' in e for e in result['errors']))
            self.assertTrue(any('outside calibration' in e for e in result['errors']))
            self.assertEqual(result['completed_by_split'], {})
            row['reviewer_kind'] = 'human_independent'
            row['episodes'][0]['claims'][0]['end'] = 7
            pilot.write_jsonl(out / 'review.jsonl', [row])
            self.assertTrue(pilot.validate(out, out / 'review.jsonl')['valid'])


if __name__ == '__main__':
    unittest.main()
