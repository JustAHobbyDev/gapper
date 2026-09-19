# Hacker News conversation structure — September 18–19, 2026

**Every sampled comment has a complete structural path to its root. However,
4,210 of 11,616 comments (36.24%) need pre-window history.** Supplying those paths
requires 3,440 distinct historical records: 3,053 comments and 387 stories.
Full textual ancestry is available for 99.13% of comments under the definition
below; including the sampled comment's own text lowers this to 96.25%.

## Scope, definitions, and reproduction

Window: **2026-09-18 08:00 UTC inclusive → 2026-09-19 08:00 UTC exclusive**.
Inputs are the existing `data/2026-09-19/{sample,context}.jsonl` and `manifest.json`.
HN alone contributes 12,988 sample records (11,616 comments, 1,371 stories, one
job) and 3,440 context records. Make's 551 context records are excluded.

```sh
python3 conversations.py data/2026-09-19
python3 -m unittest discover -s tests -v
python3 verify.py data/2026-09-19
```

The offline analyzer writes ignored local artifacts under
`data/2026-09-19/conversations/`: `summary.json` (statistics, denominators, anomalies,
input and analyzer SHA-256s), `comments.jsonl` (each comment's ancestor IDs, context
IDs, depth, failures and text gaps), and `threads.jsonl` (every represented root's
sample size and maximum depth). Run the same command with another collection
folder to reproduce these measurements. This report is a fixed interpretation
of this window. No acquired text is copied into tracked files.

Method: index HN records by native ID; independently traverse native `parent`
links, tracking visited IDs; stop at a parentless story/poll/job. Compare computed
roots/depths and native relationships with normalized fields. Audit sample and
context together, without relying on the collector's “no missing parents” result.
There is no networking, keyword filtering, content classification, or collector
change. Duplicate IDs are reported; conflicting native payloads are excluded
from the graph instead of arbitrarily selected. None occur here.

Definitions:

- **Depth** = ancestor hops, including the root: direct reply to root = 1.
- **Context** = record in `context.jsonl`; **pre-window** = native creation time
  before the start. All 3,440 HN context records are pre-window, with none after
  the cutoff or of unknown age. These concepts coincide in this run.
- **Structurally complete** = all nodes on root → … → parent → comment exist,
  with valid types and no cycle. This does not mean a full thread with siblings
  or descendants was collected. A cached root ID alone does not prove a path.
- **Text available** = native HTML yields nonempty text after tag removal and
  whitespace trimming. This measures presence, not meaning or adequacy. Dead
  flags do not automatically remove returned text; deleted records stay in the
  structural graph.
- **Full textual ancestry** = all ancestor comment bodies plus root title
  present. A submission body is optional and measured separately; external
  articles are not fetched. This metric excludes the sampled comment's own body
  unless explicitly stated. Missing optional root bodies are not text gaps.
- Percentages use **11,616 sampled comments** unless stated otherwise. Quantiles
  use nearest rank (`ceil(p × n)`); median uses the ordinary midpoint average.
  Depth/context distributions use complete chains, which here include every
  comment. Per-comment context counts include the root, exclude the comment
  itself, and are not deduplicated across comments.

## Parents, roots, and complete paths

| Measure | Comments | % |
| --- | ---: | ---: |
| Comment record present, before adding ancestry | 11,616 | 100.00 |
| Direct parent available | 11,616 | 100.00 |
| Parent in sample | 9,308 | 80.13 |
| Parent in context / pre-window | 2,308 | 19.87 |
| Parent unavailable | 0 | 0.00 |
| Parent is a comment | 8,906 | 76.67 |
| Parent is a story/root | 2,710 | 23.33 |
| Root resolved and available | 11,616 | 100.00 |
| Root in sample | 7,406 | 63.76 |
| Root in context / pre-window | 4,210 | 36.24 |
| Root unavailable | 0 | 0.00 |
| Full ancestor chain available | 11,616 | 100.00 |
| All ancestors in sample | 7,406 | 63.76 |
| At least one context / pre-window ancestor | 4,210 | 36.24 |

Every comment resolves to a **story**; zero resolve to jobs, polls, or unexpected
root types. The sampled job has no sampled comments. Having an in-window direct
parent is insufficient: **1,902 comments (16.37%)** have such a parent but still
need older ancestry. Root-hop counts are exactly the depth distribution below.

Independent traversal agrees with the prior missing-parent validation, and also
finds no broken chains or cycles. In general these tests differ: available direct
parents alone do not rule out a cycle or an unavailable ancestor further up.
A stored root record can also exist despite a missing intermediate node; the
analyzer tests that case explicitly.

## Depth and historical context per comment

| Statistic | Depth / root hops | Context records required |
| --- | ---: | ---: |
| Minimum | 1 | 0 |
| Median | 3 | 0 |
| Mean | 3.276 | 0.965 |
| p75 | 4 | 1 |
| p90 | 6 | 3 |
| p95 | 8 | 5 |
| p99 | 10 | 9 |
| Maximum | 20 | 20 |

| Depth | Comments | % |
| --- | ---: | ---: |
| 1 | 2,710 | 23.33 |
| 2 | 2,555 | 22.00 |
| 3 | 2,137 | 18.40 |
| 4 | 1,496 | 12.88 |
| 5 | 1,006 | 8.66 |
| 6 | 640 | 5.51 |
| 7 | 432 | 3.72 |
| 8 | 266 | 2.29 |
| 9 | 177 | 1.52 |
| 10 | 81 | 0.70 |
| 11 | 55 | 0.47 |
| 12 | 24 | 0.21 |
| 13 | 15 | 0.13 |
| 14 | 13 | 0.11 |
| 15 | 3 | 0.03 |
| 16 | 3 | 0.03 |
| 17 | 1 | 0.01 |
| 18 | 1 | 0.01 |
| 19 | 0 | 0.00 |
| 20 | 1 | 0.01 |

Among only the **4,210 history-dependent comments**, historical records required
have median **2**, mean **2.663**, p90 **6**, p95 **7**, and maximum **20**.
The full count histogram is in `summary.json`.

Deep-chain inspection examples (IDs only; full paths in the local summary):

| Sample comment | Root | Depth | Historical ancestors |
| --- | --- | ---: | ---: |
| 49760983 | 49701104 | 20 | 20 |
| 49760618 | 49753211 | 18 | 0 |
| 49760375 | 49753211 | 17 | 0 |
| 49753184 | 49701004 | 16 | 16 |
| 49758856 | 49753211 | 16 | 0 |

All five have distinct IDs along each path, valid comment-to-parent links, a
story root, nondecreasing creation timestamps, and full textual ancestry. The
depth-17 and one depth-16 example are prefixes of the depth-18 chain. The depth-20
comment replies to historical parent 49734536; its depth-19 ancestor is outside
the window, explaining the empty depth-19 sample bin. These are structurally
consistent chains, not evidence of a traversal loop. No semantic judgment of
conversation content was made.

## How much additional history is needed?

The **3,440 unique ancestors outside the sample** are all used by sampled comments;
none of the retained HN context is surplus to their paths. This is **29.61 extra
records per 100 sampled comments**, or **26.49%** additional records relative to
the entire 12,988-record HN sample. The union of all required ancestors is 8,298
records: 4,858 already in-window and 3,440 historical.

There are **11,210 historical ancestor occurrences** across individual paths.
Deduplicating by ID reduces this to 3,440 stored records, averaging 3.26 uses per
historical record. Only **1,467** unique historical records are immediate parents;
**1,973** additional unique historical records occur further up. Retaining only
immediate parents would therefore miss substantial required ancestry.

The acquisition report records **2,683 additional ancestor requests** beyond its
16,000-ID enumeration. The other **757** needed historical records were already
in the enumerated range. Retained records and extra fetches are different costs:
this run needed 3,440 retained historical records, but only 2,683 extra item
lookups beyond enumeration. This is not an HTTP-attempt count or a prediction
for another window/cache state.

Required history extends to **2026-09-01 15:01:17 UTC**, **16.707 days before the
window start**. Across unique historical records, age before start has median
0.647 days, p90 3.547, p95 5.165, and p99 9.394. A fixed one-day lookback would
not reproduce these paths; neither would the collector's six-hour enumeration
guard by itself. Ancestor retrieval supplies the older records.

## Thread-level structure

There are **893 distinct comment-bearing roots**, all stories. Of these, **506
(56.66%)** are in-window and **387 (43.34%)** predate it. The older roots contribute
4,210 comments (36.24% of the comment stream). An additional **866 sampled
submissions** have no sampled comments; including them gives **1,759 represented
roots**, of which 387 (22.00%) predate the window. Thread-size statistics below
use the 893 comment-bearing roots, not those 866 zero-comment submissions.

Comments per root within this sample: minimum **1**, median **1**, mean **13.008**,
p75 **4**, p90 **21**, p95 **67**, p99 **245**, maximum **837**.

| Sample comments per root | Roots | % of 893 |
| --- | ---: | ---: |
| 1 | 484 | 54.20 |
| 2–5 | 235 | 26.32 |
| 6–10 | 46 | 5.15 |
| 11–25 | 46 | 5.15 |
| 26–50 | 26 | 2.91 |
| 51–100 | 30 | 3.36 |
| 101–250 | 18 | 2.02 |
| 251–500 | 6 | 0.67 |
| 501+ | 2 | 0.22 |

| Largest roots included | Sample comments | % of stream |
| --- | ---: | ---: |
| 1 | 837 | 7.21 |
| 5 | 2,649 | 22.80 |
| 10 | 3,927 | 33.81 |
| 20 | 5,710 | 49.16 |
| 50 | 8,175 | 70.38 |

The largest root is 49752056 (837 comments); next is 49753211 (781). Thus nearly
half the sampled comments occur under 20 of 893 comment-bearing roots (2.24%).
These are observed window sizes, not complete lifetime thread sizes. Context
retrieval adds ancestors, not all historical siblings or future replies.

## Text availability and moderation edge cases

| Measure | Comments | % |
| --- | ---: | ---: |
| Sample comment body available | 11,248 | 96.83 |
| Parent body available, regardless of parent type | 9,275 | 79.85 |
| Parent conversational text available (comment body or root title) | 11,527 | 99.23 |
| Root title available | 11,516 | 99.14 |
| Root body available | 1,325 | 11.41 |
| All textual ancestors available (root title + ancestor comment bodies) | 11,515 | 99.13 |
| Full path text, also requiring sampled comment body | 11,180 | 96.25 |
| At least one structural ancestor missing required text | 101 | 0.87 |
| At least one ancestor comment missing its body | 1 | 0.01 |
| At least one deleted ancestor | 6 | 0.05 |
| At least one dead ancestor | 360 | 3.10 |

Among the 8,906 comments whose parent is another comment, **8,905 (99.99%)** have
that parent's body. Every one of the **368 bodyless sampled comments** is marked
deleted. There are also 620 sampled comments marked dead; returned nonempty text
is counted even when flagged.

Across distinct roots, **811/893 (90.82%)** have titles and **106/893 (11.87%)**
have bodies. Root body absence is generally not enough to diagnose loss: a linked
submission can have a title/URL without a body. As an explicit applicability
proxy, **140 roots lack an external URL**, and **54/140 (38.57%)** have bodies;
they account for 344 sampled comments, 234 of which have root bodies (68.02%).
This is a field-presence proxy, not a classification of submission kind; deleted
metadata can also omit URLs. The archived corpus cannot tell whether an absent
optional body ever existed. Requiring *every* ancestor body, including the root,
would give 1,325 comments (11.41%), but would conflate bodyless submissions with
missing conversational replies.

Text gaps come from **82 root records without titles**, affecting **100 comments**,
and **one deleted ancestor comment**, 49759313, affecting one other comment.
All 83 records are deleted and/or dead. Of the roots, 77 are dead only, four
are deleted only, and one has both flags. These text gaps are not broken links.
The historical context itself has **no bodyless comments**: all 3,053 retained
historical comment bodies exist. Its 387 roots include one deleted, untitled
story. Dead ancestors often retain usable text under the presence definition;
360 comments having dead ancestors does not mean 360 text failures.

## Structural anomalies and validation

Across all **16,428 retained HN records**, the audit found zero missing referenced
parents, self-parent references, cycles, invalid parent types, roots with parent
links, duplicate record IDs, conflicting native records, duplicate child IDs,
or retained child-list entries disagreeing with their child's parent. Every
sampled comment has a valid root and unbroken chain; no unexpected root type
occurs. Native IDs/types/parents agree with normalized fields; computed roots
and depths agree with stored values. No parent is newer than its child, and
there are no scope/window or missing-time anomalies.

The child-list audit checks listed children that are retained; it does not
require every listed sibling to be collected or every child to appear in a
moderation-affected parent listing. Parent links define the reconstructed paths.

All **21 unit tests pass**, including missing intermediate ancestry despite a
cached root, deleted/dead text, shared historical ancestors, cycles, invalid
root types, conflicting duplicates, percentile rules, and deterministic exports.
The independent corpus verifier also reports zero integrity errors and zero
missing referenced parents. Original corpus hashes remain unchanged:

- Sample: `f9b02d102512da25ee62cc4d0ce93049389cfa4aa000a2ca306e62e61c2bc128`
- Context: `0c9ad2b7fa85ef1e6271a494835df6e0ef49af947a79358bd7ac6fde28925f7c`

## Implications for acquisition and context retrieval

For this window, retaining **3,440 deduplicated historical records** alongside
the chronological sample makes **100% of comment paths structurally recoverable**.
A root-only or immediate-parent-only strategy cannot supply all intermediate
conversation context. Following ancestors to the root and reusing records by ID
captures the observed requirement, including the long tail beyond a day of
history and up to 20 historical ancestors for one comment.

The observed median hides the acquisition burden: 63.76% need no outside history,
but 36.24% do. Percentile-based depth or age caps would leave some paths incomplete
and should be reported as such. Preserve metadata even when text is absent, and
track structural and textual completeness separately; additional traversal alone
cannot recover text missing from the archived source response.

These are retrieval-time snapshots from one observed day. Complete ancestry does
not prove complete historical text, source coverage, or availability of linked
articles and surrounding siblings. The measurements support context acquisition
planning only; no opportunity detection or semantic analysis was performed.
