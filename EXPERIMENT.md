# First acquisition experiment — 2026-09-19

Collected creation times **2026-09-18 08:00:00 UTC inclusive through
2026-09-19 08:00:00 UTC exclusive**. This was the latest completed UTC-hour cutoff
when work started. Local corpus: `data/2026-09-19/` (intentionally untracked).

## Observed corpus

| Source | Sample records | Types | Records with body text | Body characters | Extra context |
| --- | ---: | --- | ---: | ---: | ---: |
| Hacker News | 12,988 | 11,616 comments; 1,371 stories; 1 job | 11,324 | 3,391,352 | 3,440 |
| Make Community | 151 | 1 topic; 41 replies; 109 system events | 42 | 28,029 | 551 |
| Total | 13,139 | | 11,366 | 3,419,381 | 3,991 |

Body-text counts exclude titles and preserve empty bodies. HN records include 416
marked deleted and 1,018 marked dead; these flags may overlap and are not topical
filters. Deleted records are retained as available metadata, not recovered text.
System events in Make are preserved separately from human discussion posts.

HN scanned all 16,000 IDs from 49,748,574 through 49,764,573, plus 2,683 additional
ancestor requests. Its scan reached the six-hour guard below the window. No null,
failed, or timestampless IDs were observed in that scan; no sampled thread root
remained unresolved. HN creation timestamps showed no inversions in scanned ID
order. Context includes transitive ancestors, not every historical sibling.

Make fetched three post-feed pages and six recent-activity topic-list pages, both
through the guarded boundary. It examined 126 candidate topics; 124 contributed
sampled posts. The sample spans five category IDs (48, 65, 66, 74, 75); selection
was not restricted to Hire Help. No stream gaps, failed URLs, or topic caps were
observed. There was one observed creation-time inversion in the post feed.

**Acquisition finding:** the global Make post feed alone exposed only 41 of the
151 final sample records. Public topic endpoints supplied another 110: 109 system
events and one post marked hidden but returned publicly. The recent-activity
listing was necessary to find many of their topics. This is evidence about source
coverage, not an opportunity judgment. The large system-event count must not be
mistaken for a count of people asking for help.

## Artifacts and validation

- `sample.jsonl`: 20,527,273 bytes, chronological and deduplicated.
- `context.jsonl`: 10,052,137 bytes, separate from sample counts.
- 18,828 compressed HTTP-response archives: 18,684 HN and 144 Make. All final
  archived responses have HTTP 200; 12 URLs needed multiple attempts. Original
  attempt bodies and headers are retained, including transient failures.
- `report.json` and `report.md`: detailed counts, hourly distribution, categories,
  ID range, traversal boundaries, missing-content indicators, and artifact hashes.
- `verification.json`: offline integrity result and identical-replay result.
- `manifest.json`: fixed interval, retrieval-run timestamps, invocation parameters,
  and collector source checksum. Successful responses were reused during refinement.

Twelve automated tests pass. Offline verification checks time-window membership,
uniqueness, ordering, per-source counts, artifact hashes, source-native payload
equality with archived responses, retrieval timestamps, referenced parents, and
an archive for every scanned HN ID. No integrity errors or missing referenced
parents were found. Offline replay with networking disabled reproduces identical
sample and context checksums.

Sample SHA-256:
`f9b02d102512da25ee62cc4d0ce93049389cfa4aa000a2ca306e62e61c2bc128`

Context SHA-256:
`0c9ad2b7fa85ef1e6271a494835df6e0ef49af947a79358bd7ac6fde28925f7c`

## Interpretation boundary

The run traversed the selected public interfaces without unresolved request
failures. This does not prove absolute historical completeness: moderation, source
visibility, omitted/unbumped activity, and arbitrarily backdated/imported content
can escape these interfaces or guarded stopping rules. Retrieval-time text may
reflect edits after creation. No private data access or external article fetching
was attempted. The corpus is one day of observations, not evidence that this day
represents typical source volume or opportunity prevalence.

No keyword retrieval, AI/pain/buying-intent filters, opportunity classification,
scoring, or detector design was performed. Raw content remains local and out of Git.
