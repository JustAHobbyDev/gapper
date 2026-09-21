import json
from pathlib import Path
import tempfile
import unittest

import blind_review as br
import pilot
import review_ui
from test_pilot import record


class BlindReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        run = self.base / 'run'; run.mkdir()
        pilot.write_jsonl(run / 'sample.jsonl', [record(i, root=str(i)) for i in range(1, 5)])
        pilot.write_jsonl(run / 'context.jsonl', [])
        (run / 'manifest.json').write_text(json.dumps({'window': {}}))
        self.prepared = self.base / 'pilot'
        pilot.prepare(run, self.prepared, 4)
        (self.prepared / 'ai_review.html').write_text('SECRET_AI_JUDGMENT')
        self.root = self.base / 'review'
        br.initialize(self.prepared, self.root)
        self.p = next(p for p in pilot.read_jsonl(self.prepared / 'packets.jsonl') if p['split'] == 'calibration')
        self.pid = self.p['packet_id']
        self.ai = {'packet_id': self.pid, 'status': 'reviewed', 'reviewer_id': 'model',
                   'reviewer_kind': 'ai_provisional', 'thread_label': 'no_candidate', 'episodes': []}
        self.ai_file = self.base / 'ai.jsonl'
        pilot.write_jsonl(self.ai_file, [self.ai])
        self.provenance = self.base / 'provenance.json'
        self.provenance.write_text(json.dumps({'model': 'test-only'}))
        self.human = dict(self.ai, reviewer_id='human', reviewer_kind='human_independent', thread_label='unknown')
        self.human['review_burden'] = dict(review_ui.burden_template(br.packet(self.root, self.pid)['primary_region']),
            extra_context_opened=False, context_sufficiency='sufficient', review_scope='primary_only')
        self.form = self.base / 'human.json'
        self.form.write_text(json.dumps(self.human))

    def test_bundle_contains_no_ai_and_reveal_requires_commit(self):
        for p in (self.root / 'reviewer').rglob('*'):
            if p.is_file():
                self.assertNotIn('SECRET_AI_JUDGMENT', p.read_text())
        br.seal_ai(self.root, self.ai_file, self.provenance)
        with self.assertRaisesRegex(ValueError, 'Commit the human'):
            br.reveal(self.root, self.pid)
        self.assertEqual(list((self.root / 'comparisons').iterdir()), [])

    def test_commit_reveal_and_adjudication_preserve_disagreement(self):
        br.seal_ai(self.root, self.ai_file, self.provenance)
        committed = br.commit(self.root, self.form, 'prior_summary')
        self.assertFalse(committed['ai_revealed'])
        original = (self.root / 'commits' / (self.pid + '.json')).read_bytes()
        with self.assertRaises(FileExistsError):
            br.commit(self.root, self.form, 'none')
        comparison = br.reveal(self.root, self.pid)
        self.assertTrue(comparison['differences']['thread_label']['disagrees'])
        self.assertEqual(comparison, br.reveal(self.root, self.pid))
        decision = self.base / 'decision.json'
        decision.write_text(json.dumps({'reviewer_id': 'human', 'rationale': 'retain uncertainty',
                                        'episode_alignment': [], 'disagreements': []}))
        with self.assertRaisesRegex(ValueError, 'thread-label disagreement'):
            br.adjudicate(self.root, self.pid, decision)
        data = json.loads(decision.read_text())
        data['disagreements'] = [{'dimension': 'thread_label', 'human': 'unknown', 'ai': 'no_candidate',
                                 'decision': 'unresolved', 'rationale': 'coverage'}]
        decision.write_text(json.dumps(data))
        br.adjudicate(self.root, self.pid, decision)
        self.assertEqual(original, (self.root / 'commits' / (self.pid + '.json')).read_bytes())
        with self.assertRaises(FileExistsError):
            br.adjudicate(self.root, self.pid, decision)

    def test_sealed_ai_cannot_be_replaced_or_added_after_commit(self):
        br.seal_ai(self.root, self.ai_file, self.provenance)
        with self.assertRaisesRegex(ValueError, 'already sealed'):
            br.seal_ai(self.root, self.ai_file, self.provenance)
        br.commit(self.root, self.form, 'none')
        path = self.root / 'private/ai' / (self.pid + '.json')
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'changed'):
            br.reveal(self.root, self.pid)

    def test_human_can_commit_without_ai_but_no_retrospective_blind_pair(self):
        br.commit(self.root, self.form, 'none')
        with self.assertRaisesRegex(ValueError, 'before human commitment'):
            br.seal_ai(self.root, self.ai_file, self.provenance)
        with self.assertRaisesRegex(ValueError, 'No AI result'):
            br.reveal(self.root, self.pid)

    def test_exposure_and_source_integrity(self):
        with self.assertRaisesRegex(ValueError, 'human_assisted'):
            br.commit(self.root, self.form, 'ai_annotation')
        (self.root / 'reviewer/records.jsonl').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            br.commit(self.root, self.form, 'none')

    def test_split_hidden_everywhere_in_reviewer_bundle(self):
        for path in (self.root / 'reviewer').rglob('*'):
            if path.is_file():
                for term in ['calibration', 'held_out', 'source_transfer']:
                    self.assertNotIn(term, path.read_text(), str(path))
        manifest = br.verify(self.root)
        self.assertEqual(manifest['experiment_assignments'][self.pid], self.p['split'])

    def test_insufficient_evidence_and_burden_required(self):
        self.human['thread_label'] = 'insufficient_evidence'
        self.form.write_text(json.dumps(self.human))
        br.commit(self.root, self.form, 'none')
        saved = json.loads((self.root / 'commits' / (self.pid + '.json')).read_text())
        self.assertEqual(saved['annotation']['thread_label'], 'insufficient_evidence')
        invalid = dict(self.human)
        invalid.pop('review_burden')
        self.form.write_text(json.dumps(invalid))
        with self.assertRaisesRegex(ValueError, 'burden is required'):
            br.commit(self.root, self.form, 'none')

    def test_upgrade_refuses_uncommitted_review_notes(self):
        path = self.root / 'reviewer/forms' / (self.pid + '.json')
        row = json.loads(path.read_text())
        row['coverage_notes'] = ['human draft note']
        path.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, 'Human review work exists'):
            br.upgrade(self.prepared, self.root, self.base / 'refuse')
        self.assertEqual(json.loads(path.read_text())['coverage_notes'], ['human draft note'])

    def test_upgrade_preserves_seals_without_exposing_ai(self):
        br.seal_ai(self.root, self.ai_file, self.provenance)
        target = self.base / 'next'
        br.upgrade(self.prepared, self.root, target)
        self.assertEqual((self.root / 'private/ai' / (self.pid + '.json')).read_bytes(),
                         (target / 'private/ai' / (self.pid + '.json')).read_bytes())
        with self.assertRaisesRegex(ValueError, 'Commit the human'):
            br.reveal(target, self.pid)
        br.commit(self.root, self.form, 'none')
        with self.assertRaisesRegex(ValueError, 'Existing human commitments'):
            br.upgrade(self.prepared, self.root, self.base / 'refuse')


if __name__ == '__main__':
    unittest.main()
