import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

import blind_review as br
import pilot
import review_app as app
from test_pilot import record

AI_SECRET = 'SECRET_AI_SUMMARY'


class ReviewAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        run = base / 'run'; run.mkdir()
        rows = [record(i, root=str(i), text=f'Story {i} text') for i in range(1, 5)]
        rows += [record(100, root='100', text='Large root')]
        rows += [record(i, root='100', parent=100 if i < 130 else i - 30, text=f'Comment {i} 😀 about invoices')
                 for i in range(101, 180)]
        rows += [record(200, root='200', text='')]
        pilot.write_jsonl(run / 'sample.jsonl', rows)
        pilot.write_jsonl(run / 'context.jsonl', [])
        (run / 'manifest.json').write_text(json.dumps({'window': {}}))
        pilot.prepare(run, base / 'pilot', 6)
        self.root = base / 'review'
        br.initialize(base / 'pilot', self.root)
        packets = pilot.read_jsonl(base / 'pilot/packets.jsonl')
        # The AI-paired packet must be in calibration; which one is decided by the pilot's hash.
        self.pid = next(p['packet_id'] for p in packets if p['split'] == 'calibration')
        self.first = next(p for p in packets if p['packet_id'] == self.pid)['record_ids'][0]
        ai = {'packet_id': self.pid, 'status': 'reviewed', 'reviewer_id': 'model', 'reviewer_kind': 'ai_provisional',
              'thread_label': 'has_candidate', 'coverage_notes': [], 'episodes': [self.episode(
                  'ai-1', self.first, workflow=AI_SECRET, need_status='possible', gap_labels=['integration'],
                  hypotheses=['inferred architecture'])]}
        pilot.write_jsonl(base / 'ai.jsonl', [ai])
        (base / 'provenance.json').write_text(json.dumps({'model': 'test-only'}))
        br.seal_ai(self.root, base / 'ai.jsonl', base / 'provenance.json')
        self.store = app.Store(self.root)
        self.addCleanup(lambda: self.store.db.close())
        self.store.set_reviewer('reviewer-a', 'none')

    def episode(self, eid, rid, field='pain', **extra):
        claim = {'claim_id': 'c1', 'field': field, 'summary': 'reported friction', 'basis': 'firsthand_report',
                 'polarity': 'supports', 'record_id': rid, 'text_field': 'text', 'start': 0, 'end': 5}
        return {'episode_id': eid, 'actor_ref': 'speaker', 'workflow': 'reconcile invoices', 'need_status': 'concrete',
                'adoption_status': 'not_stated', 'resolution': 'unknown', 'gap_labels': [], 'anchor_ids': [rid],
                'minimum_record_ids': [rid], 'claims': [claim], 'hypotheses': [], 'open_questions': []} | extra

    def draft(self, pid, label='no_candidate', episodes=(), **extra):
        body = {'thread_label': label, 'context_sufficiency': 'sufficient', 'coverage_notes': '',
                'episodes': list(episodes)} | extra
        self.store.save_draft(pid, body)
        return body

    def exported(self, name):
        return pilot.read_jsonl(self.store.exports / name)

    def test_no_episode_review_commits_and_exports_a_valid_reference(self):
        self.draft('hacker_news-1')
        view = self.store.commit('hacker_news-1')
        self.assertEqual(view['status'], 'committed')
        self.assertIsNone(view['draft'])
        row = self.exported('human_reference.reviewer-a.jsonl')[0]
        self.assertEqual((row['reviewer_id'], row['reviewer_kind'], row['thread_label']),
                         ('reviewer-a', 'human_independent', 'no_candidate'))
        result = pilot.validate(self.root / 'reviewer', self.store.exports / 'human_reference.reviewer-a.jsonl')
        self.assertTrue(result['valid'], result['errors'])
        self.assertEqual(self.store.state()['reviewed'], 1)

    def test_episode_evidence_keeps_source_ids_spans_and_optional_details(self):
        rid = '101'
        e = self.episode('episode-1', rid, details={'pain': ' slow ', 'steps': 'export\n\nmatch', 'burden': {'time': '', 'cost': '$5'},
                                                   'constraints': ['audit'], 'workaround': ''})
        e['claims'][0].update(start=14, end=21, span_kind='span')  # after the emoji: code-point offsets
        e['claims'].append(dict(e['claims'][0], claim_id='c2', field='failure', polarity='corrects', relates_to='c1',
                                start=0, end=7, in_minimum_set=False))
        del e['anchor_ids'], e['minimum_record_ids']
        self.draft('hacker_news-100', 'has_candidate', [e])
        self.store.commit('hacker_news-100')
        saved = self.exported('human_commits.jsonl')[0]['annotation']['episodes'][0]
        self.assertEqual(saved['anchor_ids'], [rid])
        self.assertEqual(saved['minimum_record_ids'], [rid])
        claim = saved['claims'][0]
        self.assertEqual((claim['record_id'], claim['start'], claim['end']), (rid, 14, 21))
        source = next(r for r in self.store.records['hacker_news-100'] if r['native_id'] == rid)
        self.assertEqual(claim['text_sha256'], pilot.digest(source['text']))
        self.assertEqual(source['text'][14:21], 'about i')
        self.assertEqual(saved['claims'][1]['polarity'], 'corrects')
        self.assertEqual(saved['details'], {'pain': 'slow', 'steps': ['export', 'match'], 'burden': {'cost': '$5'},
                                            'constraints': ['audit']})

    def test_several_episodes_and_validation_messages(self):
        with self.assertRaises(app.ReviewError) as caught:
            self.draft('hacker_news-100', 'has_candidate', [], context_sufficiency='needed_extra')
            self.store.commit('hacker_news-100')
        self.assertEqual(len(caught.exception.messages), 2)
        bad = self.episode('episode-1', '999999')
        self.draft('hacker_news-100', 'no_candidate', [bad])
        with self.assertRaisesRegex(app.ReviewError, 'outside this packet'):
            self.store.commit('hacker_news-100')
        self.assertEqual(self.store.commits('hacker_news-100', 'reviewer-a'), [])
        self.draft('hacker_news-100', 'has_candidate', [self.episode(f'episode-{n}', str(100 + n)) for n in (1, 2, 3)])
        self.store.commit('hacker_news-100')
        burden = self.store.commits('hacker_news-100', 'reviewer-a')[0]['annotation']['review_burden']
        self.assertEqual((burden['episode_count'], burden['claim_count']), (3, 3))

    def test_large_packet_is_bounded_and_supplemental_viewing_is_recorded(self):
        pid = 'hacker_news-100'
        view = self.store.view(pid)
        region = view['packet']['primary_region']
        self.assertEqual(len(view['records']), 80)
        self.assertLessEqual(region['initial_record_count'], 24)
        secondary = region['secondary_record_ids']
        self.store.record_telemetry(pid, {'visible_seconds': 30, 'active_seconds': 9999, 'viewed': secondary[:3] + ['bogus']})
        self.store.record_telemetry(pid, {'visible_seconds': 5, 'active_seconds': 5, 'viewed': secondary[:1]})
        self.draft(pid, context_sufficiency='needed_extra')
        self.store.commit(pid)
        burden = self.store.commits(pid, 'reviewer-a')[0]['annotation']['review_burden']
        self.assertTrue(burden['extra_context_opened'])
        self.assertEqual(burden['expanded_record_ids'], sorted(secondary[:3]))
        self.assertEqual((burden['review_scope'], burden['supplemental_records_viewed']), ('expanded_partial', 3))
        self.assertEqual((burden['visible_page_seconds'], burden['active_seconds']), (35, 125))  # implausible deltas are capped
        self.assertEqual(burden['initial_record_count'], region['initial_record_count'])
        row = next(r for r in self.store.queue() if r['packet_id'] == pid)
        self.assertTrue(row['context_opened'])
        self.assertEqual(self.exported('telemetry.jsonl')[0]['viewed'], sorted(secondary[:3]))

    def test_episode_without_in_window_evidence_is_derived_as_historical(self):
        pid = 'hacker_news-100'
        p = self.store.packets[pid]
        p['anchor_ids'] = [i for i in p['anchor_ids'] if i != '101']  # treat 101 as earlier context
        old = self.episode('episode-1', '101')
        self.draft(pid, 'has_candidate', [old])
        with self.assertRaisesRegex(app.ReviewError, 'earlier context are historical'):
            self.store.commit(pid)
        self.draft(pid, 'insufficient_evidence', [old])
        with self.assertRaisesRegex(app.ReviewError, 'historical episode is textual evidence'):
            self.store.commit(pid)
        self.draft(pid, 'no_candidate', [dict(old, claims=[dict(old['claims'][0], end=10 ** 6)])])
        with self.assertRaisesRegex(app.ReviewError, 'invalid role, basis, relation or span'):
            self.store.commit(pid)
        # A reviewer-supplied flag is ignored: citing an in-window record makes the episode new.
        mixed = dict(self.episode('episode-2', '102'), historical=True)
        mixed['claims'].append(dict(old['claims'][0], claim_id='c2'))
        self.draft(pid, 'has_candidate', [old, mixed])
        self.store.commit(pid)
        row = self.exported('human_reference.reviewer-a.jsonl')[0]
        self.assertEqual([(e['episode_id'], e['anchor_ids'], 'historical' in e) for e in row['episodes']],
                         [('episode-2', ['102'], False)])
        self.assertEqual([(e['episode_id'], e['historical'], e['anchor_ids']) for e in row['historical_episodes']],
                         [('episode-1', True, [])])
        self.assertEqual((row['review_burden']['episode_count'], row['review_burden']['historical_episode_count'],
                          row['review_burden']['claim_count']), (1, 1, 3))
        self.assertTrue(pilot.validate(self.root / 'reviewer', self.store.exports / 'human_reference.reviewer-a.jsonl')['valid'])
        draft = self.store.revise(pid)['draft']
        self.assertEqual([e['episode_id'] for e in draft['episodes']], ['episode-2', 'episode-1'])

    def test_bodyless_packet_completes_as_insufficient_evidence(self):
        self.draft('hacker_news-200', 'insufficient_evidence')
        self.assertEqual(self.store.commit('hacker_news-200')['status'], 'insufficient_evidence')
        self.assertEqual(self.exported('human_reference.reviewer-a.jsonl')[0]['episodes'], [])

    def test_draft_survives_restart_and_is_the_resume_target(self):
        self.assertEqual(self.store.status('hacker_news-3', 'reviewer-a'), 'not_reviewed')
        body = self.draft('hacker_news-3', 'unknown')
        self.store.db.close()
        reopened = app.Store(self.root)
        self.addCleanup(reopened.db.close)
        self.assertEqual(reopened.state()['reviewer_id'], 'reviewer-a')
        self.assertEqual(reopened.state()['resume'], 'hacker_news-3')
        self.assertEqual(reopened.view('hacker_news-3')['draft'], body)
        self.assertEqual(reopened.view('hacker_news-3')['status'], 'in_progress')
        self.assertEqual(self.exported_count(reopened), 0)

    def exported_count(self, store):
        return store.export()['counts']['human_commits']

    def test_commit_is_immutable_and_corrections_create_revisions(self):
        pid = 'hacker_news-1'
        self.draft(pid)
        self.store.commit(pid)
        original = self.store.commits(pid, 'reviewer-a')[0]
        with self.assertRaisesRegex(sqlite3.DatabaseError, 'immutable'):
            self.store.db.execute('UPDATE commits SET record=?', ('{}',))
        with self.assertRaisesRegex(sqlite3.DatabaseError, 'immutable'):
            self.store.db.execute('DELETE FROM commits')
        with self.assertRaisesRegex(app.ReviewError, 'Start a revision'):
            self.store.save_draft(pid, {'thread_label': 'unknown'})
        draft = self.store.revise(pid)['draft']
        with self.assertRaisesRegex(app.ReviewError, 'why'):
            self.store.commit(pid)
        self.store.save_draft(pid, dict(draft, thread_label='unknown', revision_note='reconsidered'))
        self.store.commit(pid)
        first, second = self.store.commits(pid, 'reviewer-a')
        self.assertEqual(first, original)
        self.assertEqual((second['revision'], second['supersedes_revision'], second['revision_note']), (2, 1, 'reconsidered'))
        self.assertEqual(second['annotation']['review_burden']['revisions_after_commit'], 1)
        self.assertEqual(second['annotation']['reviewer_kind'], 'human_independent')
        self.assertEqual(self.exported('human_reference.reviewer-a.jsonl')[0]['thread_label'], 'unknown')
        self.assertEqual(len(self.exported('human_commits.jsonl')), 2)

    def test_ai_and_assignments_are_inaccessible_before_commit(self):
        self.draft(self.pid, 'unknown')
        visible = json.dumps([self.store.view(self.pid), self.store.queue(), self.store.state()])
        for secret in [AI_SECRET, 'ai_provisional', 'comparison', 'calibration', 'held_out', 'source_transfer', '"split"', 'stratum']:
            self.assertNotIn(secret, visible)
        for call in [self.store.reveal, self.store.comparison]:
            with self.assertRaises(app.ReviewError) as caught:
                call(self.pid)
            self.assertEqual(caught.exception.status, 403)
        with self.assertRaisesRegex(app.ReviewError, 'not revealed'):
            self.store.adjudicate(self.pid, {'rationale': 'x'})
        self.store.commit(self.pid)
        self.assertEqual(self.store.view(self.pid)['comparison'], {'available': True, 'revealed': False})
        self.assertNotIn(AI_SECRET, json.dumps(self.store.view(self.pid)))
        self.assertEqual(self.exported('ai_annotations.jsonl'), [])
        with self.assertRaises(app.ReviewError):
            self.store.comparison(self.pid)  # committing alone does not reveal

    def compared(self):
        mine = self.episode('episode-1', self.first, need_status='concrete')
        self.draft(self.pid, 'has_candidate', [mine, self.episode('episode-2', self.first, workflow='other work')])
        self.store.commit(self.pid)
        self.store.reveal(self.pid)
        return self.store.comparison(self.pid)

    def test_comparison_adjudication_and_assisted_revision_stay_separate(self):
        view = self.compared()
        diff = view['reveal']['differences']
        self.assertEqual(diff['suggested_pairs'], [{'human_episode_id': 'episode-1', 'ai_episode_id': 'ai-1'}])
        self.assertEqual(diff['human_only_episode_ids'], ['episode-2'])
        pair = next(p for p in diff['pairs'] if p['human_episode_id'] == 'episode-1')
        self.assertTrue(pair['labels']['need_status']['disagrees'])
        self.assertEqual(pair['gap_labels']['ai_only'], ['integration'])
        self.assertEqual(pair['ai_unsupported_by_human']['hypotheses'], ['inferred architecture'])
        self.assertEqual(self.store.status(self.pid, 'reviewer-a'), 'ai_comparison_available')
        decision = {'rationale': 'evidence supports the human labels', 'episodes': [
            {'human_episode_id': 'episode-1', 'ai_episode_id': 'ai-1', 'decision': 'merged',
             'merged': {'need_status': 'possible', 'gap_labels': ['integration'], 'note': 'kept AI gap'}}]}
        with self.assertRaisesRegex(app.ReviewError, 'exactly once'):
            self.store.adjudicate(self.pid, decision)
        decision['episodes'].append({'human_episode_id': 'episode-2', 'ai_episode_id': None, 'decision': 'unresolved'})
        before = (self.store.commits(self.pid, 'reviewer-a'), self.store.reveal_record(self.pid, 'reviewer-a'))
        self.store.adjudicate(self.pid, decision)
        self.store.adjudicate(self.pid, decision)
        self.assertEqual(before, (self.store.commits(self.pid, 'reviewer-a'), self.store.reveal_record(self.pid, 'reviewer-a')))
        first, second = self.exported('adjudications.jsonl')
        self.assertEqual((first['version'], second['version']), (1, 2))
        result = first['adjudicated_annotation']
        self.assertEqual([e['need_status'] for e in result['episodes']], ['possible'])
        self.assertEqual([c['origin'] for c in result['episodes'][0]['claims']], ['human', 'ai'])
        self.assertEqual(result['unresolved'][0]['human_episode_id'], 'episode-2')
        self.assertIn('need_status:episode-1 / ai-1', [d['dimension'] for d in first['decision']['disagreements']])
        self.assertEqual(first['human_commit_sha256'], before[0][0]['sha256'])
        self.assertEqual(self.store.status(self.pid, 'reviewer-a'), 'adjudicated')
        # All three records remain separately exported; the human reference is still the blind revision.
        self.assertEqual(self.exported('ai_annotations.jsonl')[0]['annotation']['episodes'][0]['workflow'], AI_SECRET)
        draft = self.store.revise(self.pid)['draft']
        self.store.save_draft(self.pid, dict(draft, revision_note='after comparison', episodes=draft['episodes'][:1]))
        self.store.commit(self.pid)
        latest = self.store.commits(self.pid, 'reviewer-a')[-1]
        self.assertEqual((latest['annotation']['reviewer_kind'], latest['exposure_disclosure']), ('human_assisted', 'ai_annotation'))
        self.assertEqual(len(self.exported('human_reference.reviewer-a.jsonl')[0]['episodes']), 2)

    def test_changed_seal_blocks_reveal_and_exports_are_deterministic(self):
        self.draft(self.pid, 'unknown')
        self.store.commit(self.pid)
        path = self.root / 'private/ai' / (self.pid + '.json')
        original = path.read_bytes()
        path.write_text('{}')
        with self.assertRaisesRegex(app.ReviewError, 'changed'):
            self.store.reveal(self.pid)
        path.write_bytes(original)
        self.store.reveal(self.pid)
        snapshot = {p.name: p.read_bytes() for p in self.store.exports.iterdir()}
        self.store.export()
        self.assertEqual(snapshot, {p.name: p.read_bytes() for p in self.store.exports.iterdir()})
        metadata = json.loads(snapshot['experiment_metadata.json'])
        self.assertEqual(metadata['files']['human_commits.jsonl'], pilot.digest(snapshot['human_commits.jsonl']))
        self.assertNotIn('calibration', snapshot['experiment_metadata.json'].decode())

    def test_http_gates_ai_and_refuses_foreign_origins(self):
        server = app.serve(self.store, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        port = server.server_address[1]
        def call(method, path, body=None, **headers):
            c = http.client.HTTPConnection('127.0.0.1', port)
            c.request(method, path, json.dumps(body) if body is not None else None, headers)
            r = c.getresponse()
            return r.status, r.read().decode(), r
        self.assertEqual(call('GET', f'/api/packets/{self.pid}/comparison')[0], 403)
        self.assertEqual(call('POST', f'/api/packets/{self.pid}/reveal', {})[0], 403)
        self.assertEqual(call('GET', '/api/state', Host='evil.example')[0], 403)
        self.assertEqual(call('POST', '/api/reviewer', {'reviewer_id': 'x', 'exposure': 'none'}, Origin='http://evil.example')[0], 403)
        self.assertEqual(call('GET', '/../review_app.py')[0], 404)
        status, page, response = call('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn("default-src 'self'", response.getheader('Content-Security-Policy'))
        status, body, _ = call('PUT', f'/api/packets/{self.pid}/draft', {'thread_label': 'no_candidate', 'context_sufficiency': 'sufficient', 'episodes': []},
                               Origin=f'http://127.0.0.1:{port}')
        self.assertEqual(status, 200, body)
        status, body, _ = call('POST', f'/api/packets/{self.pid}/commit', {})
        self.assertEqual(status, 200, body)
        self.assertNotIn(AI_SECRET, body)
        status, body, _ = call('POST', f'/api/packets/{self.pid}/reveal', {})
        self.assertEqual(status, 200)
        self.assertIn(AI_SECRET, body)


if __name__ == '__main__':
    unittest.main()
