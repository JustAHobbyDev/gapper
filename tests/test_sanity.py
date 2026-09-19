import json
from pathlib import Path
import tempfile
import unittest

import sanity


def record(i, parent=None):
    return {'source': 'hacker_news', 'native_id': str(i), 'item_type': 'comment' if parent else 'story',
            'created_at': '2026-09-18T12:00:00+00:00', 'text': 'Ordinary text',
            'parent_id': str(parent) if parent else None, 'scope': 'sample',
            'url': f'https://news.ycombinator.com/item?id={i}', 'source_native': {'id': i}}


class SanitySamples(unittest.TestCase):
    def test_selection_ignores_subject_and_input_order(self):
        records = [record(i, 1) for i in range(2, 20)] + [record(1)]
        selected, slots = sanity.pick(records)
        changed = [dict(r, text='Completely different nonempty subject') for r in reversed(records)]
        other, other_slots = sanity.pick(changed)
        self.assertEqual([r['native_id'] for r in selected], [r['native_id'] for r in other])
        self.assertEqual(slots, other_slots)

    def test_unmodified_records_ancestors_and_deterministic_exports(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sample = record(3, 2)
            parent, ancestor = record(2, 1), record(1)
            parent['scope'] = ancestor['scope'] = 'context'
            (root / 'sample.jsonl').write_text(json.dumps(sample) + '\n')
            (root / 'context.jsonl').write_text(json.dumps(parent) + '\n' + json.dumps(ancestor) + '\n')
            original = (root / 'sample.jsonl').read_bytes()
            metadata = sanity.generate(root)
            self.assertEqual(metadata['selected'], 1)
            self.assertEqual(metadata['supporting_ancestors'], 2)
            self.assertEqual(metadata['missing_relationships'], [])
            self.assertEqual(json.loads((root / 'sanity/sample.jsonl').read_text()), sample)
            support = [json.loads(x) for x in (root / 'sanity/context.jsonl').read_text().splitlines()]
            self.assertEqual(support, [ancestor, parent])
            before = {p.name: p.read_bytes() for p in (root / 'sanity').iterdir()}
            sanity.generate(root)
            self.assertEqual(before, {p.name: p.read_bytes() for p in (root / 'sanity').iterdir()})
            self.assertEqual((root / 'sample.jsonl').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
