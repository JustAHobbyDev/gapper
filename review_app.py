#!/usr/bin/env python3
"""Local human review app for the context-ablation pilot.

SQLite drafts, write-once human commits/revisions, gated AI comparison, separate
adjudications and deterministic exports. Standard library only; binds to loopback.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import sqlite3
import threading
import webbrowser

import blind_review
import pilot
import review_ui

HERE = Path(__file__).parent
STATIC = HERE / 'review_static'
DEFAULT_ROOT = HERE / 'data/2026-09-19/research/blind-review-v2'
INSTRUMENT = 'review-app-v1'
HIDDEN_PACKET_KEYS = {'split', 'stratum', 'population_weight', 'inclusion_probability'}
RECORD_KEYS = ['native_id', 'parent_id', 'author', 'created_at', 'scope', 'item_type', 'title',
               'text', 'url', 'post_number', 'reply_to_post_number']
LABELS = ['has_candidate', 'unknown', 'no_candidate', 'insufficient_evidence']
SUFFICIENCY = ['sufficient', 'needed_extra', 'still_insufficient', 'uncertain']
EXPOSURES = ['none', 'prior_summary']
CLAIM_KEYS = ['claim_id', 'field', 'summary', 'basis', 'polarity', 'record_id', 'text_field',
              'start', 'end', 'span_kind', 'relates_to', 'in_minimum_set']
DECISIONS = ['accept_human', 'accept_ai', 'merged', 'unresolved']
EPISODE_LABEL_KEYS = ['need_status', 'adoption_status', 'resolution']
REVIEWER_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$')
MAX_BODY = 4_000_000

SCHEMA = '''
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS drafts(
  packet_id TEXT NOT NULL, reviewer_id TEXT NOT NULL, body TEXT NOT NULL,
  base_revision INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY(packet_id, reviewer_id));
CREATE TABLE IF NOT EXISTS telemetry(
  packet_id TEXT NOT NULL, reviewer_id TEXT NOT NULL, cycle INTEGER NOT NULL,
  started_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
  visible_seconds REAL NOT NULL DEFAULT 0, active_seconds REAL NOT NULL DEFAULT 0,
  context_opened INTEGER NOT NULL DEFAULT 0, viewed TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY(packet_id, reviewer_id, cycle));
CREATE TABLE IF NOT EXISTS commits(
  packet_id TEXT NOT NULL, reviewer_id TEXT NOT NULL, revision INTEGER NOT NULL,
  committed_at TEXT NOT NULL, record TEXT NOT NULL, sha256 TEXT NOT NULL,
  PRIMARY KEY(packet_id, reviewer_id, revision));
CREATE TABLE IF NOT EXISTS reveals(
  packet_id TEXT NOT NULL, reviewer_id TEXT NOT NULL, revealed_at TEXT NOT NULL,
  record TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(packet_id, reviewer_id));
CREATE TABLE IF NOT EXISTS adjudications(
  packet_id TEXT NOT NULL, reviewer_id TEXT NOT NULL, version INTEGER NOT NULL,
  recorded_at TEXT NOT NULL, record TEXT NOT NULL, sha256 TEXT NOT NULL,
  PRIMARY KEY(packet_id, reviewer_id, version));
'''
IMMUTABLE = ['commits', 'reveals', 'adjudications']


class ReviewError(ValueError):
    def __init__(self, messages, status=422):
        self.messages = [messages] if isinstance(messages, str) else list(messages)
        self.status = status
        super().__init__('; '.join(self.messages))


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def pruned(value):
    """Drop unset optional values so absent evidence is not exported as empty claims."""
    if isinstance(value, dict):
        result = {k: pruned(v) for k, v in value.items()}
        return {k: v for k, v in result.items() if v not in (None, '', [], {})}
    if isinstance(value, list):
        return [v for v in map(pruned, value) if v not in (None, '', [], {})]
    return value.strip() if isinstance(value, str) else value


def text_list(value):
    items = value.splitlines() if isinstance(value, str) else value if isinstance(value, list) else []
    return [s.strip() for s in items if isinstance(s, str) and s.strip()]


def compare(human, ai):
    """Describe differences; alignment by shared evidence records is only a suggestion."""
    def records(e):
        return {c.get('record_id') for c in e.get('claims', [])}
    def fields(e):
        return {c.get('field') for c in e.get('claims', [])}
    def split(a, b):
        return {'human_only': sorted(a - b), 'ai_only': sorted(b - a), 'shared': sorted(a & b)}
    pairs = []
    for h in human['episodes']:
        for a in ai['episodes']:
            hr, ar = records(h), records(a)
            labels = {k: {'human': h.get(k), 'ai': a.get(k), 'disagrees': h.get(k) != a.get(k)}
                      for k in EPISODE_LABEL_KEYS}
            gaps = split(set(h.get('gap_labels', [])), set(a.get('gap_labels', [])))
            evidence = split(hr, ar)
            roles = split(fields(h), fields(a))
            pairs.append({'human_episode_id': h['episode_id'], 'ai_episode_id': a['episode_id'],
                          'evidence_overlap': len(hr & ar) / len(hr | ar) if hr | ar else 0.0,
                          'labels': labels, 'gap_labels': gaps, 'evidence_records': evidence,
                          'claim_fields': roles,
                          # AI content with no counterpart in the human review. Not an error by itself.
                          'ai_unsupported_by_human': {
                              'claim_fields': roles['ai_only'], 'evidence_records': evidence['ai_only'],
                              'hypotheses': a.get('hypotheses', [])},
                          'classification_disagrees': any(v['disagrees'] for v in labels.values())
                          or bool(gaps['human_only'] or gaps['ai_only']),
                          'evidence_disagrees': bool(evidence['human_only'] or evidence['ai_only'])})
    suggested, used_h, used_a = [], set(), set()
    for p in sorted(pairs, key=lambda p: (-p['evidence_overlap'], p['human_episode_id'], p['ai_episode_id'])):
        if p['evidence_overlap'] > 0 and p['human_episode_id'] not in used_h and p['ai_episode_id'] not in used_a:
            used_h.add(p['human_episode_id']); used_a.add(p['ai_episode_id'])
            suggested.append({'human_episode_id': p['human_episode_id'], 'ai_episode_id': p['ai_episode_id']})
    return {'thread_label': {'human': human['thread_label'], 'ai': ai['thread_label'],
                             'disagrees': human['thread_label'] != ai['thread_label']},
            'episode_count': {'human': len(human['episodes']), 'ai': len(ai['episodes'])},
            'episode_alignment': 'suggested_by_shared_evidence_records_requires_explicit_review',
            'suggested_pairs': suggested, 'pairs': pairs,
            'human_only_episode_ids': [e['episode_id'] for e in human['episodes'] if e['episode_id'] not in used_h],
            'ai_only_episode_ids': [e['episode_id'] for e in ai['episodes'] if e['episode_id'] not in used_a]}


class Store:
    def __init__(self, root, db=None):
        self.root = Path(root)
        self.manifest = blind_review.verify(self.root)
        reviewer = self.root / 'reviewer'
        self.packets, self.order = {}, []
        for p in pilot.read_jsonl(reviewer / 'packets.jsonl'):
            p = {k: v for k, v in p.items() if k not in HIDDEN_PACKET_KEYS}
            self.packets[p['packet_id']] = p
            self.order.append(p['packet_id'])
        index = {(r['source'], r['native_id']): r for r in pilot.read_jsonl(reviewer / 'records.jsonl')}
        self.records = {pid: [index[p['source'], i] for i in p['record_ids']] for pid, p in self.packets.items()}
        self.manifest_sha256 = pilot.digest((self.root / 'manifest.json').read_bytes())
        path = Path(db) if db else self.root / 'app/review.sqlite3'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.exports = path.parent / 'exports'
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        for table in IMMUTABLE:
            for op in ['UPDATE', 'DELETE']:
                self.db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} "
                                f"BEGIN SELECT RAISE(ABORT, '{table} records are immutable'); END")

    # -- small helpers -----------------------------------------------------
    def one(self, sql, *args):
        return self.db.execute(sql, args).fetchone()

    def all(self, sql, *args):
        return self.db.execute(sql, args).fetchall()

    def packet(self, pid):
        if pid not in self.packets:
            raise ReviewError('Unknown packet ID', 404)
        return self.packets[pid]

    def setting(self, key, default=None):
        row = self.one('SELECT value FROM settings WHERE key=?', key)
        return json.loads(row['value']) if row else default

    def reviewer(self):
        rid = self.setting('reviewer_id')
        if not rid:
            raise ReviewError('Choose a reviewer identity first', 409)
        return rid

    def set_reviewer(self, reviewer_id, exposure):
        reviewer_id = (reviewer_id or '').strip()
        if not REVIEWER_RE.match(reviewer_id):
            raise ReviewError('Reviewer ID: 1-40 letters, digits, dot, dash or underscore')
        if exposure not in EXPOSURES:
            raise ReviewError('State whether you have seen earlier general AI findings for this corpus')
        with self.lock:
            for key, value in [('reviewer_id', reviewer_id), ('exposure:' + reviewer_id, exposure)]:
                self.db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                                (key, json.dumps(value)))
        return self.state()

    def commits(self, pid, rid):
        return [dict(json.loads(r['record']), sha256=r['sha256']) for r in
                self.all('SELECT * FROM commits WHERE packet_id=? AND reviewer_id=? ORDER BY revision', pid, rid)]

    def reveal_record(self, pid, rid):
        row = self.one('SELECT * FROM reveals WHERE packet_id=? AND reviewer_id=?', pid, rid)
        return dict(json.loads(row['record']), sha256=row['sha256']) if row else None

    def adjudication_records(self, pid, rid):
        return [dict(json.loads(r['record']), sha256=r['sha256']) for r in
                self.all('SELECT * FROM adjudications WHERE packet_id=? AND reviewer_id=? ORDER BY version', pid, rid)]

    def draft_row(self, pid, rid):
        return self.one('SELECT * FROM drafts WHERE packet_id=? AND reviewer_id=?', pid, rid)

    def ai_path(self, pid):
        return self.root / 'private/ai' / (pid + '.json')

    def ai_digest(self, pid):
        path = self.ai_path(pid)
        return pilot.digest(path.read_bytes()) if path.exists() else None

    def telemetry_row(self, pid, rid, cycle):
        row = self.one('SELECT * FROM telemetry WHERE packet_id=? AND reviewer_id=? AND cycle=?', pid, rid, cycle)
        return dict(row, viewed=json.loads(row['viewed']), context_opened=bool(row['context_opened'])) if row else None

    # -- queue / state -------------------------------------------------------
    def status(self, pid, rid):
        commits = self.commits(pid, rid)
        if not commits:
            t = self.telemetry_row(pid, rid, 1)
            started = self.draft_row(pid, rid) or (t and t['active_seconds'] >= 10)
            return 'in_progress' if started else 'not_reviewed'
        if self.adjudication_records(pid, rid):
            return 'adjudicated'
        if self.reveal_record(pid, rid) or commits[-1]['ai_sha256_at_commit']:
            return 'ai_comparison_available'
        if commits[-1]['annotation']['thread_label'] == 'insufficient_evidence':
            return 'insufficient_evidence'
        return 'committed'

    def queue(self):
        rid = self.reviewer()
        with self.lock:
            rows = []
            for pid in self.order:
                p, reg = self.packets[pid], self.packets[pid]['primary_region']
                commits = self.commits(pid, rid)
                draft = self.draft_row(pid, rid)
                opened = self.one('SELECT MAX(context_opened) AS o FROM telemetry WHERE packet_id=? AND reviewer_id=?', pid, rid)['o']
                body = json.loads(draft['body']) if draft else None
                shown = commits[-1]['annotation'] if commits else body or {}
                rows.append({'packet_id': pid, 'source': p['source'], 'status': self.status(pid, rid),
                             'open_revision': bool(commits and draft), 'revisions': len(commits),
                             'outcome': shown.get('thread_label'), 'episodes': len(shown.get('episodes', [])),
                             'retained_records': p['retained_records'], 'characters': p['characters'],
                             'tokens_estimate': math.ceil(p['characters'] / 4),
                             'initial_record_count': reg['initial_record_count'],
                             'initial_characters': reg['initial_characters'],
                             'initial_tokens_estimate': reg['initial_tokens_estimate'],
                             'context_opened': bool(opened)})
            return rows

    def state(self):
        rid = self.setting('reviewer_id')
        result = {'reviewer_id': rid, 'exposure': self.setting('exposure:' + rid) if rid else None,
                  'total': len(self.order), 'order': self.order, 'instrument': INSTRUMENT,
                  'reference_status': self.manifest['reference_status']}
        if rid:
            with self.lock:
                result['reviewed'] = self.one('SELECT COUNT(DISTINCT packet_id) AS n FROM commits WHERE reviewer_id=?', rid)['n']
                last = self.one('SELECT packet_id FROM drafts WHERE reviewer_id=? ORDER BY updated_at DESC LIMIT 1', rid)
                done = {r['packet_id'] for r in self.all('SELECT DISTINCT packet_id FROM commits WHERE reviewer_id=?', rid)}
            result['resume'] = last['packet_id'] if last else next((p for p in self.order if p not in done), None)
        return result

    def view(self, pid):
        rid = self.reviewer()
        p = self.packet(pid)
        with self.lock:
            commits, draft = self.commits(pid, rid), self.draft_row(pid, rid)
            result = {'packet': p, 'records': [{k: r.get(k) for k in RECORD_KEYS} for r in self.records[pid]],
                      'status': self.status(pid, rid),
                      'draft': json.loads(draft['body']) if draft else None,
                      'draft_saved_at': draft['updated_at'] if draft else None,
                      'telemetry': self.telemetry_row(pid, rid, len(commits) + 1),
                      'commits': [{k: c[k] for k in ['revision', 'committed_at', 'annotation', 'revision_note', 'sha256']}
                                  for c in commits]}
            # Nothing about AI results, including their existence, precedes a human commit.
            if commits:
                result['comparison'] = {'available': bool(commits[-1]['ai_sha256_at_commit']),
                                        'revealed': bool(self.reveal_record(pid, rid))}
            return result

    # -- drafts and telemetry ------------------------------------------------
    def save_draft(self, pid, body):
        rid = self.reviewer()
        self.packet(pid)
        if not isinstance(body, dict):
            raise ReviewError('Draft must be an object')
        with self.lock:
            commits, existing = self.commits(pid, rid), self.draft_row(pid, rid)
            if commits and not existing:
                raise ReviewError('This review is committed. Start a revision to change it.', 409)
            t = now()
            self.db.execute('INSERT INTO drafts VALUES(?,?,?,?,?,?) ON CONFLICT(packet_id, reviewer_id) '
                            'DO UPDATE SET body=excluded.body, updated_at=excluded.updated_at',
                            (pid, rid, canonical(body), len(commits) or None, t, t))
        return {'saved_at': t}

    def revise(self, pid):
        rid = self.reviewer()
        with self.lock:
            commits = self.commits(pid, rid)
            if not commits:
                raise ReviewError('Nothing committed to revise', 409)
            if not self.draft_row(pid, rid):
                a = commits[-1]['annotation']
                body = {'thread_label': a['thread_label'], 'episodes': a['episodes'],
                        'coverage_notes': a.get('coverage_notes', []),
                        'context_sufficiency': a['review_burden']['context_sufficiency'], 'revision_note': ''}
                t = now()
                self.db.execute('INSERT INTO drafts VALUES(?,?,?,?,?,?)',
                                (pid, rid, canonical(body), len(commits), t, t))
        return self.view(pid)

    def discard_revision(self, pid):
        rid = self.reviewer()
        with self.lock:
            if not self.commits(pid, rid):
                raise ReviewError('Only an uncommitted revision draft can be discarded', 409)
            self.db.execute('DELETE FROM drafts WHERE packet_id=? AND reviewer_id=?', (pid, rid))
        return self.view(pid)

    def record_telemetry(self, pid, data):
        rid = self.reviewer()
        p = self.packet(pid)
        def seconds(key):
            v = data.get(key, 0)
            return min(float(v), 120.0) if type(v) in {int, float} and math.isfinite(v) and v > 0 else 0.0
        reg = p['primary_region']
        allowed = set(reg['secondary_record_ids']) | set(reg['clipped_record_ids'])
        with self.lock:
            commits = self.commits(pid, rid)
            if commits and not self.draft_row(pid, rid):
                return {'recorded': False}  # reading a committed review is not review burden
            cycle, t = len(commits) + 1, now()
            row = self.telemetry_row(pid, rid, cycle)
            viewed = set(row['viewed']) if row else set()
            viewed |= {i for i in data.get('viewed', []) if isinstance(i, str) and i in allowed}
            opened = bool((row and row['context_opened']) or data.get('context_opened') or viewed)
            self.db.execute('INSERT INTO telemetry VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(packet_id, reviewer_id, cycle) DO UPDATE SET '
                            'last_seen_at=excluded.last_seen_at, visible_seconds=visible_seconds+excluded.visible_seconds, '
                            'active_seconds=active_seconds+excluded.active_seconds, context_opened=excluded.context_opened, viewed=excluded.viewed',
                            (pid, rid, cycle, t, t, seconds('visible_seconds'), seconds('active_seconds'),
                             int(opened), json.dumps(sorted(viewed))))
        return {'recorded': True}

    # -- commit ----------------------------------------------------------------
    def build_annotation(self, pid, body, rid, kind, telemetry, revision):
        p, errors = self.packets[pid], []
        index = {r['native_id']: r for r in self.records[pid]}
        label = body.get('thread_label')
        if label not in LABELS:
            errors.append('Choose a packet outcome.')
        if body.get('context_sufficiency') not in SUFFICIENCY:
            errors.append('Say whether the initially shown context was sufficient.')
        episodes, seen = [], set()
        for n, e in enumerate(body.get('episodes') or [], 1):
            name = f'Episode {n}'
            eid = e.get('episode_id') or f'episode-{n}'
            if eid in seen:
                errors.append(f'{name}: duplicate episode ID.')
            seen.add(eid)
            if not (e.get('workflow') or '').strip():
                errors.append(f'{name}: describe the workflow or task.')
            claims = []
            for c in e.get('claims') or []:
                c = {k: c.get(k) for k in CLAIM_KEYS if c.get(k) is not None}
                source = index.get(c.get('record_id'))
                if not source or c.get('text_field') not in {'text', 'title'}:
                    errors.append(f'{name}: evidence refers to a record outside this packet.')
                    continue
                if not (c.get('summary') or '').strip():
                    errors.append(f'{name}: evidence from {c["record_id"]} needs a one-line summary.')
                # Bind the offsets to the exact source text they were selected against.
                c['text_sha256'] = pilot.digest(source.get(c['text_field']) or '')
                claims.append(c)
            if not claims:
                errors.append(f'{name}: link at least one source comment as evidence.')
            cited = [c['record_id'] for c in claims]
            # Derived from the linked evidence, so the reviewer never types or copies source IDs.
            anchors = [i for i in p['anchor_ids'] if i in set(cited)]
            if claims and not anchors:
                errors.append(f'{name}: needs evidence from at least one in-window record; '
                              'an episode evidenced only by older context is historical, not new.')
            chosen = {c['record_id'] for c in claims if c.get('in_minimum_set') is not False}
            minimum = [i for i in p['record_ids'] if i in chosen]
            if claims and not minimum:
                errors.append(f'{name}: keep at least one evidence item in the minimum evidence set.')
            episode = {'episode_id': eid, 'actor_ref': (e.get('actor_ref') or '').strip() or 'unresolved',
                       'workflow': (e.get('workflow') or '').strip(),
                       'need_status': e.get('need_status') or 'unknown',
                       'adoption_status': e.get('adoption_status') or 'unknown',
                       'resolution': e.get('resolution') or 'unknown',
                       'gap_labels': sorted(set(e.get('gap_labels') or [])),
                       'anchor_ids': anchors, 'minimum_record_ids': minimum, 'claims': claims,
                       'hypotheses': text_list(e.get('hypotheses')),
                       'open_questions': text_list(e.get('open_questions')),
                       'details': pruned({k: text_list(v) if k in {'steps', 'inputs', 'outputs', 'systems'} else v
                                          for k, v in (e.get('details') or {}).items()})}
            episodes.append(episode)
        if label == 'has_candidate' and not episodes:
            errors.append('A concrete workflow outcome needs at least one episode.')
        if label in {'no_candidate', 'insufficient_evidence'} and episodes:
            errors.append('This outcome records no episodes. Remove the episodes or choose another outcome.')
        t = telemetry or {'viewed': [], 'context_opened': False, 'visible_seconds': 0, 'active_seconds': 0, 'started_at': None}
        reg = p['primary_region']
        expandable = set(reg['secondary_record_ids']) | set(reg['clipped_record_ids'])
        viewed = sorted(set(t['viewed']) & expandable)
        opened = bool(t['context_opened'] or viewed)
        if body.get('context_sufficiency') == 'needed_extra' and not opened:
            errors.append('"Needed extra context" requires opening the additional context you used.')
        if errors:
            raise ReviewError(errors)
        burden = dict(review_ui.burden_template(reg), extra_context_opened=opened, expanded_record_ids=viewed,
                      context_sufficiency=body['context_sufficiency'],
                      visible_page_seconds=round(t['visible_seconds']), measurement_method='browser_visible_time',
                      review_scope='primary_only' if not opened else
                      'all_retained' if expandable <= set(viewed) else 'expanded_partial',
                      active_seconds=round(t['active_seconds']), started_at=t['started_at'],
                      supplemental_records_available=len(reg['secondary_record_ids']),
                      supplemental_records_viewed=len(set(viewed) & set(reg['secondary_record_ids'])),
                      episode_count=len(episodes), claim_count=sum(len(e['claims']) for e in episodes),
                      revisions_after_commit=revision - 1, instrument=INSTRUMENT)
        return {'packet_id': pid, 'reviewer_id': rid, 'reviewer_kind': kind, 'status': 'reviewed',
                'minutes': None, 'thread_label': label, 'coverage_notes': text_list(body.get('coverage_notes')),
                'episodes': episodes, 'review_burden': burden}

    def commit(self, pid):
        rid = self.reviewer()
        p = self.packet(pid)
        with self.lock:
            blind_review.verify(self.root)
            draft = self.draft_row(pid, rid)
            if not draft:
                raise ReviewError('No draft to commit', 409)
            body, commits = json.loads(draft['body']), self.commits(pid, rid)
            revision = len(commits) + 1
            note = (body.get('revision_note') or '').strip()
            if commits and not note:
                raise ReviewError('Say why this committed review is being revised.')
            revealed = self.reveal_record(pid, rid)
            exposure = 'ai_annotation' if revealed else self.setting('exposure:' + rid)
            kind = 'human_assisted' if revealed else 'human_independent'
            row = self.build_annotation(pid, body, rid, kind, self.telemetry_row(pid, rid, revision), revision)
            try:  # the frozen pilot validators remain the authority for the shared schema
                blind_review.checked_annotation(self.root, row, kind)
                review_ui.validate_burden(row, p)
            except ValueError as exc:
                raise ReviewError(str(exc))
            t = now()
            record = {'committed_at': t, 'annotation': row, 'exposure_disclosure': exposure,
                      'reference_status': 'single_reviewer_exploratory',
                      'ai_sha256_at_commit': self.ai_digest(pid), 'source_manifest_sha256': self.manifest_sha256,
                      'independence': {'none': 'self_reported_no_prior_ai_exposure'}.get(exposure, 'prior_exposure_disclosed'),
                      'packet_id': pid, 'reviewer_id': rid, 'revision': revision,
                      'supersedes_revision': revision - 1 or None, 'revision_note': note or None,
                      'initial_context': {k: p['primary_region'][k] for k in
                                          ['policy', 'anchor_id', 'primary_record_ids', 'clipped_record_ids']}}
            self.db.execute('BEGIN')
            try:
                self.db.execute('INSERT INTO commits VALUES(?,?,?,?,?,?)',
                                (pid, rid, revision, t, canonical(record), pilot.digest(canonical(record))))
                self.db.execute('DELETE FROM drafts WHERE packet_id=? AND reviewer_id=?', (pid, rid))
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK')
                raise
            self.export()
        return self.view(pid)

    # -- comparison and adjudication -----------------------------------------------
    def reveal(self, pid):
        rid = self.reviewer()
        self.packet(pid)
        with self.lock:
            existing = self.reveal_record(pid, rid)
            if existing:
                return existing
            commits = self.commits(pid, rid)
            if not commits:
                raise ReviewError('Commit the human review before comparing with AI', 403)
            if self.draft_row(pid, rid):
                raise ReviewError('Commit or discard the open revision before revealing AI', 409)
            human = commits[-1]
            if not human['ai_sha256_at_commit']:
                raise ReviewError('No AI result was sealed at commitment; no blind paired comparison is available', 404)
            if self.ai_digest(pid) != human['ai_sha256_at_commit']:
                raise ReviewError('Sealed AI annotation changed', 409)
            ai = json.loads(self.ai_path(pid).read_text())
            t = now()
            record = {'packet_id': pid, 'reviewer_id': rid, 'revealed_at': t, 'human_revision': human['revision'],
                      'human_commit_sha256': human['sha256'], 'ai_sha256': human['ai_sha256_at_commit'],
                      'ai_result': ai, 'differences': compare(human['annotation'], ai['annotation']),
                      'adjudication_status': 'pending', 'reference_status': 'single_reviewer_exploratory'}
            self.db.execute('INSERT INTO reveals VALUES(?,?,?,?,?)',
                            (pid, rid, t, canonical(record), pilot.digest(canonical(record))))
            self.export()
            return self.reveal_record(pid, rid)

    def comparison(self, pid):
        rid = self.reviewer()
        self.packet(pid)
        with self.lock:
            record = self.reveal_record(pid, rid)
            if not record:
                raise ReviewError('AI annotation is not revealed for this packet', 403)
            human = next(c for c in self.commits(pid, rid) if c['revision'] == record['human_revision'])
            return {'reveal': record, 'human': human, 'adjudications': self.adjudication_records(pid, rid)}

    def adjudicate(self, pid, data):
        rid = self.reviewer()
        with self.lock:
            view = self.comparison(pid)
            h, a = view['human']['annotation'], view['reveal']['ai_result']['annotation']
            diff, errors = view['reveal']['differences'], []
            if not isinstance(data, dict) or not (data.get('rationale') or '').strip():
                raise ReviewError('Adjudication needs an overall rationale.')
            label = data.get('thread_label') or {}
            if diff['thread_label']['disagrees']:
                if label.get('decision') not in DECISIONS:
                    errors.append('Decide the packet-outcome disagreement.')
                if label.get('decision') == 'merged' and label.get('value') not in LABELS:
                    errors.append('A merged outcome needs a value.')
            final_label = {'accept_human': h['thread_label'], 'accept_ai': a['thread_label'],
                           'merged': label.get('value'), 'unresolved': None}.get(label.get('decision'), h['thread_label'])
            humans = {e['episode_id']: e for e in h['episodes']}
            ais = {e['episode_id']: e for e in a['episodes']}
            pairs = {(p['human_episode_id'], p['ai_episode_id']): p for p in diff['pairs']}
            episodes, unresolved, alignment, disagreements = [], [], [], []
            if diff['thread_label']['disagrees']:
                disagreements.append({'dimension': 'thread_label', 'human': h['thread_label'], 'ai': a['thread_label'],
                                      'decision': label.get('decision'), 'rationale': label.get('rationale') or ''})
            seen_h, seen_a = [], []
            for item in data.get('episodes') or []:
                hid, aid, decision = item.get('human_episode_id'), item.get('ai_episode_id'), item.get('decision')
                if (hid is None and aid is None) or (hid is not None and hid not in humans) or (aid is not None and aid not in ais):
                    errors.append('Episode alignment refers to an unknown episode.')
                    continue
                seen_h += [hid] if hid is not None else []
                seen_a += [aid] if aid is not None else []
                name = ' / '.join(str(i) for i in [hid, aid] if i is not None)
                if decision not in DECISIONS:
                    errors.append(f'{name}: choose an adjudication decision.')
                    continue
                he, ae = humans.get(hid), ais.get(aid)
                origin = {'decision': decision, 'human_episode_id': hid, 'ai_episode_id': aid}
                alignment.append(dict(origin, match='matched' if he and ae else 'human_only' if he else 'ai_only',
                                      rationale=item.get('rationale') or ''))
                pair = pairs.get((hid, aid))
                if pair:
                    for k, v in pair['labels'].items():
                        if v['disagrees']:
                            disagreements.append({'dimension': f'{k}:{name}', 'human': v['human'], 'ai': v['ai'],
                                                  'decision': decision, 'rationale': item.get('rationale') or ''})
                    for k in ['gap_labels', 'evidence_records']:
                        if pair[k]['human_only'] or pair[k]['ai_only']:
                            disagreements.append({'dimension': f'{k}:{name}', 'human': pair[k]['human_only'] + pair[k]['shared'],
                                                  'ai': pair[k]['ai_only'] + pair[k]['shared'], 'decision': decision,
                                                  'rationale': item.get('rationale') or ''})
                else:
                    disagreements.append({'dimension': f'episode_presence:{name}', 'human': hid, 'ai': aid,
                                          'decision': decision, 'rationale': item.get('rationale') or ''})
                if decision == 'unresolved':
                    unresolved.append(dict(origin, human_episode=he, ai_episode=ae))
                elif decision == 'merged':
                    merged = dict(he or ae)
                    override = item.get('merged') or {}
                    for k in EPISODE_LABEL_KEYS + ['workflow']:
                        if override.get(k):
                            merged[k] = override[k]
                    if isinstance(override.get('gap_labels'), list):
                        merged['gap_labels'] = sorted(set(override['gap_labels']))
                    merged['claims'] = [dict(c, origin=o) for o, e in [('human', he), ('ai', ae)] if e for c in e['claims']]
                    merged['merge_note'] = override.get('note') or ''
                    episodes.append(dict(merged, adjudication=origin))
                else:
                    kept = he if decision == 'accept_human' else ae
                    if kept:  # accepting the side that saw no episode drops it, leaving the alignment as its trace
                        episodes.append(dict(kept, adjudication=origin))
            if sorted(seen_h) != sorted(humans) or sorted(seen_a) != sorted(ais):
                errors.append('Every human and AI episode must be adjudicated exactly once.')
            if final_label in {'no_candidate', 'insufficient_evidence'} and episodes:
                errors.append('The adjudicated outcome records no episodes, but episodes were accepted.')
            if final_label == 'has_candidate' and not episodes and not unresolved:
                errors.append('The adjudicated outcome is a concrete workflow, but no episode was accepted.')
            if errors:
                raise ReviewError(errors)
            t, version = now(), len(view['adjudications']) + 1
            record = {'packet_id': pid, 'recorded_at': t, 'version': version,
                      'decision': {'reviewer_id': rid, 'rationale': data['rationale'].strip(),
                                   'episode_alignment': alignment, 'disagreements': disagreements},
                      'adjudicated_annotation': {'packet_id': pid, 'reviewer_id': rid, 'reviewer_kind': 'adjudicated',
                                                 'thread_label': final_label,
                                                 'thread_label_status': 'unresolved' if final_label is None else 'decided',
                                                 'episodes': episodes, 'unresolved': unresolved},
                      'human_commit_sha256': view['human']['sha256'], 'ai_sha256': view['reveal']['ai_sha256'],
                      'comparison_sha256': view['reveal']['sha256'], 'originals_preserved': True,
                      'reference_status': 'single_reviewer_exploratory'}
            self.db.execute('INSERT INTO adjudications VALUES(?,?,?,?,?,?)',
                            (pid, rid, version, t, canonical(record), pilot.digest(canonical(record))))
            self.export()
            return self.comparison(pid)

    # -- export ----------------------------------------------------------------
    def export(self):
        """Regenerate every export from the database. Same database state, same bytes."""
        with self.lock:
            out = self.exports
            out.mkdir(parents=True, exist_ok=True)
            commits = [json.loads(r['record']) | {'sha256': r['sha256']} for r in
                       self.all('SELECT * FROM commits ORDER BY reviewer_id, packet_id, revision')]
            reveals = [json.loads(r['record']) | {'sha256': r['sha256']} for r in
                       self.all('SELECT * FROM reveals ORDER BY reviewer_id, packet_id')]
            adjudications = [json.loads(r['record']) | {'sha256': r['sha256']} for r in
                             self.all('SELECT * FROM adjudications ORDER BY reviewer_id, packet_id, version')]
            telemetry = [dict(r, viewed=json.loads(r['viewed'])) for r in
                         map(dict, self.all('SELECT * FROM telemetry ORDER BY reviewer_id, packet_id, cycle'))]
            for stale in out.glob('human_reference.*.jsonl'):
                stale.unlink()
            files = {'human_commits.jsonl': commits, 'comparisons.jsonl': reveals,
                     'adjudications.jsonl': adjudications, 'telemetry.jsonl': telemetry,
                     # Only revealed AI results are exported, so the export cannot unblind pending packets.
                     'ai_annotations.jsonl': sorted(
                         ({'packet_id': r['packet_id'], 'ai_sha256': r['ai_sha256'], **r['ai_result']}
                          for r in {r['packet_id']: r for r in reveals}.values()), key=lambda r: r['packet_id'])}
            # Reference = each reviewer's last independent revision; later assisted revisions stay in human_commits.
            reference = {}
            for c in commits:
                if c['annotation']['reviewer_kind'] == 'human_independent':
                    reference[c['reviewer_id'], c['packet_id']] = c['annotation']
            for rid in sorted({k[0] for k in reference}):
                files[f'human_reference.{rid}.jsonl'] = [v for k, v in sorted(reference.items()) if k[0] == rid]
            for name, rows in files.items():
                pilot.write_jsonl(out / name, rows)
            metadata = {'instrument': INSTRUMENT, 'protocol': self.manifest['protocol'],
                        'source_manifest_sha256': self.manifest_sha256,
                        'pilot_manifest_sha256': self.manifest['pilot_manifest_sha256'],
                        'experiment_packets_sha256': self.manifest.get('experiment_packets_sha256'),
                        'experiment_assignments': 'join on packet_id with private/experiment_packets.jsonl; not copied here',
                        'selector': self.manifest.get('selector'), 'reference_status': self.manifest['reference_status'],
                        'human_inter_annotator_agreement': self.manifest['human_inter_annotator_agreement'],
                        'token_estimator': 'ceil(source Unicode characters / 4); not tokenizer output',
                        'time_measurement': 'visible = foreground tab; active = visible with input in the last 60 s; neither verifies reading',
                        'packets': len(self.order), 'reviewers': sorted({c['reviewer_id'] for c in commits}),
                        'counts': {'human_commits': len(commits), 'packets_committed': len({(c['reviewer_id'], c['packet_id']) for c in commits}),
                                   'comparisons': len(reveals), 'adjudications': len(adjudications)},
                        'app_sha256': pilot.digest(Path(__file__).read_bytes()),
                        'files': {n: pilot.digest((out / n).read_bytes()) for n in sorted(files)}}
            (out / 'experiment_metadata.json').write_text(json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + '\n')
            return {'directory': str(out), 'files': sorted(files) + ['experiment_metadata.json'], 'counts': metadata['counts']}


ROUTES = [
    ('GET', r'/api/state', lambda s, m, d: s.state()),
    ('POST', r'/api/reviewer', lambda s, m, d: s.set_reviewer(d.get('reviewer_id'), d.get('exposure'))),
    ('GET', r'/api/queue', lambda s, m, d: s.queue()),
    ('POST', r'/api/export', lambda s, m, d: s.export()),
    ('GET', r'/api/packets/([\w.-]+)', lambda s, m, d: s.view(m[1])),
    ('PUT', r'/api/packets/([\w.-]+)/draft', lambda s, m, d: s.save_draft(m[1], d)),
    ('POST', r'/api/packets/([\w.-]+)/telemetry', lambda s, m, d: s.record_telemetry(m[1], d)),
    ('POST', r'/api/packets/([\w.-]+)/commit', lambda s, m, d: s.commit(m[1])),
    ('POST', r'/api/packets/([\w.-]+)/revise', lambda s, m, d: s.revise(m[1])),
    ('POST', r'/api/packets/([\w.-]+)/discard-revision', lambda s, m, d: s.discard_revision(m[1])),
    ('POST', r'/api/packets/([\w.-]+)/reveal', lambda s, m, d: s.reveal(m[1]) and s.comparison(m[1])),
    ('GET', r'/api/packets/([\w.-]+)/comparison', lambda s, m, d: s.comparison(m[1])),
    ('POST', r'/api/packets/([\w.-]+)/adjudicate', lambda s, m, d: s.adjudicate(m[1], d)),
]
ASSETS = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
          '/app.css': ('app.css', 'text/css')}


def handler(store):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'gapper-review'

        def log_message(self, *args):
            pass

        def reply(self, status, body, kind='application/json'):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind + '; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            # Source text is untrusted: no inline script, no external loads.
            self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def handle_request(self, method):
            port = self.server.server_address[1]
            local = {f'127.0.0.1:{port}', f'localhost:{port}'}
            origin = self.headers.get('Origin')
            # Loopback is reachable from any web page in the browser; refuse rebinding and cross-site writes.
            if self.headers.get('Host') not in local or (origin and origin.split('//')[-1] not in local):
                return self.reply(403, {'errors': ['Cross-origin request refused']})
            path = self.path.split('?')[0]
            if method == 'GET' and path in ASSETS:
                name, kind = ASSETS[path]
                return self.reply(200, (STATIC / name).read_bytes(), kind)
            try:
                data = {}
                if method != 'GET':
                    size = int(self.headers.get('Content-Length') or 0)
                    if size > MAX_BODY:
                        raise ReviewError('Request too large', 413)
                    data = json.loads(self.rfile.read(size) or b'{}')
                for verb, pattern, function in ROUTES:
                    match = re.fullmatch(pattern, path)
                    if verb == method and match:
                        return self.reply(200, function(store, match, data))
                self.reply(404, {'errors': ['Not found']})
            except ReviewError as exc:
                self.reply(exc.status, {'errors': exc.messages})
            except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                self.reply(400, {'errors': [str(exc)]})

        def do_GET(self):
            self.handle_request('GET')

        def do_POST(self):
            self.handle_request('POST')

        def do_PUT(self):
            self.handle_request('PUT')
    return Handler


def serve(store, port=8765):
    return ThreadingHTTPServer(('127.0.0.1', port), handler(store))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', type=Path, default=DEFAULT_ROOT, help='blind-review root (default: current pilot)')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--db', type=Path, help='SQLite path (default: ROOT/app/review.sqlite3)')
    parser.add_argument('--export', action='store_true', help='write exports and exit')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        store = Store(args.root, args.db)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'{exc}\n')
    if args.export:
        print(json.dumps(store.export(), indent=2))
        return
    if any(any((args.root / d).iterdir()) for d in ['commits', 'comparisons', 'adjudications'] if (args.root / d).is_dir()):
        print('Note: this root also holds CLI-committed records; the app does not read or change them.')
    server = serve(store, args.port)
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    print(f'Gapper review: {url}  (Ctrl+C to stop)\nDatabase: {store.exports.parent}/review.sqlite3\nExports:  {store.exports}')
    if not args.no_browser:
        threading.Timer(0.3, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == '__main__':
    main()
