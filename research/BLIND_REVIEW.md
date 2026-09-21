# Independent human review and deferred AI comparison

Each human label is a **single-reviewer exploratory reference**, not validated
ground truth or evidence of human inter-annotator agreement.

## Initial review

Open `index.html` inside the `reviewer/` directory. This bundle contains only
source packets, source metadata, blank forms, and instructions. It has no AI
results, selection hints, candidate summaries, or links to AI annotations.
You can copy the entire reviewer directory elsewhere to review independently.

Read a packet and edit its `forms/PACKET_ID.json` file using the annotation guide.
Use `human_independent` for your own initial interpretation. Do not consult
AI drafts or ask an assistant that has read them to suggest your initial label.
If you already saw that packet's AI annotation, use `human_assisted` and disclose
that exposure. A prior general summary can also be disclosed separately.

Commit your completed label from the project directory:

```sh
python3 blind_review.py commit REVIEW_ROOT REVIEW_ROOT/reviewer/forms/PACKET_ID.json --exposure none
```

Use `--exposure prior_summary` if you saw earlier general findings, or
`--exposure ai_annotation` if you saw that packet's AI result. This records a
self-report; the software cannot prove what someone has or has not seen.
“Commit” here means save an immutable experiment record, not a Git commit.
Source material and labels must remain outside Git.

Commitment saves a separate copy. Editing the form afterward does not change the
original label. The tool refuses to overwrite a commitment. AI results must have
been sealed beforehand for a blind paired comparison; a human can still commit
without one, but that case will not get a retrospective blind-comparison claim.

## Reveal and compare

Only after committing:

```sh
python3 blind_review.py reveal REVIEW_ROOT PACKET_ID
```

This reveals only the corresponding packet's AI result. It stores both original
results, their hashes, the thread-label disagreement and episode counts. Different
local episode IDs are not automatically paired by position. Inspect evidence,
actor attribution, omitted/extra episodes, gap classes, and resolution separately.
An uncommitted packet cannot be revealed through this workflow.

Save an adjudication JSON file, then run:

```sh
python3 blind_review.py adjudicate REVIEW_ROOT PACKET_ID DECISION.json
```

Example structure (no corpus content):

```json
{
  "reviewer_id": "reviewer-a",
  "rationale": "Explain the comparison and final interpretation.",
  "episode_alignment": [],
  "disagreements": [
    {
      "dimension": "thread_label",
      "human": "unknown",
      "ai": "no_candidate",
      "decision": "unresolved",
      "rationale": "Explain why."
    }
  ]
}
```

Episode alignment entries should identify human/AI episode IDs (null for an
unmatched episode), the match decision, and rationale. Disagreements should cover
all material differences, not just the top-level label. An empty disagreement
list means the reviewer found none; it does not mean automated semantic agreement.
The adjudication is a third immutable record. It never replaces either original.

## Operator setup and separation

```sh
python3 blind_review.py init PILOT_DIRECTORY REVIEW_ROOT
python3 blind_review.py seal-ai REVIEW_ROOT AI_ANNOTATIONS.jsonl AI_PROVENANCE.json
```

The source-only packet is produced first; AI results are sealed separately under
`private/ai/`. New drafts may be generated alongside human work, but must not see
human labels and must be sealed before the paired human commitment. Preserve
model/prompt/run provenance and record any preexisting exposure. Current v1 AI
drafts cover seven calibration packets only; the remaining 130 have no AI result.
Do not fabricate or reuse another packet's annotation to fill gaps.

The gate prevents accidental exposure through the review commands. It is not an
OS security boundary against someone deliberately opening private files. Send
only `reviewer/` to a reviewer, never the entire operator workspace. Previously
published AI summaries cannot be made unseen; disclose exposure when applicable.
Original frozen pilot artifacts remain unchanged. This workflow has its own
manifest binding the source bundle and instructions.
