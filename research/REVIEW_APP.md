# Human review app

A local browser instrument for the context-ablation pilot. It replaces editing
JSON and downloading one file per packet. It is not a general annotation tool.

```sh
python3 review_app.py            # current pilot root; opens http://127.0.0.1:8765/
python3 review_app.py REVIEW_ROOT --port 8765 --no-browser
python3 review_app.py --export   # regenerate exports without starting the server
```

Python 3 standard library only; binds to loopback; no accounts or network use.
`REVIEW_ROOT` is a `blind_review.py init`/`upgrade` root. Source integrity is
checked against its manifest on start and on every commit. The app reads only
`reviewer/` source files; `private/ai/` is read only by the gated reveal.

## Reviewing

Enter a reviewer ID once (and whether you have seen earlier general AI findings
about the corpus). Both are stored locally and written into every record. Change
them from the reviewer chip in the top bar. Use **Resume**, **Next/Prev**, the
jump box, or the queue. Progress counts packets with a committed human review.
Split and sampling assignments never reach the browser.

The left pane shows the bounded primary region as a thread: root, structural
anchor, its ancestors and replies, and `in window` versus `earlier context`.
The region is chosen by structure, not relevance; display does not imply
evidence. **Show additional thread context** reveals collapsed supplemental
branches that open one level at a time; the whole retained thread stays
reachable. Search covers the displayed records and reports only a count for
undisplayed ones until context is opened, because snippets would be unrecorded
exposure.

Pick an outcome. *No workflow opportunity* and *Insufficient textual evidence*
need nothing else except the context-sufficiency answer, so tiny or bodyless
packets take a few keystrokes (`4`, sufficiency, `Ctrl+Enter` twice). For
episodes, press **+ Evidence** on a comment or select text inside one, choose a
role, basis and relation (supporting, contradicting, correcting, superseding,
qualifying), and write a one-line summary. Source IDs, field, code-point offsets
and a hash of the source text are stored automatically. Only the workflow
description and one evidence link from an in-window record are required per
episode; every other field is optional and omitted from the record when empty.
Press `?` for keyboard shortcuts.

Drafts autosave to SQLite. **Commit human review** writes an immutable revision.
Later corrections use **Revise**, which requires a reason and adds revision N+1;
earlier revisions cannot be updated or deleted (enforced by database triggers).

## AI isolation, comparison and adjudication

Before a human commit, no response contains AI labels, evidence, summaries, or
even whether an AI result exists; the comparison endpoints return 403. After
commit, **Compare with AI annotation** appears when a result was sealed before
that commit and its hash still matches. Revealing is recorded once. Any later
human revision of that packet is recorded as `human_assisted` with
`ai_annotation` exposure, and the exported human reference remains the last
independent revision.

The comparison shows both sides with differing labels, gap classes and evidence
records highlighted, human-only and AI-only episodes, and AI hypotheses or
evidence roles with no counterpart in the human review. Episode pairing is a
suggestion from shared evidence records; correct it with the selector. Record
each item as accept human, accept AI, merged, or unresolved. An adjudication is
a third versioned record holding hashes of both originals; it never edits them.

## Storage and exports

`REVIEW_ROOT/app/review.sqlite3` keeps separate tables for drafts, telemetry,
commits, reveals (with the AI snapshot as revealed) and adjudications. Packet
source files and sealed AI files stay where `blind_review.py` put them.

Every commit, reveal and adjudication regenerates `REVIEW_ROOT/app/exports/`
(also **Export** or `--export`). The same database state yields the same bytes.

| File | Content |
| --- | --- |
| `human_reference.REVIEWER.jsonl` | Last independent revision per packet, in the `pilot.py validate` annotation schema |
| `human_commits.jsonl` | Every revision with commit metadata, initial context and sealed-AI hash |
| `ai_annotations.jsonl` | AI results **revealed so far**, never pending ones |
| `comparisons.jsonl`, `adjudications.jsonl` | Reveal records with differences; adjudication versions |
| `telemetry.jsonl` | Per packet and revision cycle: start, visible/active seconds, context opened, supplemental records viewed |
| `experiment_metadata.json` | Protocol, manifest and code hashes, counts, file hashes. Join split assignments from `private/experiment_packets.jsonl` by `packet_id`; they are not copied here |

Annotations reuse the pilot schema. Episodes add an optional `details` object
(desired outcome, steps, artifacts, systems, friction, burden, current approach,
constraints, commercial signals), claims add `claim_id`, `span_kind`
(`record` or `span`), `relates_to`, `in_minimum_set` and `text_sha256`, and
`polarity` also accepts `corrects` and `supersedes`. `review_burden` keeps the
v2 fields and adds `active_seconds`, `started_at`, supplemental counts, episode
and claim counts and `revisions_after_commit`. `anchor_ids` are the cited
in-window records; `minimum_record_ids` are cited records left in the minimum set.

Measurement limits: visible seconds count a foreground tab; active seconds also
need input within the last 60 s. Neither verifies reading. A supplemental record
counts as viewed after one second on screen. `review_scope` is `all_retained`
only when every supplemental and clipped record was viewed. Nothing else about
interaction is logged. `minutes` stays null rather than being invented.

The CLI `commit`/`reveal`/`adjudicate` path in `blind_review.py` still works but
writes files the app does not read. Use one path per review root; use the app
for this pilot. Blinding remains workflow separation, not an OS access boundary.

## Validation

`tests/test_review_app.py` covers no-episode, single and multiple episodes, a
large bounded packet with supplemental viewing, a bodyless packet, restart and
resume, commit immutability and revisions, AI and split inaccessibility before
commit (store and HTTP), comparison, adjudication versions, assisted revisions,
seal tampering, deterministic exports with surviving source IDs and spans, and
refusal of foreign Host/Origin requests. The same steps were exercised once in
headless Chromium against the real 137-packet root with a scratch database,
including the 782-record thread (24 records initially; about 0.2 s to re-render
with all 782 expanded) and text-selection evidence. No human label was created
in the real review root by that check.
