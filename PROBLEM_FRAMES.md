# Problem Frames

## Entry #1 — 2026-09-19 — Raw public acquisition probe

### Domains

The machine is a local, restartable acquisition CLI. The user (biddable) chooses
the experiment. Public HN and Make services (causal interfaces with independently
changing state) expose public items and topic relationships. Their authors and
moderators are biddable and may edit/delete content independently. API responses
are lexical snapshots. The machine creates and owns a local response archive,
normalized corpus, context corpus, and coverage report. Git stores code, tests,
and documentation; downloaded content remains outside version control.

Boundary: unauthenticated GET requests out; HTTP responses and timestamps in;
local files out. No source writes, accounts, outreach, external article fetching,
classification, or model calls. Public handles/text remain in local source records.

### Frame split

1. Acquisition: Transformation of enumerated source responses into chronological
   records, preserving originals and inclusion decisions.
2. Conversation context: Information Display plus Transformation of parent/root
   relationships into separately marked supporting records.
3. Coverage: Information Display of counts, text availability, failures, gaps,
   pagination boundaries, and reconstruction limits.

### Requirements (per frame, with explicit out-of-scope)

1. Approximately 24 hours of recent publicly retrievable creations from both
   sources, without topical queries or category selection. All available item
   types retained, including moderation flags. Edits of older creations are not
   themselves new in-window items. No opportunity scoring.
2. Preserve native IDs, explicit reply links, thread roots, and supporting context
   so sampled conversations can be inspected. No claim to reconstruct unavailable
   posts, every sibling, or historical content as it existed at creation time.
3. Count only deduplicated in-window items as the sample; quantify extra context
   separately. Report unavailable content and stopping assumptions, not a claim
   of absolute completeness. Never equate source-side ID gaps with lost public posts.

### Invariance test

Pass for archived snapshots and observable enumeration. Reject an unconditional
claim of complete historical capture: APIs are live, moderation changes content,
timestamps need not perfectly follow identifiers, and public visibility differs
from all stored content. Use a fixed UTC interval, preserve retrieval times, scan
past its lower boundary with a six-hour guard, and expose the evidence/assumptions.
An ID traversal does not prove that no backdated/imported content exists elsewhere.

### Stakeholder test

The immediate stakeholder is a researcher inspecting an unselected corpus.
Existing search/ranking products serve relevance-seeking users; borrowing their
keyword or popularity selection would undermine this experiment. No named tool
is being cloned. Use source-native enumeration instead of a search analogy.

### Open questions — decided here, with reasoning

- Project alias/path: gapper, `~/p/gapper`; local Git repository on main.
- Interval: default end is latest completed UTC hour; inclusive start, exclusive
  end, 24 hours. Save once in manifest and reuse on resume. Explicit end supported.
- HN: snapshot maxitem, enumerate every ID backward in batches, include all kinds;
  stop only after a sufficiently populated entire batch is older than start minus
  six hours. Record nulls, missing timestamps, failures, and observed inversions.
  Fetch transitive ancestors/poll roots separately; do not recursively crawl kids.
- Make: paginate public `/posts.json?before=ID` across all exposed categories.
  Use the same guarded lower boundary and detect non-advancing pagination. Retain
  every exposed post type. Fetch participating topics and their available post
  streams for context; record stream gaps and limits. Null reply-to means a reply
  to the topic, not necessarily the immediately preceding post.
- Sources share one interval. Context fetched later may include post-window edits
  or creations; scope labels prevent mixing them into sample counts.
- Public unauthenticated visibility only. Identify the client; use bounded
  concurrency, throttling, retries/backoff and Retry-After. Do not bypass denials.
- Persist raw response payloads and request metadata including non-success/null
  responses. Cache successes for resume; retry failed requests on a subsequent run.
- Caps prevent runaway acquisition and are reported as partial when hit. Unknown
  or failed coverage is never silently treated as zero content.
- Keep the ten-record exploratory artifact separate if later provided; it is not
  needed for enumeration and must not seed or influence this corpus.

### Carried forward

Implement stdlib Python collectors, response archive and normalized JSONL exports,
fixed run manifest and coverage JSON/Markdown. Test interval boundaries, nulls,
reply ancestry, chronological sorting, deduplication, pagination, retries, and
resume. Run the actual experiment; commit implementation/tests/docs with Git and
keep corpus ignored. Evaluate detector design only after inspecting the corpus.

Primary references verified 2026-09-19:
- https://github.com/HackerNews/API
- https://github.com/discourse/discourse/blob/main/app/controllers/posts_controller.rb
- https://community.make.com/posts.json
- https://community.make.com/robots.txt

Live probes verified public Make post pagination and raw/cooked text fields.

### Addendum — 2026-09-19 — Observed feed omission

The first live Make collection exposed three in-window posts through topic streams
that the global post feed omitted: one marked hidden but publicly returned, and
two system autobump posts. `/latest.json` showed other recently bumped topics
absent from that feed. Add a query-independent, paginated recent-activity listing
pass and fetch those candidate topics as well. Select records by their actual
creation times; preserve native post types and label small-action posts `system`.
This changes enumeration within the existing public-source domain, not the goal
or opportunity-selection criteria. Reports retain activity-list boundaries and
IDs added by the supplementary pass. Avoid claiming inaccessible and hidden are
synonymous: public endpoint behavior is the observable boundary.
