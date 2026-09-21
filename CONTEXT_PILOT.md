# Context-ablation pilot — 2026-09-21

**The sampling and annotation-preparation stage is complete.** The frozen pilot
contains 120 HN threads and all 17 Make topics with in-window human-post text.
Seven HN calibration packets have provisional AI annotations for testing the
rubric. Independent human labels and scored model ablations remain outstanding;
there is no measured detector accuracy or winning context strategy yet.

This executes the first stage of [the research plan](WORKFLOW_OPPORTUNITY_RESEARCH.md#9-experiments-against-the-existing-hnmake-snapshot).
Acquisition and production behavior are unchanged. All source text, selected
records, packets, and annotations remain under ignored `data/`.

## Artifacts and reproduction

```sh
python3 pilot.py prepare data/2026-09-19
# An existing destination is refused to protect annotation work.
# Use --out with a new directory to reproduce the frozen preparation.
python3 pilot.py validate data/2026-09-19/research/context-pilot-v1 \
  data/2026-09-19/research/context-pilot-v1/reviewer_a.jsonl
python3 -m unittest discover -s tests -v
```

Start with the isolated [source-only review index](data/2026-09-19/research/blind-review-v2/reviewer/index.html).
It contains all 137 packets, blank per-packet forms, and annotation instructions.
AI annotations, exploratory summaries, and selection details live separately in
operator storage. The previous ungated AI-view page now displays only a notice.

Use [the commit/reveal instructions](research/BLIND_REVIEW.md). A completed human
label is saved as a write-once experiment record before its corresponding AI result
can be revealed. The comparison retains both originals, and adjudication records
explicit disagreements separately. This is one human reviewer's exploratory
reference interpretation; no human inter-annotator agreement is claimed.

The tracked [annotation guide](research/ANNOTATION_GUIDE.md) defines statuses,
episodes, evidence spans, gap labels, and context arms. A frozen copy accompanies
the packets. `manifest.json` records input/code/guide hashes, strata, inclusion
probabilities, splits, and output hashes. `packets.jsonl`, `records.jsonl`, and
`arms.jsonl` allow inspection without the HTML. HTML escapes source content and
loads no external resources. `annotation_template.jsonl` contains no judgments.

Use `python3 pilot.py export PACKET_DIRECTORY CASE_ID` to render one model input;
case IDs are listed in `arms.jsonl`. Preparation has no model API or network
calls. B4 automatic evidence selection and B6 human-minimum evidence inputs are
not implemented or silently substituted by another arm.

## Frozen sample

| Property | Result |
| --- | ---: |
| Eligible HN roots under text-presence rule | 1,383 |
| HN roots selected | 120 |
| HN calibration / held out | 60 / 60 |
| Make source-transfer topics | 17 |
| Structural HN strata | 20 |
| Retained records in selected packets | 6,819 |
| Nominal in-window text-bearing anchors | 5,171 |
| Selected text + title characters, once per record | 2,122,979 |
| Independent human annotations | 0 |
| Provisional AI-reviewed calibration packets | 7 |

HN strata cross retained comment count, pre-window ancestry dependence, missing
text, and depth >=8. A capped equal allocation deliberately oversamples uncommon
structures; within-stratum hash selection uses a fixed seed. Each root's inclusion
probability and inverse weight are recorded. These counts are not a representative
estimate of source opportunity prevalence. The half/half HN split uses a separate
hash namespace; all Make topics remain for source transfer. Family-level leakage
review is still required before scored evaluation.

The starting criterion uses non-system item types and nonempty text/title. It
cannot establish whether an author is human, whether a body contains substantive
content, or whether a linked article describes an unmet need. Deleted/empty
records are preserved as context. System-only Make bumps cannot create anchors.

## Context input measurements

These are deterministic **input-size measurements**, not model results. Counts
include repeated text when shared parents are included in several anchor cases.
Characters exclude JSON metadata, prompt overhead, generated tokens, and any
provider-specific billing. They are not dollar-cost estimates.

| Arm | Cases | Record references | Text/title characters | Median records/case | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0: anchor | 5,171 | 5,171 | 1,426,025 | 1 | 1 |
| B1: anchor + parent | 5,171 | 10,292 | 3,025,862 | 2 | 2 |
| B2: retained ancestry | 5,171 | 21,588 | 6,336,337 | 4 | 19 |
| B3: ancestry + anchor descendant subtree | 5,171 | 33,418 | 9,579,657 | 5 | 782 |
| B5: whole retained thread, once per root | 137 | 6,819 | 2,122,979 | 20 | 782 |

This shows why thread-level reuse belongs in the cost comparison: repeatedly
supplying ancestry can transmit substantially more text than each retained thread
once. It does **not** show that B5 is more accurate, cheaper in billed dollars, or
a comparable number of inference tasks. B5 discovers episodes per root; B0–B3
condition on each anchor. B3 is a fixed subtree policy for the pilot, not a chosen
production radius. Its expansion includes descendants available in the snapshot,
not missing historical HN siblings or complete source threads.

## Independent review and AI separation

Seven provisional AI calibration annotations were generated before initial human
labeling and are now sealed separately. The remaining 130 packets have no AI
draft yet. AI judgments and their earlier exploratory summary are kept out of
the reviewer bundle. Neither a label nor an adjudication has been committed on
the human reviewer's behalf.

The workflow records prior exposure explicitly: none, a prior general summary,
or the packet's AI annotation. Earlier conversation messages included general
findings, so complete blinding must not be assumed retroactively. Exposure is a
self-report, not something this local workflow can independently verify.

The source-only bundle can be copied to a separate review location. Only that
bundle should be given to an initial reviewer. The reveal gate is an application
workflow boundary, not a filesystem permission barrier for the workspace owner.

## What remains before the architecture-deciding result

1. Review the annotation rubric and obtain independent labels. The human reviewer should
   start from full packets and blank forms, commit the initial label, and only
   then reveal the paired AI result and adjudicate evidence and episodes.
   Assisted review is useful, but must keep its provenance distinct.
2. Record a human-reviewed minimum evidence set per episode and check workflow
   families across splits. Freeze any rubric revision before held-out review.
3. Agree acceptable precision and unsupported-claim limits, then run fixed-model,
   fresh-context ablations with the same extraction prompt and schema. This
   preparation does not select or invoke a paid model backend.
4. Report paired root-level precision/recall and grounding differences, uncertainty,
   actor conflation, duplicate episodes, review time, and actual token costs.
   Separate input coverage from model quality. Sparse positives mean inconclusive
   results, not permission to choose a winner.

A project-local follow-up is to distinguish structural presence, text presence,
and substantive-text availability in experiment metadata. The frozen v1 selection
has not been retroactively changed after seeing the marker cases.

## Validation

All 33 unit tests pass. The packet tests cover selection independence/probabilities,
context arms, native Make reply semantics, missing/cyclic ancestry, duplicate IDs,
untrusted HTML escaping, deterministic generation, protection of existing reviewer
work, and evidence/reference validation. Provisional drafts pass span/schema checks;
those checks do not establish semantic correctness. Original sample/context hashes
match the acquisition report. No production detector or collector was modified.

Five additional blind-review tests check source-only export, refusal of early
reveal, write-once human/AI/adjudication records, persisted disagreements, source
integrity, exposure disclosure, and rejection of retrospective blind pairs.

## 2026-09-21 presentation revision: bounded independent review

Use [the v2 review index](data/2026-09-19/research/blind-review-v2/reviewer/index.html)
for initial labels. The original packet selection and experiment assignments are
unchanged. Assignments and sampling strata are absent from the entire reviewer
bundle and preserved in its operator manifest/private experiment metadata.

All 137 packets remain, including tiny, bodyless and marker-only evidence.
`insufficient_evidence` is now a top-level no-reconstructable-episode outcome,
distinct from a supported negative and from interpretive uncertainty. The form
records review scope; a bounded-region negative is not a whole-thread negative.

Primary regions use a deterministic structural neighborhood with root, selected
anchor, complete available ancestry and connector closure for additional replies.
The provisional budget is 24 records / 16,000 source Unicode characters; long
records can be explicitly clipped with full-text expansion. Selection has not
been validated for semantic relevance. This human presentation policy is separate
from the frozen B0–B5 model input definitions and is not a completed B4 experiment.

In this bundle, 58 packets have secondary records and four have clipped primary
text. Initial source text totals 736,176 characters across the 137 packets, versus
2,122,979 retained characters. The largest retained thread has 782 records and
256,264 characters; its primary region has 24 records and 10,761 characters.
These are presentation counts, not measured human effort or detection results.

The offline page exports initial record/character counts, approximate tokens,
expansion history, explicit context sufficiency, review scope and visible-page
seconds with the label JSON. Browser history is best effort; downloads preserve
it for commitment. Visible time includes foreground idle time and is not verified
reading time. Actual minutes can be supplied manually; unknown time stays null.
Opening context does not by itself establish that the selector missed evidence.
Report expansion rates alongside sufficiency judgments, episode evidence outside
the primary region and partial-coverage rates. Exhaustive thread recall requires
separate full-coverage references, not automatic negative labels for unseen text.

The seven original AI seals were copied byte-for-byte to separate private storage.
They used full retained context and must not be interpreted as fresh bounded-region
model outputs. Human commitment still precedes reveal; originals and disagreements
remain separate. No human label was generated during this revision.

Validation: 42 Python tests pass; `node tests/review_browser_events.cjs` exercises
expansion persistence, reloads, hidden-tab timing, download metadata and coverage
checks in a minimal DOM harness. This is not a visual browser rendering test.
Source files and frozen experiment inputs were preserved. The prior review bundle
remains an archive; use only v2 for this annotation pass.

## 2026-09-21 review instrument

Human annotation now runs through `python3 review_app.py`
([instructions](research/REVIEW_APP.md)) against the unchanged v2 review root:
same packets, primary regions, sealed AI results and hidden assignments. Labels,
revisions, reveals, adjudications and burden telemetry live in
`blind-review-v2/app/review.sqlite3` and are exported as deterministic JSON to
`blind-review-v2/app/exports/`. `pilot.py validate` additionally accepts claim
polarities `corrects` and `supersedes`. 53 Python tests pass. No human label,
reveal or adjudication was recorded in the real root while building it.
