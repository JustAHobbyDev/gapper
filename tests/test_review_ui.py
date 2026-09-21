import unittest

import pilot
import review_ui as ui
from test_pilot import record


class RegionTests(unittest.TestCase):
    def packet(self, rows):
        return pilot.describe('hacker_news', '1', rows)

    def test_large_region_bounded_preserves_ancestry_and_all_secondary(self):
        rows = [record(1, text='r' * 20000)] + [record(i, parent=i // 2, text='x' * 3000) for i in range(2, 783)]
        p = self.packet(rows)
        region = ui.region(p, rows)
        primary = set(region['primary_record_ids'])
        self.assertLessEqual(len(primary), 24)
        self.assertLessEqual(region['initial_characters'], 16000)
        self.assertIn('1', primary)
        index = {r['native_id']: r for r in rows}
        for rid in primary:
            self.assertTrue(set(pilot.ancestry(index[rid], index)[0]) <= primary)
        self.assertEqual(primary | set(region['secondary_record_ids']), set(index))
        self.assertTrue(region['clipped_record_ids'])
        self.assertEqual(region, ui.region(dict(p, split='anything'), rows))

    def test_tiny_bodyless_not_removed(self):
        rows = [record(1, text=''), record(2, parent=1, text='')]
        p = self.packet(rows)
        region = ui.region(p, rows)
        self.assertEqual(region['initial_record_count'], 2)
        self.assertEqual(region['secondary_record_ids'], [])
        self.assertEqual(region['initial_characters'], len(rows[0]['title']))

    def test_extreme_depth_chooses_eligible_anchor_and_preserves_connectors(self):
        rows = [record(1)] + [record(i, parent=i-1) for i in range(2, 90)]
        region = ui.region(self.packet(rows), rows)
        self.assertLessEqual(region['initial_record_count'], 24)
        self.assertGreater(region['anchor_candidates_exceeding_record_budget'], 0)
        self.assertEqual(set(region['primary_record_ids']), {str(i) for i in range(1, 25)})

    def test_clipping_and_script_injection_escaped(self):
        rows = [record(1, text='</script><script>evil()</script>' + 'x' * 20000)]
        p = self.packet(rows); p['primary_region'] = ui.region(p, rows)
        output = ui.render(p, rows, {'packet_id': p['packet_id']})
        self.assertNotIn('<script>evil()', output)
        self.assertIn('&lt;script&gt;evil()', output)
        self.assertIn('Initial text clipped', output)
        self.assertIn('insufficient_evidence', output)
        self.assertNotIn('<details open', output)

    def test_burden_inconsistent_coverage_and_counts_rejected(self):
        rows = [record(1, text='x' * 20000)]
        p = self.packet(rows); p['primary_region'] = ui.region(p, rows)
        b = dict(ui.burden_template(p['primary_region']), extra_context_opened=False,
                 context_sufficiency='sufficient', review_scope='primary_only')
        ui.validate_burden({'review_burden': b}, p)
        for changes in [{'initial_characters': 1}, {'expanded_record_ids': ['1']},
                        {'review_scope': 'all_retained'}, {'visible_page_seconds': -1},
                        {'context_sufficiency': 'needed_extra'}]:
            with self.assertRaises(ValueError):
                ui.validate_burden({'review_burden': dict(b, **changes)}, p)
        ui.validate_burden({'review_burden': dict(b, extra_context_opened=True,
            expanded_record_ids=['1'], review_scope='all_retained')}, p)
