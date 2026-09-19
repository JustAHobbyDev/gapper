import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

import gapper as g

START = datetime(2026, 9, 18, 8, tzinfo=timezone.utc)
END = START + timedelta(days=1)


def response(payload, ok=True, url="fixture"):
    return {"ok": ok, "payload": payload, "url": url, "status": 200 if ok else 403,
            "retrieved_at": "2026-09-19T09:00:00+00:00", "response_ref": "fixture.json.gz"}


class FakeClient:
    def __init__(self, values):
        self.values = values
        self.urls = []

    def fetch(self, url):
        self.urls.append(url)
        return self.values.get(url, response(None, False, url))


def post(i, number, created, reply=None):
    return {"id": i, "topic_id": 7, "post_number": number, "created_at": created.isoformat(),
            "cooked": "<p>ordinary conversation</p>", "raw": "ordinary conversation",
            "username": "fixture", "category_id": 12, "reply_to_post_number": reply}


class Parsing(unittest.TestCase):
    def test_half_open_window_and_timezone(self):
        self.assertTrue(g.in_window(START.isoformat(), START, END))
        self.assertFalse(g.in_window(END.isoformat(), START, END))
        self.assertFalse(g.in_window(None, START, END))
        self.assertIsNone(g.parse_time("2026-09-18T08:00:00"))
        self.assertEqual(g.parse_time("2026-09-18T03:00:00-05:00"), START)

    def test_html_preservation_and_sort_dedup(self):
        self.assertEqual(g.plain("<p>A &amp; B</p><p>C</p>"), "A & B\nC")
        a = {"source": "make", "native_id": "1", "created_at": END.isoformat()}
        b = {"source": "make", "native_id": "2", "created_at": START.isoformat()}
        self.assertEqual(g.chronological([a, b, a]), [b, a])

    def test_ancestry_missing_cycle_and_poll(self):
        nodes = {1: {"type": "story"}, 2: {"type": "comment", "parent": 1},
                 3: {"type": "comment", "parent": 2}, 4: {"type": "poll"},
                 5: {"type": "pollopt", "poll": 4}, 6: {"type": "comment", "parent": 6}}
        self.assertEqual(g.hn_root(3, nodes), (1, 2))
        self.assertEqual(g.hn_root(5, nodes), (4, 1))
        self.assertEqual(g.hn_root(6, nodes), (None, None))
        self.assertEqual(g.hn_root(999, nodes), (None, None))


class Collectors(unittest.TestCase):
    def test_hn_guard_does_not_stop_at_first_old_item(self):
        values = {g.HN + '/maxitem.json': response(800)}
        for i in range(1, 801):
            dt = START - timedelta(hours=10)
            if i == 401:
                dt = START  # A newer timestamp after 399 older records.
            values[f'{g.HN}/item/{i}.json'] = response({'id': i, 'type': 'story', 'time': dt.timestamp()})
        client = FakeClient(values)
        sample, _, stats = g.hn_collect(client, START, END, workers=2)
        self.assertEqual([r['native_id'] for r in sample], ['401'])
        self.assertEqual(stats['scanned_ids'], 800)
        self.assertEqual(stats['stop_reason'], 'guard_boundary_reached')
        self.assertGreater(stats['timestamp_inversions'], 0)

    def test_make_activity_discovers_system_post_and_missing_stream_chunk(self):
        root = post(1, 1, START - timedelta(days=30))
        root['topic_id'] = 9
        system = post(2, 2, START + timedelta(hours=1))
        system.update(topic_id=9, post_type=3, action_code='autobumped')
        topic = {'id': 9, 'bumped_at': START.isoformat(), 'pinned': False}
        client = FakeClient({
            g.MAKE + '/posts.json': response({'latest_posts': []}),
            g.MAKE + '/latest.json': response({'topic_list': {'topics': [topic], 'more_topics_url': '/latest?page=1'}}),
            g.MAKE + '/latest.json?page=1': response({'topic_list': {'topics': []}}),
            g.MAKE + '/t/9.json': response({'post_stream': {'stream': [1, 2], 'posts': [root]}}),
            g.MAKE + '/t/9/posts.json?post_ids%5B%5D=2': response({'post_stream': {'posts': [system]}}),
            g.MAKE + '/categories.json': response({'category_list': {}})})
        sample, context, stats = g.make_collect(client, START, END)
        self.assertEqual(len(sample), 1)
        self.assertEqual(sample[0]['item_type'], 'system')
        self.assertEqual(sample[0]['parent_id'], '1')
        self.assertEqual([r['native_id'] for r in context], ['1'])
        self.assertEqual(stats['in_window_discovered_via_context'], [2])
        self.assertEqual(stats['stream_gaps'], {})
        self.assertEqual(stats['failed_urls'], [])

    def test_hn_all_types_comments_context_nulls_and_failures(self):
        values = {g.HN + "/maxitem.json": response(8)}
        items = {
            8: {"id": 8, "type": "comment", "parent": 2, "time": START.timestamp(), "text": "No keyword needed"},
            7: {"id": 7, "type": "job", "time": START.timestamp()},
            6: {"id": 6, "type": "story", "time": END.timestamp()},
            5: {"id": 5, "deleted": True},
            4: None,
            2: {"id": 2, "type": "comment", "parent": 1, "time": (START - timedelta(days=1)).timestamp()},
            1: {"id": 1, "type": "story", "title": "Unrelated old thread", "time": (START - timedelta(days=2)).timestamp()}}
        values.update({f"{g.HN}/item/{i}.json": response(p) for i, p in items.items()})
        client = FakeClient(values)
        sample, context, stats = g.hn_collect(client, START, END, workers=2, max_ids=8)
        self.assertEqual({r['native_id'] for r in sample}, {'7', '8'})
        self.assertEqual({r['native_id'] for r in context}, {'1', '2'})
        comment = next(r for r in sample if r['native_id'] == '8')
        self.assertEqual((comment['thread_id'], comment['depth']), ('1', 2))
        self.assertEqual(stats['null_ids'], [4])
        self.assertEqual(stats['failed_ids'], [3])
        self.assertEqual(stats['missing_time_ids'], [5])
        self.assertEqual(stats['stop_reason'], 'id_cap')
        self.assertEqual(len(client.urls), 9)

    def test_make_pagination_context_and_explicit_reply(self):
        older = START - timedelta(days=1)
        p1, p2, p3 = post(1, 1, older), post(2, 2, START), post(3, 3, START + timedelta(hours=2), 2)
        values = {
            g.MAKE + '/posts.json': response({'latest_posts': [p3, p2]}),
            g.MAKE + '/posts.json?before=2': response({'latest_posts': [p1]}),
            g.MAKE + '/t/7.json': response({'title': 'Ordinary topic', 'tags': [],
                'post_stream': {'stream': [1, 2, 3], 'posts': [p1, p2, p3]}}),
            g.MAKE + '/categories.json': response({'category_list': {'categories': []}})}
        client = FakeClient(values)
        sample, context, stats = g.make_collect(client, START, END)
        self.assertEqual(len(sample), 2)
        self.assertEqual(len(context), 1)
        self.assertEqual(sample[0]['parent_id'], '1')
        self.assertEqual(sample[1]['parent_id'], '2')
        self.assertEqual(sample[1]['parent_relation'], 'explicit_reply')
        self.assertEqual(stats['stop_reason'], 'guard_boundary_reached')
        self.assertEqual(stats['stream_gaps'], {})
        self.assertFalse(any('search' in url or '/c/' in url for url in client.urls))

    def test_make_detects_nonadvancing_cursor_and_context_failure(self):
        p = post(3, 3, START, 2)
        client = FakeClient({g.MAKE + '/posts.json': response({'latest_posts': [p]}),
                             g.MAKE + '/posts.json?before=3': response({'latest_posts': [p]})})
        sample, _, stats = g.make_collect(client, START, END)
        self.assertEqual(len(sample), 1)
        self.assertEqual(stats['stop_reason'], 'nonadvancing_cursor')
        self.assertEqual(stats['unresolved_parent_sample_ids'], ['3'])
        self.assertTrue(stats['failed_urls'])


class Archive(unittest.TestCase):
    def test_success_archive_resumes_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            client = g.Client(d, 'test', 1000)
            stream = io.BytesIO(b'{"id": 1, "unknown": "retained"}')
            stream.status, stream.headers = 200, {'Content-Type': 'application/json'}
            with patch.object(g, 'urlopen', return_value=stream) as network:
                first = client.fetch('https://example.test/items/1')
                second = client.fetch('https://example.test/items/1')
                self.assertEqual(network.call_count, 1)
            self.assertEqual(first, second)
            self.assertEqual(first['payload']['unknown'], 'retained')
            self.assertEqual(first['attempts'][0]['body'], '{"id": 1, "unknown": "retained"}')
            self.assertTrue((Path(d) / first['response_ref']).exists())

    def test_denial_recorded_without_retry(self):
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as d:
            error = HTTPError('https://example.test', 403, 'Forbidden', {}, io.BytesIO(b'denied'))
            with patch.object(g, 'urlopen', side_effect=error) as network:
                result = g.Client(d, 'test', 1000).fetch('https://example.test')
            self.assertEqual(network.call_count, 1)
            self.assertFalse(result['ok'])
            self.assertEqual(result['status'], 403)
            self.assertEqual(result['attempts'][0]['body'], 'denied')

    def test_retry_after_and_failed_response_recovery(self):
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as d:
            error = HTTPError('https://example.test', 429, 'Limited', {'Retry-After': '2'}, io.BytesIO(b'wait'))
            stream = io.BytesIO(b'null')
            stream.status, stream.headers = 200, {}
            with patch.object(g, 'urlopen', side_effect=[error, stream]), patch.object(g.time, 'sleep') as sleep:
                result = g.Client(d, 'test', 1000).fetch('https://example.test')
            self.assertTrue(result['ok'])
            self.assertIsNone(result['payload'])
            self.assertEqual([a['status'] for a in result['attempts']], [429, 200])
            self.assertIn(unittest.mock.call(2), sleep.call_args_list)


if __name__ == '__main__':
    unittest.main()
