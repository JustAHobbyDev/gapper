# Workflow opportunity detection: design research

Date: 2026-09-20. Status: proposed research direction; no detector implementation,
semantic corpus evaluation, model training, or source changes performed.

**Recommendation:** treat Failed Adoption / Unrealized AI Value as a first-class
entry path into workflow discovery. Screen broadly for evidence, reconstruct an
actor's workflow using conversation context, and retain an attributed evidence
cluster. Only then classify the missing capability and formulate a provisional
implementation hypothesis. Rank research candidates separately from their
commercial attractiveness, which the current corpus cannot establish.

The four proposed dimensions—workflow specificity, pain, gap clarity, and
feasibility—are useful review dimensions, but research does not establish them as
a sufficient or validated scoring model. Add evidence grounding, coverage,
contradictions, and resolution status. Avoid fixed weights until annotated tests
show which dimensions are reliable and useful.

## 1. Scope, findings, and strength of evidence

This is a targeted literature and first-party industry review, not a systematic
meta-analysis. Searches covered customer needs, complaints, suggestions, feature
requests, purchase intent, jobs-to-be-done, process extraction, dialogue and
document relation extraction, conversation disentanglement, semantic clustering,
and model cascades. Sources below distinguish established task results, industry
practice, and Gapper-specific proposals. No reviewed study directly validates
profitable AI implementation opportunity detection in HN/Make discussions.

The proposed frame is evidence reconstruction → hypothesis synthesis → researcher
review. Public text supports statements about **what participants reported**;
it does not establish the actual state of their workplace or future purchasing
behavior. See [Problem Frames, Entry #2](PROBLEM_FRAMES.md).

### Transferable prior work

| Research or practice | Finding or method | Transfer to Gapper; boundary |
| --- | --- | --- |
| Timoshenko & Hauser, 2019, [Identifying Customer Needs from User-Generated Content](https://pubsonline.informs.org/doi/abs/10.1287/mksc.2018.1123) | Filter noninformative sentences, cluster embeddings to reduce repetitive material, and use professional analysis to identify needs. Evaluated against needs from conventional research in oral care. | Strong precedent for screening, diversity, and measuring distinct useful needs per review cost. Product reviews and a known product category differ from open professional conversations. |
| Timoshenko, Mao & Hauser, [Transforming the Voice of the Customer](https://arxiv.org/abs/2503.01870v2), 2026 revision, preprint | Evaluates LLM abstraction of customer needs with professionals. Reports benefits from supervised fine-tuning and evaluates specificity and grounding. | Separate extraction/abstraction quality from fluent summarization. The full text discusses false negatives versus hallucination when selecting training negatives. It does not establish that current off-the-shelf models need fine-tuning for Gapper. |
| Negi et al., 2019, [SemEval Task 9: Suggestion Mining](https://aclanthology.org/S19-2151/) | Sentence classification with both within-domain and cross-domain forum/review evaluations. | Suggestions and requests are useful speech acts. Their presence does not establish a workflow or unmet need; their absence does not exclude latent demand. Test transfer from HN to Make explicitly. |
| Preoţiuc-Pietro et al., 2019, [Automatically Identifying Complaints](https://aclanthology.org/P19-1495/) | Models complaints as a mismatch between expectations and experience, using annotated social posts across domains. | Extract attempted task, expected result, actual failure, and consequence. Negative sentiment alone is an inadequate target label. |
| Maalej et al., 2015, [How can I improve my app?](https://ieeexplore.ieee.org/document/7332474/) | Classifies app feedback for maintenance/evolution, including usage, bugs, and requests, combining language and sentiment analysis. | Use separate evidence roles rather than one positivity score. A bug in an existing product may indicate support work, not a new implementation business. |
| [Building Task-Oriented Dialogue Systems for Online Shopping](https://cdn.aaai.org/ojs/11182/11182-13-14710-1-2-20201228.pdf), AAAI 2017 | Separates intent, product category, attributes, and session-dependent intent. | Useful distinction between recommending, comparing, and buying. Its broad purchase-related intent labels should not be translated into willingness to pay for custom software. |
| Bellan et al., 2022, [PET process extraction dataset](https://arxiv.org/abs/2203.04860) | Annotates process activities, actors, gateways, and flow relationships in process descriptions. | Extract actor–action–artifact relations and explicit ordering. Forum fragments are less complete than authored process descriptions; do not force a full BPMN model. |
| Yu et al., 2020, [DialogRE](https://aclanthology.org/2020.acl-main.444/) | Dialogue relation extraction benefits from speaker information; facts span utterances. Dataset includes supporting triggers. | Preserve speakers and evidence across turns. Scripted dialogue relations are not evidence that a particular HN context radius is optimal. |
| Yao et al., 2019, [DocRED](https://aclanthology.org/P19-1074/) | Document-level entity/relation extraction requires combining information across sentences. | Claim-level source links and coreference are more useful than independent sentence scores. Wikipedia document structure differs from branching discussion. |
| Kummerfeld et al., 2019, [Conversation Disentanglement](https://aclanthology.org/P19-1374/) | Annotated reply graphs expose problems with missing and extraneous messages in reconstructed conversations. | Relevant context selection is itself an evaluation target. Native links help, but one reply tree can still contain several workflow discussions. |
| Reimers & Gurevych, 2019, [Sentence-BERT](https://aclanthology.org/D19-1410/) | Produces embeddings suitable for efficient semantic similarity and clustering. | Retrieve possible duplicates using canonical need descriptions, then verify equivalence. Similarity is not proof of the same workflow or independent demand. |
| Liu et al., 2024, [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) | On tested retrieval and question-answering tasks, relevant-information position affects use of long context. | Benchmark whole-thread input and ordering; a large context window does not guarantee accurate synthesis. Results are model/task-specific, not a universal 2026 performance claim. |
| Chen et al., 2023, [FrugalGPT](https://arxiv.org/abs/2305.05176) | Explores model cascades under cost/quality tradeoffs. | Supports testing conditional expensive analysis. Its savings are not a forecast for this pipeline, whose screening errors and extraction tasks differ. |
| [Productboard auto-linking](https://support.productboard.com/hc/en-us/articles/26949590820627-Link-insights-automatically-with-Productboard-AI), first-party documentation | Links feedback to feature ideas while distinguishing manual, unverified AI, and verified AI links. | Transfer evidence lineage and review status. An existing customer's feedback and feature hierarchy are unavailable assumptions for Gapper. Product behavior is not an accuracy benchmark. |
| [Strategyn JTBD canvas](https://strategyn.com/wp-content/uploads/2024/06/JTBD-Canvas.pdf), first-party method | Separates a functional job from an outcome and its measure. | Normalize the desired work outcome without prescribing AI. Do not invent outcome metrics or customer importance when absent. This is a formulation method, not an extraction benchmark. |

These findings favor evidence-backed need discovery over sentiment analysis or
lead scoring. Process extraction supplies a useful partial vocabulary; dialogue
extraction supplies attribution and context; customer-needs work supplies
screening and abstraction. None establishes a complete Gapper ontology.

### What the existing corpus supports

The [acquisition report](EXPERIMENT.md) and [HN structural analysis](HN_CONVERSATIONS.md)
cover 2026-09-18 08:00 UTC through 2026-09-19 08:00 UTC. Read-only schema/count
inspection for this document confirmed source and item-type counts.

| Property | Observed value | Implication |
| --- | --- | --- |
| HN in-window records | 12,988, including 11,616 comments | Screening cost must include roots as well as comments. Root-only opportunities are possible. |
| HN context | 3,440 records | Already available for offline expansion. |
| HN comments needing pre-window ancestry | 4,210 / 11,616 = 36.24% | A sample-only experiment systematically removes relevant context opportunities. |
| HN ancestry | 100% structural paths; 99.13% textual ancestry; 96.25% also have their own text | Missing text must be measured separately from missing links. |
| HN depth | Median 3, p95 8, maximum 20 | Immediate-parent input is an important baseline, not a sufficient default assumption. |
| Make in-window records | 151: 42 human posts and 109 system events | Bumps are not new statements of demand. |
| Make context | 551 records | Potentially rich prior discussion, with original dates retained. |
| Make roots with in-window human posts | 17, computed from sample `topic`/`reply` records | Review all 17 topics for an initial study; 124 participating topics is not 124 fresh human discussions. |

The stored fields already include source, native ID, parent/thread IDs, author,
timestamps, scope, text, raw/native content, and response reference. Make native
post numbers and explicit reply targets must remain available when building its
graph. A null reply target means topic-level reply, not previous-message reply.

HN ancestry is complete **within the retained paths**, not a complete thread
archive. Historical siblings and other descendants may be absent; external
articles and attachments were not fetched. A whole-retained-thread comparator is
possible now; a whole-source-thread completeness claim is not. Make stream
coverage was reported without gaps for this run, but still represents the public
retrieval snapshot, not all historical versions or inaccessible posts.

## 2. Recommended unit of analysis

Use three different units for three different jobs:

- **Screening:** a comment or root, optionally with its immediate parent and root
  metadata. Output evidence roles and uncertainty, not a final opportunity score.
- **Reconstruction:** a bounded conversation region with explicit reply and
  speaker information, expanded as needed.
- **Persistent candidate:** an **evidence cluster for one actor/workflow episode**,
  linked to a separate cross-discussion workflow family when appropriate.

An evidence cluster is a selected set of claims and their source spans, not a
thread summary. It may cross branches when a participant clarifies the same
workflow elsewhere. It may contain one sufficient post. Conversely, a single
thread may yield several candidates, or none.

| Input unit | Context and inference | Cost/scalability | Main error and duplication risk | Proposed role |
| --- | --- | --- | --- | --- |
| Comment | Misses antecedents and later explanations | Lowest input cost | Incomplete needs; technical advice mistaken for demand; multiple hits per opportunity | Baseline and candidate seed |
| Comment + parent | Resolves many local questions | Low; shared parents can repeat | Misses root situation and later evidence | Cheap default candidate context to test |
| Reply chain + root | Preserves a clarification sequence and actor references | Moderate; chains overlap | Misses sibling corroboration or correction; repeated prefixes | First expansion |
| Branch/subtree | Includes responses, alternatives, and resolution | Variable; popular branches grow large | Topic drift; mixed workplaces; overlapping subtrees | Expand when local evidence is insufficient |
| Root + selected descendants | Retains framing and chosen evidence | Budgetable | Selection can omit crucial negation or antecedents | Region assembly with paths preserved |
| Whole retained thread | Broadest available counterevidence | High variance; process once per root | Distractors, conflated actors, long-context failures | Baseline and small-thread fallback |
| Extracted evidence cluster | Focused synthesis with traceable claims | Compact downstream, but selection/extraction cost comes first | Selection bias, incorrect coreference, hidden contradictory evidence | Recommended stored unit, empirically provisional |

Start with seed → ancestors/root → available replies addressing that workflow.
Include connector comments needed to interpret pronouns, replies, or negation.
Seek corrections and resolution, not only supportive statements. Search neighboring
branches within the same root for the same actor/task/artifact when evidence is
incomplete. Stop at a recorded token budget, semantic boundary, or no new relevant
claims; mark truncation and unresolved references. Merge overlapping regions before
expensive analysis where they address the same workflow.

A useful reply from another person is a `proposes` claim. It becomes an observed
attempt or success only if someone reports trying it. Do not join one user's time
estimate with another user's tool configuration merely because both mention PDFs.
Keep multiple users' episodes separate and link their shared need at family level.

This recommendation is an inference from the reviewed work and the local graph
structure, not a demonstrated improvement in Gapper accuracy.

## 3. Proposed opportunity evidence schema

Use three small logical records: **evidence claim**, **candidate episode**, and
**workflow family**. These can initially be JSON records and ID indexes; no graph
database, full process ontology, or agent framework is justified yet.

### Evidence claim: provenance first

Every populated observed field points to one or more claims with:

| Field | Definition |
| --- | --- |
| `claim_id`, `kind`, `value` | Stable local identifier, evidence role, minimally normalized content. |
| `source_ref` | Source + native ID, thread/parent IDs, canonical URL, response reference, creation/retrieval times, sample/context scope. |
| `span` | Start/end offsets into versioned normalized text, with text hash and normalizer version. Local excerpts can aid review; never commit acquired text. |
| `speaker_ref`, `subject_ref` | Who made the statement versus whose workflow it describes; unknown if unresolved. Use corpus-local identifiers. |
| `basis` | Firsthand report, secondhand report, suggestion, question, hypothetical, or analyst inference. |
| `polarity`, `relations` | Supports, contradicts, corrects, answers, or supersedes another claim; retain both sides. |
| `review_status` | Unreviewed, accepted, corrected, or rejected; separate from machine confidence. |

“Observed” means the statement appears in the source. It does not certify the
statement as true. A model-generated summary is always derived, even when it
faithfully compresses observed claims.

### Candidate episode

| Group / fields | Meaning and minimum useful shape | Evidence status |
| --- | --- | --- |
| Identity: `candidate_id`, `anchor_ids`, `region_ids`, `evidence_ids` | One actor/workflow episode; one or more in-window human anchors for new discovery. List included context separately. | Deterministic lineage plus proposed grouping |
| `actor`, `domain` | Reported role/organization context, without invented identity or firm size. Domain label may be inferred and marked accordingly. | Observed or explicit inference |
| `workflow`, `desired_outcome` | Short task and intended result, without choosing a vendor or architecture. | Derived from linked claims |
| `steps` | Optional partial list of `{action, actor, inputs, outputs, system, follows, evidence_ids}`. `follows` only when supported; unordered tasks remain unordered. | Observed relationships, normalized |
| `pain` | Failure, delay, checking, rework, error, or unmet result. | Reported |
| `burden` | Optional quantities with value/range, unit, period, whose burden, and qualifier: time, frequency, volume, cost. | Reported; estimates marked |
| `current_workaround` | What is used now, including manual work and partial automation; retain whether it works. | Reported |
| `adoption` | `attempted`: yes/no/unknown; named tool if given; expected result, failure mode, reported consequence. | Reported; tool use by another speaker stays separate |
| `constraints` | Verification, confidentiality, approval, deployment, formats, access, and deterministic requirements. | Reported, not inferred from profession alone |
| `suggested_solutions` | What commenters propose, with speaker and support; distinguishes suggestion from demonstrated implementation. | Observed proposal, not verified feasibility |
| `feasibility_evidence`, `buying_signal` | Reports of working portions/interfaces; explicit recommendation request, vendor evaluation, hiring, budget, or willingness to pay. Preserve exact intent category. | Reported, with confirmation status |
| `resolution` | Unresolved, reportedly solved, partially solved, disputed, or unknown, with dated evidence. | Derived status grounded in claims |
| `coverage` | Missing text/nodes, unavailable attachments, selected versus retained nodes, context scope, token truncation, retrieval snapshot, unresolved actor links. | Measured or explicitly unknown |
| `assessment` | Need status, failed-adoption subtype(s), gap hypotheses, alternatives, supporting/contradicting claims, unanswered questions. | Inferred, versioned |
| `generation` | Corpus hashes, schema/prompt/model versions, run ID, token usage, review version. | Run metadata |

Put technical architecture in an optional `implementation_hypotheses` list under
`assessment`. Each hypothesis needs supporting claims, assumptions, possible
non-AI remedy, disconfirming evidence, and a next validation step. It is not a
required field for detecting a real need.

Do not require every field to be populated. Core candidate sufficiency is an
identifiable task/outcome, grounded friction, and enough actor/artifact context
to know which work is affected. A concrete **implementation** candidate also
needs an evidenced reason to suspect a capability beyond generic instruction;
otherwise keep it as an unmet need or unresolved classification. Repetition,
failed workaround, and buying intent strengthen evidence but are not mandatory.

Use `unknown`, `not_stated`, `not_applicable`, and `contradicted` deliberately;
zero frequency and no attempted workaround are substantive claims, not defaults.
Avoid a single uncalibrated `confidence: 0.93`. Track claim support, context
adequacy, classification certainty, and technical feasibility separately. Numeric
confidence requires held-out calibration against human labels.

The original long field list is mostly useful, but several items need grouping:
inputs/outputs/tools belong to steps or workflow-level artifacts when their step
is unknown; frequency/volume/economic signal belong to burden; missing capability
and suggested solution must not be collapsed. Defer exhaustive domain taxonomies,
BPMN gateways, revenue forecasts, inferred API availability, and scalar market scores.

### Workflow family

Store `family_id`, a versioned canonical need, member episode IDs, shared and
variant constraints, merge rationale, disputed matches, and report counts.
Never replace member episodes with a synthetic “average customer.”

## 4. Proposed detection pipeline and cost model

These are logical stages, not a requirement for five separate LLM calls.
Reconstruction and gap classification can share one call initially if their
outputs and evidence references remain distinct.

| Stage | Work and output | Parent/root use and failure handling |
| --- | --- | --- |
| 0. Prepare snapshot | Index retained records, native relationships, text versions, source/scope, and coverage. Exclude system events from semantic demand counts; retain them in acquisition. | Reuse HN paths; preserve Make's explicit reply semantics. Bodyless nodes remain graph metadata. |
| 1. Screen for evidence | Cheap multi-label classifier for task, friction, workaround, AI failure, clarification, suggestion, verification, or request. Include roots and non-AI workflow reports. | Compare comment-only with parent-aware screening. Uncertain and context-dependent items can pass; never require a complaint keyword. |
| 2. Assemble context | Expand to ancestors/root and relevant available replies; deduplicate overlapping regions; preserve negations and resolution. | Root title is context, not proof that every reply has its topic. Mark incomplete/truncated regions. |
| 3. Extract claims/workflow | Resolve actors, identify supported steps/artifacts and burden, attach spans, and allow multiple episodes or no candidate. | Preserve source IDs and conversational order. Abstain on unresolved references. |
| 4. Classify and hypothesize | Determine need status and adoption gap; optionally generate bounded capability hypotheses. | A technical reply is evidence of a proposal. Missing access or unstated success remains unknown. |
| 5. Validate and consolidate | Check schema, span existence, number units, attribution, contradictions, duplicates, and resolution. Retrieve candidate family matches. | Span existence alone does not prove entailment; reviewer audit must test meaning. |
| 6. Present/rank for review | Evidence-backed research queue and separate commercial unknowns; record human corrections. | Link back to all supporting and contradicting records; new evidence can downgrade a candidate. |

Content remains untrusted input throughout; source text does not issue tool
instructions. Model extraction should have no permission to execute suggested
code or follow arbitrary links. Raw archives stay unchanged. Cache derived
results by source text/context hash and model/prompt/schema version; changes to
context invalidate dependent extraction. Failed stages are pending/errors, not
negative labels. Paid/model-backed corpus experiments have not been run here.

### Why stage it, and when not to

Staging offers cheaper rejection of obvious non-evidence, reusable claims,
diagnosable failures, and independent comparison of ranking strategies. However,
a classifier can discard exactly the vague opening that a later reply explains.
Expansion can miss evidence, and repeated prompts plus intermediate output can
cost more than processing small threads once. Include random screening negatives
in audit, pass evidence-bearing replies even when OP is generic, and compare
small retained threads processed in one call. Do not treat a cascade as proven.

A measurable planning formula is:

```text
C_stage = (p_s_in * T_s_in + p_s_out * T_s_out
         + p_e_in * T_e_in + p_e_out * T_e_out) / 1,000,000
         + embedding/reranking cost + retries + review cost

T_e_in ≈ U * (mean_region_tokens + extraction_prompt_tokens)
U = distinct expanded regions after merging, not positive comments
```

Prices are variables, not current provider quotes. Count actual billed input,
output, cached input, and any separately billed reasoning before comparing models.
Measure end-to-end recall as well as cost; cheap rejection with low recall is not
an improvement.

HN in-window bodies contain 3,391,352 characters: at an **illustrative** four
characters/token, about 0.848 million body tokens. A read-only sum of retained HN
`text` plus `title` produced 4,756,447 characters, about 1.189 million at that same
rough ratio. This excludes prompt/metadata overhead and is not a tokenizer result.
Serializing `source_native` duplicates text and should not be the model input.

For a deliberately hypothetical comment-only budget: 11,616 screening inputs
averaging 150 input and 20 output tokens imply 1.7424M input and 0.23232M output
tokens. If merging yields 400 regions averaging 2,000 input and 400 output tokens,
extraction adds 0.8M input and 0.16M output tokens. Neither acceptance rate nor
region length is measured. This illustrates why a cheap screen is not necessarily
cheap in total tokens, and why actual model prices and whole-thread baselines
matter. Sweep acceptance rates and region sizes rather than promising savings.

## 5. Signal taxonomy, reply structure, and sentiment

| Signal class | Evidence-bearing forms | Qualification |
| --- | --- | --- |
| Workflow specificity | Named actions, artifact transformations, outputs, systems, actors, explicit sequence | A tool name or file format alone is weak; do not reward verbosity. |
| Recurrent friction | Manual transfer, repeated checking, delays, rework, quantified frequency/volume | Retain units and attribution. A generic “wastes time” is weaker than a described burden. |
| Missing implementation | Failed handoff, inaccessible records, unreliable structured output, absent validation, approval or provenance | Identify the affected task and why generic interaction fails. |
| Workaround/partial implementation | Scripts, spreadsheets, macros, Make flows, assistants, manual exception handling | Strong evidence of work being done; also possible evidence the problem is already solved. |
| Verification/constraints | Ledger matching, citations, review gates, internal-only processing, required format | May motivate implementation or make it infeasible. Both directions matter. |
| Corroboration/commercial intent | Specific independent firsthand episodes; requests to hire, pay, or evaluate vendors | Generic agreement is not an independent episode; recommendation requests do not establish budget. |
| Negative | Model debates, philosophy, speculative replacement claims, generic tips, unsupported complaints | Low candidate confidence without workflow evidence; retain as contextual nodes if needed. |
| Ambiguous | Long replies, deep branches, many upvotes, “RAG,” “agent,” recommendation links, profession names | Useful retrieval hints at most. Could be promotion, argument, basic support, or imagined use cases. |
| Counterevidence | Confirmed sufficient solution, abandoned workflow, contradictory volume, unavailable required data | Can lower or close a candidate while preserving historical failed adoption. |

### Conversation patterns

Test, rather than assume, whether these patterns improve selection:

- Workflow owner answers clarifying questions: may add artifacts and constraints.
- A respondent asks about inputs, access, volume, or approval: may identify missing
  evidence; the question is not itself an answer.
- A respondent proposes an architecture and the owner requests implementation
  detail: stronger engagement, still not a purchase or successful deployment.
- Several users provide their own matching workflows: corroboration with separate
  episodes; count generic agreement separately.
- Tool disagreement: may expose a constraint, or simply reflect preferences.
- Partial solution followed by residual manual work: candidate boundary can be the
  unresolved portion. A confirmed final fix can eliminate that residual.

Use structure first for retrieval and attribution. Depth, length, and reply count
are opportunity-ranking features only if they add held-out value after controlling
for discussion size, source, and textual specificity. HN popularity must not become
an economic signal by accident. A “workflow owner” may be a commenter rather than
OP; track both identities.

### Negative AI sentiment

Represent failed adoption as a supported relationship:

`actor attempted tool on task → expected result → reported failure → residual work`

Not every element must be explicit to create a candidate, but absent elements
remain unknown. “AI is garbage” has no task or failure mechanism and cannot by
itself establish failed adoption. A contract-review complaint naming unreliable
clause references and repeated manual review has implementation-relevant content.
The latter is a **synthetic example from the brief**, not a measured corpus case.

The same classifier should recognize an emotionally neutral report of that
failure, and a positive AI user whose workflow still contains manual handoffs.
Do not require the literal word AI: tool identity can be reported elsewhere in
the cluster. Conversely, access without an attempted task is unrealized value,
not necessarily failed adoption. Keep `attempted = unknown/no` distinct from yes.

## 6. Failed-adoption classification and limits on solution inference

Treat these as potentially overlapping gap labels, not a forced mutually exclusive
ladder. Record the least elaborate **supported** remedy and unresolved alternatives.
A workflow may need both education and integration. Configuration work may have
commercial value even when it does not justify custom software.

| Class | Operational criterion | Evidence needed to distinguish it | Counterexample / unknown |
| --- | --- | --- | --- |
| Education | User does not know available uses or basic operation; no task-specific capability deficit shown | Specific knowledge question or confirmed remedy through instruction | “I see no value” alone is insufficient to diagnose user ignorance. |
| Prompting | A defined task is plausibly addressed by input/task instructions within an existing interaction | Reported prompt issue and preferably a successful revision on representative work | “Prompt better” from a stranger does not prove the failure is prompting. |
| Configuration | Existing product appears able to do the job after settings, mapping, templates, retrieval source setup, or permissions configuration | Named setting/capability and evidence it meets constraints; later verify current documentation | A connector's existence does not show the user's plan supports it or access is available. |
| Integration | Work requires permitted data/action flow between systems beyond current manual interaction | Named source/destination, transferred artifact, manual boundary or failed access | Clipboard inconvenience in a one-off task is not sufficient economic evidence. |
| Workflow automation | The deficit spans triggers, ordered steps, branching, retries, review, exceptions, or monitoring | Described sequence and residual coordination work | May be achievable with existing automation tools and deterministic code. |
| Custom software opportunity | An evidenced combination of capability, interaction, control, or deployment needs appears unmet by current setup | Concrete residual requirements and reasons simpler remedies appear insufficient | Absence of a mentioned product is not proof no suitable product exists. Label provisional until researched. |
| Unsuitable AI use case | Stated requirements conflict with the proposed AI role, or deterministic/nontechnical work better fits the task | A specific mismatch such as demanding unchecked error-free probabilistic decisions, inaccessible required evidence, or no useful AI subtask | A failed chatbot attempt does not prove all automation is impossible. Narrowing AI's role may work. |
| Insufficient evidence | Missing task, constraint, attribution, or cause prevents a supported decision | Explicit unanswered questions and context gaps | Prefer this to forcing a commercially attractive classification. |

Separate `need_status` (none/possible/concrete), `adoption_status`, `gap_labels`,
and `resolution`. A confirmed easy fix can close an episode as education or
configuration; do not keep scoring it as unresolved custom development.

### How far to infer a technical solution

Use three levels:

1. **Observed need:** user-reported task, friction, constraints, and workaround.
2. **Capability hypothesis:** likely missing retrieval, extraction, validation,
   integration, deterministic computation, approval, permissions, provenance, or UI.
3. **Conditional architecture:** optional sequence tied to explicit assumptions
   and a test plan. No claim of buildability or product absence without validation.

Default output should reach level 2 only when justified. Level 3 is useful for
reviewing stronger candidates, but should never be required to make a need visible.
Technical-sounding detail must not increase confidence by itself.

For a synthetic case with emailed invoices, ledger checks, and manual entry, a
possible hypothesis is extraction → deterministic checks → exception review →
accounting-system write. OCR is conditional on scanned documents; retrieval is
conditional on needing reference material; an API write depends on supported
access and permissions. The alternative may simply be a vendor import feature.
Do not automatically attach OCR + RAG + agents to every document workflow.

A citation layer makes sources inspectable, but does not by itself prove the
interpretation is correct. A professional review gate can make a proposed role
more appropriate while also eliminating any hoped-for labor saving. Feasibility
assessment must include the residual verification burden, not only whether a
model can produce an output.

## 7. Duplicate handling and independent corroboration

Separate three operations:

1. **Record deduplication:** source/native ID and snapshot identity. Never count
   sample/context copies, quoted passages, or repeated extractions twice.
2. **Episode consolidation:** merge overlapping clusters referring to the same
   actor and workflow episode, retaining corrections, resolution, and extraction
   lineage. One person can describe different workflows in the same thread.
3. **Workflow-family matching:** group similar needs across distinct episodes
   while preserving each episode and its constraints.

Canonicalize **work**, not the proposed technology:

`actor role | intended outcome | input → actions → output | system boundary | constraints`

For example, invoice extraction and posting may form a family, with separate
variants for invoice/PO matching, ledger reconciliation, required approval, and
on-premises deployment. Different brands can express the same need; identical
brands can serve different jobs. Do not merge solely on “PDF,” “RAG,” or sentiment.

A practical experiment starts with normalized action/artifact terms and lexical
retrieval, then compares embedding retrieval of canonical need descriptions.
For shortlisted pairs, a reviewer or constrained model checks actor/task/outcome,
transformations, constraints, and unresolved status. Use explicit labels: same
episode, same workflow variant, related family, distinct, or uncertain. Avoid
unrestricted transitive merging: A resembles B and B resembles C does not prove
A and C belong to one implementation opportunity. Store merge/split decisions
and recheck cluster coherence after additions.

Track counts separately: source records, firsthand episodes, distinct source
accounts, distinct threads, and explicitly evidenced organizations. Different
accounts are not verified different people; different sites are not automatically
independent. Cross-posts, quotations, referrals to the same story, and promotions
are possible dependencies. Unknown independence stays unknown.

Independent matching reports can strengthen confidence that a need recurs. They
do not automatically improve extraction accuracy, feasibility, willingness to
pay, or unsolved status. Preserve successful counterexamples and segment the
family if one configuration is solved while another remains blocked. Limit any
future corroboration boost so a popular thread cannot dominate through repetitions.

## 8. Ranking without premature weights

Use a two-part research view initially: **evidence quality** and **candidate
attractiveness/unknowns**. Do not collapse them into a single numeric score.
Within a fixed review budget, compare human pairwise preferences and precision
among the first K candidates. Maintain a separate uncertain-but-potentially-useful
queue so sparse evidence does not disappear permanently.

| Factor | Supportable from current text? | Treatment before validation |
| --- | --- | --- |
| Workflow specificity | Yes, via supported actor/action/artifact relations | Ordinal rubric: absent, partial, reconstructable; do not count words. |
| Frequency, volume, time, errors | Sometimes explicitly reported | Preserve units and qualifiers; missing is unknown. |
| Economic pain / organizational importance | Sometimes claimed, rarely verified | Separate operational burden from inferred monetary benefit. |
| Gap clarity | Partly, through linked failure and boundary evidence | Distinguish stated missing capability from analyst hypothesis. |
| Feasibility | Partial implementations and reported access help | Report what worked and what remains unknown; architecture suggestions are weaker. |
| Existing workaround | Usually extractable if mentioned | Indicates investment but may already be sufficient. |
| Buying/hiring intent | Explicit statements can be extracted | Distinguish tool recommendation, evaluation, hiring, budget, and willingness to pay. |
| Independent corroboration | Partially measurable | Count episodes with independence caveats, not upvotes or generic agreement. |
| Professional context | Reported role/task can support it | No automatic premium for prestigious or regulated industries. |
| APIs, permissions, deployment access | Sometimes claimed | Verify later against actual system/version and authorized access; no inference from brand alone. |
| Competition / existing products | A thread can name alternatives | Coverage is incomplete; product absence needs dated external research. |
| Complexity, project size, solo-developer fit | Mostly inferred | Later reviewer assessment against explicit skills, time, integrations, and maintenance constraints. |
| Realizable ROI, budget, sales access | Generally not established | Customer/technical validation required; do not fabricate dollar scores. |
| Grounding, coverage, contradictions, resolution | Directly assessable | Display alongside every dimension; reportedly solved cases leave the unresolved queue. |

The initial four dimensions mix observed burden with inferred feasibility, and
can double-count the same evidence. A manual transfer might raise specificity,
pain, gap clarity, and workaround simultaneously. Test dimensions individually
and jointly for redundancy and reviewer agreement before setting weights.
Importance/satisfaction frameworks cannot be filled with guessed values from a
forum post. Commercial ranking is a later task with additional evidence domains.

## 9. Experiments against the existing HN/Make snapshot

**These are proposed experiments, not completed results.** First make the labels
and provenance requirements stable; then measure models. Keep derived datasets
and excerpts under ignored `data/2026-09-19/research/`. Tracked documents may
contain methodology and aggregate statistics, not acquired text.

### A. Create an annotation pilot and defensible evaluation set

Start with all 17 Make topics containing in-window human posts, plus a documented
random sample of 120 HN roots with in-window human content, stratified by retained
size and whether sampled comments need pre-window ancestry. Include root-only
submissions, ordinary negatives, missing-text cases, and deep chains. Select
within strata by fixed seed/ID hash; record inclusion probabilities. Pilot size
is a workload proposal, not a power calculation.

A separate challenge set can target failed-adoption phrases, technical replies,
partial solutions, and examples requiring several speakers. Mark it enriched;
never use its positive fraction to estimate source prevalence. Do not let the
brief's examples seed the random set. No semantic filter changes acquisition.

Two human annotators independently inspect retained context, identify every
supported workflow episode, label its status, and mark supporting/contradicting
spans and minimum sufficient context. Adjudicate disagreements, including whether
apparently different opportunities are the same episode. If only one reviewer is
available, label the result single-reviewer exploratory evidence rather than a
reliable gold standard. An LLM can assist review but is not independent ground truth.

Record agreement for classification, evidence selection, and episode grouping;
use a disagreement/confusion table and an appropriate chance-corrected statistic
for categorical labels. Incomplete context may make the correct label unknown.
Review unlabeled candidates manually: missing annotations can create false-negative
evaluation errors, as documented in [Revisiting DocRED](https://aclanthology.org/2022.emnlp-main.580/).

Split by root, then keep duplicate workflow families together where discovered.
No comment from a held-out root belongs in prompt examples or training. Use Make
as a separately reported source-transfer test if calibration used HN. This single
day is too small to establish temporal robustness; future days are a separate test.

### B. Controlled context ablation: the architecture-deciding test

Hold model, extraction schema, rubric, and decoding settings fixed. For the same
annotated anchors, compare:

| Arm | Input |
| --- | --- |
| B0 | Anchor comment/root only |
| B1 | Anchor + immediate parent |
| B2 | Anchor + root + complete retained ancestor chain |
| B3 | B2 + retained local replies/branch |
| B4 | Root + selected descendants with connecting paths, forming automatic evidence clusters |
| B5 | Whole retained thread, once per root |
| B6 | Human-selected minimum sufficient evidence, diagnostic upper-bound input |

First run reconstruction without screening so gate misses cannot explain context
results. Normalize predictions to episode IDs for comparison; multiple anchors
finding one need count once. B5 may discover episodes outside a seed's branch;
evaluate both seed-linked reconstruction and root-level opportunity discovery.
Report equal-budget comparisons as well as unrestricted context comparisons.
If a retained thread exceeds the model limit, label truncation and separately
report a chunked variant; do not silently compare it as whole-thread input.

Primary outcomes: episode-level precision/recall, supported-claim precision,
critical-field completeness, actor-conflation rate, and unique useful episodes per
review hour. Also measure evidence-span selection, unsupported solution claims,
duplicate output rate, input/output tokens, latency, dollar cost under recorded
prices, and reviewer correction time. Report context coverage for every arm.
Use root-level paired bootstrap intervals to avoid treating dependent comments
as independent trials. Report source/size/history strata and absolute counts.

A decision rule to agree before running: choose the cheapest input policy whose
held-out quality meets the reviewer's acceptable precision and unsupported-claim
limits. Prefer expansion only if it rescues meaningful cross-comment cases without
unacceptable conflation or review cost. If the pilot contains too few positives,
report inconclusive intervals and expand annotation; do not declare a winning unit.

### C. Test screening and the full cascade

Compare lexical/speech-act heuristics, a small semantic classifier, and no gate.
Evaluate comment-only and parent-aware versions. Measure recall of evidence-bearing
nodes **and** whether each positive episode has at least one retained seed.
Audit a random sample of rejected regions, weighted by selection probability.
A vague OP can be rejected safely only if other evidence still causes the region
to be considered. Sweep thresholds and costs; include uncertain routing.

Then compare staged processing against one-call retained-thread processing on the
same held-out roots. Attribute losses to screening, expansion, extraction, or
classification. Record cache/retry costs. Reject a cascade that only looks cheap
because it silently loses cross-comment opportunities.

### D. Test incremental value of conversation structure

Compare identical text with speaker/reply edges present, absent, or shuffled while
preserving token budget as closely as possible. Separately ablate clarification,
architecture suggestion, independent firsthand corroboration, and resolution
roles. Shuffling is a diagnostic perturbation, not natural-distribution evaluation.
Control for thread length and source when assessing depth/reply-count features.

Report whether structure improves attribution and evidence recovery, not just
whether a classifier learns that long threads are positive. Compare automatic
clusters with human evidence clusters to separate selection failure from inference
failure. A graph neural network is unjustified unless simpler ID-aware input fails.

### E. Test sentiment, education, and unsupported solutions

Label real held-out examples for attempted task, failure specificity, residual
work, and gap subtype. Supplement with clearly marked synthetic minimal pairs:
remove the insult but preserve workflow details; add an insult without adding a
task; replace a reported success with an untested suggestion. Predictions should
track evidence, not tone. Synthetic tests diagnose behavior, not prevalence.

Have reviewers assess proposed remedies for grounding, necessary assumptions,
non-AI alternatives, and mistaken claims of feasibility. Compare need-only,
capability-only, and optional architecture outputs. Test whether asking for a
solution increases fabricated constraints or makes reviewers overrate candidates.

### F. Test duplicate matching and ranking dimensions

Annotate pairs spanning exact duplicates, same episode, same workflow variant,
related workflows with different constraints, and deceptively similar vocabulary.
Compare lexical and embedding candidate retrieval, then pairwise adjudication.
Measure candidate-pair recall, false merges/splits, and cluster coherence. Keep
same-family episodes in one evaluation split; otherwise duplicates can inflate
extraction or ranking performance.

Ask reviewers for pairwise research-priority judgments with the evidence visible,
and label “insufficient information” where appropriate. Compare the four proposed
dimensions, the expanded evidence view, and a simple specificity-only baseline.
Measure precision@K, family diversity@K, agreement, and review time. Countercheck
whether apparent pain/feasibility predicts preference only because of verbosity.
Do not interpret researcher preference as future sales or ROI.

### G. Audit time and coverage sensitivity

Run snapshot analysis with all retained context, then with post-cutoff creations
excluded. The latter still uses retrieval-time text that may contain later edits;
it is **not** a historical as-of reconstruction. Verify scope flags for each input.
Exclude system-only bumps as new demand while retaining old episodes for historical
context. Mask selected sibling/correction nodes to estimate sensitivity to known
coverage losses; never claim this reconstructs the missing HN branches.

### Deliverables and order

1. Annotation guide, local split/selection manifest, and pilot agreement report.
2. Context ablation with costs, errors, and uncertainty intervals.
3. Gate and cluster-selection tests if context adds value.
4. Duplicate/ranking tests and a later-day/source validation plan.
5. Architecture decision recording what passed, failed, or remains inconclusive.

No default model, pricing assumption, context radius, screen threshold, embedding
store, final ranking weights, or production build should be committed from this
literature review alone.

## 10. Implications for the third source

Prefer a source whose participants discuss **performed professional work**, where
questions elicit process details and users return with attempted fixes or outcomes.
This complements HN's broad technical discussion and Make's implementation-support
context. Higher value in profession-specific communities is a hypothesis, not a
measured result from the current dataset.

| Desired property | Why it matters | What to measure in a source pilot |
| --- | --- | --- |
| Firsthand practitioner participation | Access to real tasks, artifacts, and constraints | Fraction of human posts with attributable work episodes |
| Clarification and follow-up | Distributed evidence and reported resolution | Added supported fields from replies; follow-up latency |
| Stable IDs and reply/quote structure | Reconstructable clusters and updates | Parent/root resolution, text gaps, quote attribution |
| Chronological enumeration and public unauthenticated access | Compatible with existing acquisition requirements | Observable coverage, pagination, rate limits and access stability |
| Available context | Distinguishes isolated complaint from actual need | Fraction requiring older history or unavailable attachments |
| Repeated independent reports | Recurrence assessment | Distinct firsthand episodes/families per review hour |
| Profession diversity without excessive promotion | Tests workflow hypotheses beyond AI enthusiasts | Source/role strata, promotion and generic-discussion rates |
| Legible workflow artifacts and system boundaries | Supports implementation-gap reconstruction | Supported inputs/outputs/handoffs, not just AI mentions |

Legal, accounting, insurance, property management, construction, logistics,
healthcare administration, recruiting, sales operations, and small-business
communities are domain hypotheses to compare. No particular platform's present
API accessibility or permission to collect it is established here. A source that
requires authenticated access falls outside the current probe's boundary even if
its content is attractive. A new access model would require an explicit boundary
reassessment, not a workaround.

Run matched chronological windows across prospective sources, enumerate the full
chosen source scope, and annotate random human discussions. Profession selection
is an explicit source-strategy decision, not a hidden category or keyword filter
inside the existing collector. Compare useful, grounded workflow episodes per
1,000 human posts and per review hour, with coverage and context cost. Report the
fraction discovered only after replies and the fractions resolved by education,
configuration, or actual implementation. More negative AI posts is not success.

Do not select the third source solely for explicit buying intent. A useful source
may expose latent needs through failed adoption. Conversely, a vendor-help forum
may be very specific but mostly contain configuration questions already answered
by existing tools. The pilot should measure both and preserve negative results.

## 11. Open design decisions

| Decision | Evidence needed before commitment |
| --- | --- |
| Are evidence clusters worth their selection complexity? | B2–B6 quality/cost comparison and actor-conflation audit |
| Is a parent-aware cheap screen sufficient? | Episode recall and random rejected-region audit |
| How wide/deep should expansion go? | Marginal field recovery, corrections recovered, tokens, and coverage by region size |
| When may clusters cross branches? | Annotated same-actor references and false-merge rate |
| Should reconstruction and gap classification use separate model calls? | Cost and unsupported-inference ablation, not stage count preference |
| How many schema fields should be mandatory? | Missingness, reviewer use, annotation agreement, and forced-field hallucination |
| Does negative sentiment add anything beyond failure details? | Held-out ablation and neutral/negative minimal pairs |
| Do reply patterns improve ranking beyond text? | Structure ablation controlling for thread size and source |
| Can feasibility be assessed from discussion alone? | Agreement on reported proof versus assumptions; subsequent technical validation |
| What counts as sufficiently independent corroboration? | Cross-post/account ambiguity audit; conservative counting policy |
| Can one-day data support calibration? | Positive counts and intervals; likely requires later windows |
| Which third source adds evidence rather than just more posts? | Matched source pilot with public coverage and review-efficiency measurements |

The next concrete step is an annotated context-ablation pilot. The architecture
should follow its error analysis, especially whether reply context recovers
supported needs without synthesizing fictional workflows from different people.
