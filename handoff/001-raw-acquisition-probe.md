# AI Gap Resolution — Raw Acquisition Probe

## Context

We are exploring a potential service/category we are currently calling **AI Gap Resolution**.

The underlying opportunity is to find people who have economically meaningful work problems that could potentially be resolved with AI, automation, integrations, or custom software, but who do not have the technical ability to implement the solution themselves.

We are designing an **Opportunity Detector**, but we deliberately do **not** want to design the detector yet.

Before deciding what constitutes an opportunity, what signals matter, or how anything should be scored, we want to collect real data and examine what actually exists.

This task is therefore only about the **very beginning of the pipeline: raw data acquisition**.

---

# Objective

Build a small acquisition probe that can collect a reasonably complete, chronological sample of recent public content from:

1. **Hacker News**
2. **Make Community**

The immediate experiment is:

> Collect approximately the most recent 24 hours of available content from both sources without filtering for AI, automation, business pain, buying intent, or presumed opportunity value.

We want a real corpus that we can inspect before developing theories about candidate detection.

The probe should preserve enough information that later analysis can reconstruct where each item came from and, where applicable, its conversational context.

---

# Important principle

Do **not** optimize collection around phrases such as:

* "AI"
* "automation"
* "pain point"
* "looking for help"
* "takes hours"
* "need a developer"

One of the hypotheses we specifically want to test is whether valuable work-problem disclosures occur in conversations that would never be retrieved by those searches.

For example, during exploratory research we encountered potentially interesting work/process disclosures buried in Hacker News discussions whose subjects had nothing to do with AI or automation.

The acquisition corpus therefore needs to be **query-independent enough to let us discover unexpected signals later**.

---

# Source information already established

## Hacker News

Hacker News provides an official Firebase API.

Relevant known characteristics:

* Items have monotonically increasing IDs.
* The API exposes the current maximum item ID.
* Individual items include stories, comments, jobs, polls, etc.
* Comments contain relationships to their parent and children.
* HN exposes current/new/best stories and recent Ask HN, Show HN, and job stories.
* It also exposes recently changed items.
* HN's published API documentation currently states that there is no API rate limit.

The important research objective is not merely to collect top-level stories.

We are particularly interested in **comments**, because work problems can emerge incidentally inside otherwise unrelated discussions.

Official API documentation:

https://github.com/HackerNews/API

---

## Make Community

Make Community runs on Discourse and exposes public structured data.

During research we verified public structured category data for the `Hire Help` area, including information such as:

* topic IDs
* titles
* excerpts
* users
* timestamps
* reply counts
* tags
* category information
* pagination information

Relevant public community:

https://community.make.com/

Particularly relevant section:

https://community.make.com/c/hire-a-pro/hire-help/74

Discourse also commonly exposes structured topic/post data and RSS feeds. We have verified that Make's community exposes public Discourse-style structured responses.

For this experiment, we do **not** want to collect only `Hire Help`.

That category is useful because it gives us obvious examples of explicit demand, but we also want recent content from broader Make discussions so that later we can compare explicit hiring requests with ordinary implementation questions and other conversations.

---

# Existing exploratory sample

A very small probe corpus was already assembled manually from public web-visible surfaces:

`ai_gap_acquisition_probe_2026-09-19.jsonl`

It contains 10 records from Hacker News and Make.

It is only an exploratory artifact and **must not be treated as a representative corpus**.

Its main purpose was to confirm that useful recent material exists and to expose limitations of the ChatGPT browsing environment.

For example, the sample includes a Make user saying they had only recently started using Make, were stuck, found it incomprehensible, and were now willing to pay for assistance.

That is exactly the kind of material we eventually want to study—but the acquisition probe must not preferentially search for or filter toward examples like it.

---

# What we want collected

For the first proper experiment, collect approximately **24 hours of recent content**.

Prefer the most recent completed/reliably retrievable 24-hour interval.

The resulting corpus should make it possible to answer questions such as:

* How many items did each source produce?
* What proportion are top-level topics/stories versus replies/comments?
* How much text is actually available?
* Can conversations be reconstructed?
* Are timestamps sufficiently reliable?
* Are there gaps in the collection?
* What types of content occur naturally?
* Is the volume manageable enough to analyze with models later?

Do not perform opportunity classification as part of this task.

---

# Preserve provenance

Each collected record should retain enough source information that we can trace it back to its origin.

At minimum, we care about concepts such as:

* source
* source-native identifier
* item type
* author/handle when publicly exposed
* creation timestamp
* title when applicable
* text/body
* canonical public URL or reconstructable source reference
* parent/thread relationship when available
* retrieval timestamp

Preserve useful source-native data rather than prematurely throwing fields away.

We may discover later that metadata we initially considered irrelevant is useful.

If practical, retain the original/raw response associated with collected items or otherwise preserve enough information to revisit parsing decisions.

---

# Conversation structure matters

Do not flatten discussion relationships unnecessarily.

Later analysis may need to know:

* which story/topic a comment belongs to
* what a comment was replying to
* which replies belong to a post
* whether an item is the root of a discussion or deep inside one

We don't yet know how much surrounding context the eventual detector will need, so retaining source relationships now is preferable to trying to reconstruct them later.

---

# Recency

Current date for this experiment:

**September 19, 2026**

We want the corpus to be as recent as possible.

The initial target is roughly the preceding 24 hours rather than a historical archive.

If source behavior makes an exact 24-hour boundary impractical, preserve timestamps and document the actual captured interval rather than silently approximating it.

---

# No semantic filtering

The raw corpus should include boring material.

That is intentional.

Do not exclude items merely because they appear:

* irrelevant to business
* purely technical
* casual
* political
* argumentative
* unrelated to AI
* unrelated to automation
* unlikely to contain a commercial opportunity

We need negative examples as well as positive examples.

Otherwise we cannot later estimate how sparse the useful signal really is.

Source-level exclusions needed for technical or access reasons are different and should simply be documented.

---

# Ethical/access constraint

Use public interfaces and respect the sources' access expectations and published restrictions.

We are not asking for:

* authentication circumvention
* rate-limit bypasses
* anti-bot evasion
* private content
* restricted user data

For this first probe, Hacker News and Make were chosen partly because they expose public interfaces suitable for legitimate collection.

---

# Desired outputs

Produce:

### 1. Raw corpus

A machine-readable collection of the captured HN and Make content.

JSONL would be convenient for later model experimentation, but choose an appropriate representation if there is a strong reason to do otherwise.

### 2. Collection summary

A concise report describing:

* exact time interval captured
* number of records by source
* breakdown by item type
* any known missing or skipped material
* any source/API behavior that affected completeness
* whether thread/parent relationships were successfully preserved
* any unexpected characteristics of the source data

### 3. Reproducible acquisition capability

Leave behind whatever is necessary so the same collection can be run again against a later time window.

The specific implementation is up to you.

### 4. Representative sanity samples

Include a small handful of raw records from each source so we can visually verify that:

* text is present
* timestamps make sense
* provenance is correct
* relationships appear correct
* we have not accidentally collected only titles or metadata

---

# Acceptance criteria

We should consider this experiment successful if:

* we have a recent corpus from **both HN and Make**;
* comments/replies are represented, not only top-level posts;
* collection was not based on AI/opportunity keywords;
* timestamps allow us to understand the capture interval;
* records can be traced back to their public source;
* conversational relationships are retained where the source exposes them;
* obvious collection gaps or ambiguities are documented rather than hidden;
* the result is suitable for us to inspect next and ask, empirically, what kinds of work-problem disclosures actually occur.

---

# Explicit non-goals

Do **not** yet:

* identify leads;
* score opportunities;
* classify business pain;
* determine whether disclosures are organic;
* infer technical ability;
* infer willingness to pay;
* generate outreach;
* cluster opportunity types;
* build a dashboard;
* train a classifier;
* decide what the final Opportunity Detector architecture should be.

Those decisions should be informed by the corpus produced here rather than baked into its collection.

The immediate goal is much simpler:

> **Give us an honest, recent slice of what people are actually saying on these sources so that the next design decisions can be based on evidence instead of imagined examples.**
