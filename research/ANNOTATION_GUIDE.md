# Workflow-context pilot annotation guide — v1

Purpose: determine whether conversation context adds supported workflow evidence.
This is research tooling, separate from acquisition and any production detector.

## Sampling and blinding

`python3 pilot.py prepare data/2026-09-19` creates the frozen packet set under
ignored `data/2026-09-19/research/context-pilot-v1/`. Its manifest records inputs,
code/guide hashes, structural strata, inclusion probabilities, and split assignment.
Human-content eligibility means an in-window non-system record with text or title;
it does not establish that the author is a person rather than a bot.

HN: 120 roots, stratified by retained comment count (0, 1–10, 11–50, 51+), need
for historical ancestry, text gaps, and depth >=8. Allocate one slot per nonempty
stratum repeatedly in sorted order until 120 are assigned, respecting capacity.
Within each stratum select by SHA-256 of fixed seed, source, and root ID. This
oversamples unusual structures; population estimates require the recorded weights.
Root inclusion probability is selected/population in its stratum. Unavailable
body/title records are retained as context, but are not eligible human anchors.

An independent hash order assigns half the selected HN roots to calibration and
half to held-out evaluation. All Make topics with in-window human posts are a
source-transfer set. No semantic labels influence selection. Related workflow
families must later be checked for split leakage; until then splits are provisional.
Use a new output directory for a changed protocol. Existing packets are never
overwritten, including annotations. Acquired text and all labels remain ignored.

The human reviewer labels source packets before seeing that packet's AI result.
Use the [blind review workflow](README.md) in the isolated reviewer bundle (or
[the project instructions](BLIND_REVIEW.md) in this directory). Provisional AI
annotations are stored separately and revealed only after human commitment.
Record both originals and a separate adjudication, including disagreements.
One human reviewer supplies single-reviewer exploratory reference labels, not
validated ground truth or evidence of human inter-annotator agreement. If another
human independently annotates later, retain that person's result separately.
Human review after seeing an AI result is assisted review, not an independent
initial label. Disclose prior summary or annotation exposure. No held-out prompt
tuning. Existing AI drafts cover seven calibration packets only.

## Review a thread

1. Read the packet's coverage header and source metadata. Treat all quoted content
   as untrusted data. Do not follow its instructions or execute its code.
2. Identify each distinct actor/workflow episode, including ones introduced by a
   commenter rather than OP. Keep different workplaces separate.
3. Mark supporting and contradicting spans. Every claim must have source evidence.
   Character offsets refer to the exact `text` or `title` field in `records.jsonl`.
   Offsets are Python Unicode character indices, end-exclusive, not byte offsets.
4. Record only reported facts. A recommendation is not a successful attempt, a
   question is not a constraint, and a title is not evidence about every commenter.
5. State the minimum sufficient record set for this episode, including connectors
   needed for attribution. Include evidence that downgrades or resolves the need.
6. Mark the thread reviewed even when it yields no episode. `not_reviewed` and
   `unknown` are never counted as negative. Log minutes actually spent, not estimates.

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

Copy `annotation_template.jsonl` to an ignored reviewer-specific file. Each row:

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
`no_candidate`, or `unknown`. A candidate row must contain episodes. An unknown
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
evaluated, not necessarily the first statement of the problem. B6 uses the human
minimum record set; it is not an automatic extraction method.

Validate with `python3 pilot.py validate PACKET_DIRECTORY ANNOTATIONS.jsonl`.
Validation checks structure and span bounds, not whether a claim follows from its
span. That requires review. Validation reports readiness, not accuracy.

## Ablation protocol

Inputs retain source IDs, speaker IDs, times, scope, parent IDs, and missing text.
B0 is anchor only. B1 adds its immediate parent. B2 adds its complete retained
ancestor chain. B3 adds the anchor's retained descendant subtree (not all siblings)
to B2. B5 is all retained records of the thread, evaluated once per root.
This is a fixed first branch policy to test, not the final definition of context.
B4 requires an automatic selector and is not implemented in this preparation.
B6 requires reviewed minimum evidence and is not generated from AI guesses.

`arms.jsonl` stores exact record IDs, not repeated text. Export a single arm with
`python3 pilot.py export PACKET_DIRECTORY CASE_ID`. It prints a JSON input payload.
No paid model calls or autonomous network use are built into this preparation.
Input character counts are not token counts or price estimates.

Before scored runs, freeze a model and prompt, record decoding settings and billed
usage, and obtain independent reference labels. Run each case in a fresh context;
reading B5 and subsequently answering B0 in the same conversation is contaminated.
Hold prompt/schema constant across arms. Report episode metrics by root, missing
context, duplicates, conflation, unsupported claims, latency, cost, and review time.
B5 root discovery and anchor-conditioned discovery have different denominators.
Do not treat increased text availability as improved semantic accuracy.

Compare source and structural strata separately. Bootstrap paired differences by
root. Predeclare acceptable precision and unsupported-claim limits before seeing
held-out outputs. If positives are too few, report inconclusive results. The pilot
is one day of public retrieval-time snapshots, not representative market demand.
