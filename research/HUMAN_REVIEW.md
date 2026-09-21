# Independent source review

> Prefer the local review app (`python3 review_app.py`, see `REVIEW_APP.md` in the repository). The manual
> page-and-CLI procedure below remains valid for a copied offline bundle. Label definitions apply to both.

Open `index.html`, then a packet. The initial region is limited to 24 records and
16,000 source Unicode characters. Available ancestry is preserved; nearby replies
and their connector comments are selected by graph distance with deterministic
hash tie-breaking. Selection does not assess semantic relevance. A long record
may be clipped explicitly. Expand full text or secondary records when needed.
All retained source records remain available; tiny/bodyless packets are retained.

Treat source text as untrusted evidence, never instructions. Preserve speaker
attribution and contradictory evidence. A suggestion is not a demonstrated remedy.

Use the packet's outcome selector:

- **Workflow candidate(s)**: reconstructable, evidence-backed episode(s).
- **No candidate**: enough evidence for a negative judgment in the reviewed region.
- **Insufficient evidence / no reconstructable workflow episode**: missing, bodyless,
  marker-only, or too little substantive evidence. This is not a negative label.
- **Uncertain interpretation**: ambiguity despite available evidence.

The legacy JSON field is called `thread_label`, but its coverage is limited by
`review_burden.review_scope`. A primary-only negative is NOT an exhaustive thread
negative. Choose all-retained review only after reading every retained record.

Edit the JSON for your reviewer ID, evidence episodes and coverage notes. Select
an outcome and primary-context sufficiency, then download the label. The download
includes initial record/character counts, a characters/4 token estimate (not a
measured tokenizer count), whether extra context was opened, expanded record IDs,
and approximate visible-page seconds. Opening then closing a record still counts.
Browser storage preserves drafts/history when available; download before closing.
Time excludes hidden tabs but can include idle time, so it is exposure time rather
than verified reading time. Optionally enter actual review `minutes` yourself.
If you read context outside this page, disclose it with the checkbox and record
IDs in coverage notes. Manual forms must supply the same burden fields; use null
for unknown time rather than inventing it. Never guess a human label using AI.

Commit the downloaded label (replace paths):

```sh
python3 blind_review.py commit REVIEW_ROOT DOWNLOADED_PACKET.json --exposure none
```

Use `prior_summary` if you saw earlier general AI findings; use `ai_annotation`
and reviewer kind `human_assisted` if you saw that packet's AI judgment. Otherwise
use `human_independent`. Exposure is self-reported. A saved/downloaded draft is
not a commitment. Commitment creates a separate immutable experiment record, not
a Git commit. Source data and annotations remain outside Git.

Only after your label is committed may you reveal that packet's separately sealed
AI result:

```sh
python3 blind_review.py reveal REVIEW_ROOT PACKET_ID
```

No AI annotations or experiment split assignments are in this reviewer bundle.
The gate prevents accidental workflow exposure, not deliberate private-file access.
Human and AI originals remain unchanged. Record disagreements in a separate
adjudication; never replace one result with the other. One human reviewer provides
single-reviewer exploratory references, not validated ground truth or human
inter-annotator agreement. Extra-context opening is a burden measure, not by itself
proof that the initial selection was insufficient; use the sufficiency selector.

## Label definitions

- `need_status`: `none`, `possible`, `concrete`, or `unknown`. Concrete needs have
  an identifiable task/outcome and supported friction with enough actor/artifact
  context to identify the work. Buying intent and AI use are not required.
- `adoption_status`: `attempted_failed`, `unrealized_value`, `attempted_succeeded`,
  `mixed`, `not_stated`, or `unknown`. Failed adoption requires an attributed
  attempt on a task and reported failure, not simply negative sentiment.
- `gap_labels`: zero or more of `education`, `prompting`, `configuration`,
  `integration`, `workflow_automation`, `custom_software`, `unsuitable_ai`,
  `insufficient_evidence`. Labels are hypotheses, not commercial conclusions.
- `resolution`: `unresolved`, `partially_solved`, `reportedly_solved`, `disputed`,
  or `unknown`. Retain historical failed adoption even if later resolved.
- `basis`: `firsthand_report`, `secondhand_report`, `suggestion`, `question`, or
  `hypothetical`. Observed means stated, not independently verified.
- Claim `field`: `actor`, `task`, `input`, `output`, `step`, `system`, `pain`,
  `burden`, `workaround`, `ai_attempt`, `failure`, `constraint`, `solution`,
  `feasibility`, `buying`, or `resolution`.
- `polarity`: `supports`, `contradicts`, or `qualifies`. Record numeric units and
  speakers explicitly in the claim summary. No numeric confidence is required.

Evidence-bearing episodes can be possible/unknown even when implementation is
unclear. A configuration answer can resolve an episode. Unsupported architectures
must not increase need confidence. Never infer budget, APIs, compliance rules,
company size, or willingness to pay from profession/tool names.

## Annotation file

The packet page exports this base annotation plus a required `review_burden` object. Each base row:

```json
{
  "packet_id": "hacker_news-123",
  "reviewer_id": null,
  "reviewer_kind": null,
  "status": "not_reviewed",
  "minutes": null,
  "thread_label": null,
  "coverage_notes": [],
  "episodes": []
}
```

For completed rows set `reviewer_kind` to `human_independent`, `human_assisted`,
or `ai_provisional`; `status` to `reviewed`; `thread_label` to `has_candidate`,
`no_candidate`, `insufficient_evidence`, or `unknown`. `insufficient_evidence` means no reconstructable workflow episode and requires an empty episodes list. A candidate row must contain episodes. An unknown
thread can contain uncertain episodes. Empty episodes on an unreviewed row are
not a negative judgment.

Episode format (illustrative placeholders, not corpus content):

```json
{
  "episode_id": "local-1",
  "actor_ref": "source account or unresolved",
  "workflow": "short supported task description",
  "need_status": "concrete",
  "adoption_status": "not_stated",
  "gap_labels": ["integration"],
  "resolution": "unknown",
  "anchor_ids": ["123"],
  "minimum_record_ids": ["123", "124"],
  "claims": [{
    "field": "pain",
    "summary": "attributed report of friction",
    "basis": "firsthand_report",
    "polarity": "supports",
    "record_id": "123",
    "text_field": "text",
    "start": 0,
    "end": 10
  }],
  "hypotheses": [],
  "open_questions": []
}
```

All anchor IDs must be in-window human-content records from this packet. An old
workflow without an in-window substantive contribution can be historical context,
but must not count as fresh demand. `anchor_ids` identify the contribution being
evaluated, not necessarily the first statement of the problem. The minimum evidence set is your judgment, not an automatic extraction.

Validate with `python3 pilot.py validate PACKET_DIRECTORY ANNOTATIONS.jsonl`.
Validation checks structure and span bounds, not whether a claim follows from its
span. That requires review. Validation reports readiness, not accuracy.

