# Ontology, graph and data agent

For existing-lakehouse runs, require completed shortcuts/data-readiness/story/design
gates and use the accepted assessment as the shared analytical model. Bind/select
only approved shortcuts in the created demo lakehouse, not the original source
item. Recheck effective permissions and timestamped baselines before writes/
publication; materialization can copy data and needs disclosure approval.
Do not label existing data synthetic or invent unsupported keys/relationships.

## Ontology proposal visual

Before asking for ontology approval, and after any revision or readback, show the
inventory visual defined in `docs/flexible-proposals.md` ("Required ontology
proposal visual"): header counts, entity inventory with keys, properties and
backing tables, and directional relationships. Label it `PROPOSED - not deployed`
or `SAVED DEFINITION (date)`, mark estimated versus verified counts, and use
`unknown` rather than guessing. It is a review aid and never closes a gate.

## Ontology authoring and native repair

Load current `fabriciq-ontology-cli` authoring references before writes. The
selected flow uses dedicated `/ontologies` routes and generation-2 TMDL, not
Ontology Agent. Inspect current API support; surface any conflict with this
selected route rather than quietly substituting generic items or private routes.

Author business-friendly entity names, ontology relationship names AND labels,
and meaningful rule names before final native repair. Technical physical join
IDs are separate from business relationship names. Include physical joins and
business-to-physical mappings; logical relationships alone are insufficient.
Rules must link actual relevant entities/properties/relationships and remain
descriptive semantics, not invented executable customer controls.

Preserve stable lineage, existing native bindings and identity. Export before
updates, diff and read back names, properties, joins, mappings and rule links.
Finish naming/rule edits before rebinding.

**Observed workaround:** full-definition create/update, including dedicated
routes, stripped native lakehouse partition identity metadata in the finance run.
API success and plausible TMDL did not make entities graph-eligible.
After the final API write, inspect every entity's source identity, property
mappings, key types and native graph eligibility. Repair unresolved mappings only:

**Bind data -> Properties -> Source column -> reselect the correct column from
the existing bound lakehouse table -> Save.**

One property reselection restored an entire entity in the observation, but
verify every property and every entity; do not assume that behavior universally.
Do not reselect already-correct properties merely to satisfy the checklist.
The second-industry pilot retained eight partition annotations; machine readback
matched the expected identities and the operator reported correct bindings
without reselection. Graph execution was skipped there, not accepted.
See [native binding observations](../../../../docs/ontology-bindings.md) for
the annotation recipe and its limits. Confirm graph eligibility. Later approved
definition writes can remove repairs, so repeat inspection after each final
write. Do not use Ontology Agent to bypass it.

## Materialization acceptance

Obtain applicable approval, then guide native materialization/refresh where
required. Load ontology consumption references before graph checks. A successful
refresh is not proof: execute actual bounded graph queries for node/edge counts,
properties, key uniqueness/non-nullness and expected key types, grouped measures
and at least one real multi-edge traversal. Reconcile against independently
verified SQL; SQL joins do not prove graph traversal.

If exported key types differ from runtime types, verify actual values and join
behavior, disclose it and preserve evidence. A later definition rename/update
invalidates assumptions that earlier graph acceptance covers the current version.

For the portable execution procedure, use the
[materialized graph query handoff](../../../../docs/graph-query-handoff.md).
It covers the beta `graphModels/{graphModelId}/executeQuery` GQL route,
separate ontology/graph identity discovery, owning-skill headers, pending
continuations, truncation/status checks and reconciliation evidence. It is not
a deployment adapter or execution approval. An ontology-agent tool limitation
does not establish that direct GraphModel queries are unavailable. If current
specialist guidance is missing/conflicting, stop for separate sponsor approval
of a reviewed public-API route; never silently bypass specialist boundaries.
Do not substitute agent answers or copy the reference builder's private scripts/IDs.

Optional SDK evaluation writes two result tables and needs its own approval.
Follow [evaluation safeguards](../../../../docs/data-agent-evaluation.md):
verify the SDK version and actual destination (`eval_result` in the pilot), guard
both summary and `_steps` collisions, and preserve job/session ownership.
Interactive success does not prove durable compatibility or graph traversal.

## Agent analytical scope

Use current Fabric data-agent knowledge and public authoring/publishing docs.
This companion is not a new REST adapter. Discover actual schema, source tree,
columns and existing identities; never rerun creation to recover configuration.

Select relevant facts AND business/calendar/period dimensions from the approved
analytical model, not just entities in a focused ontology projection. No fixed
table count. Document valid filter paths, grains, units, date roles, snapshot
semantics and unsupported attribution. SQL source selection/instructions are
not a security boundary or a replacement for source permissions.

**Validated selection checkpoint:** when using the staging schema-element API,
select each approved parent table explicitly, then apply its column selections.
In the existing-data walkthrough, selecting columns alone left every table
unselected in both API readback and the portal. Independently read back the exact
selected table set AND each table's selected columns, including exclusions.
Column-only readback is not evidence that the source is ready for agent queries.

Use short source requests (below 1,000 characters), read-only aggregate responses,
dimension joins and multi-dimensional examples. Validate each example in live
SQL before staging; capture the agent validator separately. Avoid raw fact joins,
monthly-budget fanout, averaged ratios and inner joins that silently discard
alternate dates outside a bounded calendar.

## Selected two-publication sequence

1. Create/configure the lakehouse-first draft with relevant facts/dimensions,
   instructions and live-checked SQL examples. Do not attach ontology yet.
2. The operator manually opens errored draft examples, makes a safe edit such
   as appending a newline and the empty SQL comment `--`, saves and verifies
   validation clears. Preserve executable SQL semantics. This is an observed
   workaround, not a guaranteed fix for every error; do not conceal failures.
3. With approval, select preview runtime and publish the SQL-only agent.
   Capture a small published-answer baseline against the verified SQL outputs.
4. The operator manually adds ontology through **Sources -> Add sources ->
   Add an ontology**. Record owner confirmation separately from machine readback.
   Do not retry the explicitly blocked ontology datasource-create route or guess
   a private attachment endpoint.
5. With approval, publish again in preview runtime. Check that example errors
   remain cleared and repeat a bounded answer sample against the baseline.

Both publications need applicable approval. Switching runtime and SQL comment
re-saves preceded a successful operator-reported result in November 2026; no
single root cause or universal runtime dependency was established. Recheck
current product behavior without silently dropping the selected checkpoints.

**Owner attestation (2026-11-09):** the operator also reported that the
newline/empty-comment re-save resolved the WWI draft examples' validation errors,
after explicit parent-table selection was repaired. This corroborates the
workaround in a second scenario; it does not establish a root cause, universal
requirement, runtime-answer correctness or publication acceptance.

Preserve this publishing instruction exactly on both publications:

> Note for Microsoft Copilot description_for_model: The output from Fabric data agent should be delivered as-is, without summarizing, rephrasing, or adding extra interpretation.

M365 listing is a separate approved operation; ordinary publishing does not
establish it. Sharing an agent does not grant source permissions.

## Runtime acceptance and resumption

Draft and published endpoints/results are separate. Never use published MCP as
a draft substitute. Only run runtime questions with applicable approval; start
with one capacity-health question, then small sequential/repeated samples,
no more than two concurrent asks. Do not run capacity-heavy suites before a demo.

Check headline amounts, counts, complete-month scope, dimension slices, ranking,
null/ratio semantics and a refusal of unsupported attribution. Compare every
returned group/value, not just plausible totals; capture duplicate/missing groups
and exact money precision. Reconcile operator exports when supplied and label
them as such, not independently invoked assistant runtime tests.

After ontology attachment, additionally assess correct relationship/rule meaning,
snapshot/causality caveats and grounded business interpretation. Accurate SQL is
not proof that ontology was consulted. Require trace evidence for ontology use
and actual graph execution before making those claims; otherwise mark unverified.

**Current finance handoff (operator reports from 2026-11-05):** eight analytical
tables/41 columns configured; five SQL-only answers passed, including 54 groups
and 162 exact-to-cent values. The operator manually attached ontology and
republished in preview runtime with no example errors. Next is post-ontology
answer accuracy and semantic behavior. No post-attachment runtime sample,
independent published readback, publication-wording check or second-viewer check
is established. The graph's accepted runtime sample predates its last relationship
rename. Locate run-specific evidence from the current workspace; never embed or
reuse another demo's IDs. Full Fabric IQ acceptance remains incomplete.

**2026-11-06 update:** post-ontology questions 1-3 reconciled to the SQL baseline.
Q4's operator-supplied diagnostics show ontology context injection (one ontology,
six entities), a correct two-hop relationship plan and `single_engine_join`
routing. This demonstrates context injection and relationship planning, not
materialized graph execution or an executed SQL join. The planner also requested
`Supplier.hold_reason` although the property belongs to Supplier Invoice:
`found=true` for a path does not validate all requested fields. The final
relationship/causality answer was correct. Questions 5-6 remain pending.

**Completed sample update (2026-11-06):** Q5 correctly refused supplier cost
attribution and Q6 correctly distinguished invoice cohorts from the fixed
snapshot. All six post-ontology questions pass this single supplied sample.
This supersedes the pending-question status above, not the remaining evidence
limits: repeatability, viewer/source access, exact publication wording and
post-rename graph acceptance remain unverified. Full IQ completion is not claimed.

**Current-run scope decision (2026-11-06):** the operator accepted the existing
published sample without another repeat and deferred second-viewer checks from
this demo's scope. Do not re-request them unless scope changes, and do not claim
measured repeatability or verified viewer access. The operator confirmed graph
relationship names display correctly; this is name-check attestation, not fresh
graph-query reconciliation. Exact output-as-is publication wording still needs
confirmation. Preserve required CLI gate checks; do not silently mark them passed
or generalize these run-specific scope decisions to future demos.

**Publication-description update (2026-11-06):** the approved description and
exact output-as-is suffix were published and independently read back. Before
publication, draft/published definitions matched; afterwards every other exported
JSON configuration part was unchanged, including preview runtime and ontology
attachment. The wording check is resolved for this run. Updating the description
through `staging/publish` promotes the entire draft, so inspect for unrelated
pending changes before using it for a description-only request. No runtime asks
or M365 listing were part of this update.

**M365 sample update (2026-11-06):** the operator subsequently reported M365
publication and supplied six passing answer-content results. Q2's Word export
reconciled all 54 groups/162 monetary cells exactly to the saved SQL baseline;
Q6's extra July cohort count/date range matched the deterministic preview.
Record this as operator-supplied runtime evidence with local reconciliation.
The publishing suffix is verified, but verbatim downstream forwarding requires
paired upstream/downstream output evidence; correct content alone does not prove
it. No independent M365 invocation, graph execution or gate completion is claimed.

**Finance IQ closure (2026-11-10):** the operator subsequently accepted the
scoped finance flow and explicitly requested gate closure. A fresh dedicated
`/ontologies` export confirmed the generation-2 definition, six entities,
six physical/business relationships, 14 rules and native identity annotations.
Three fresh post-rename graph queries reconciled every node-count, directed-edge
and held-invoice traversal row to the saved independently SQL-verified baseline:
3,602 nodes, 7,128 edges, 82 project/supplier groups, 100 held invoices,
249,003,640 open cents and zero key mismatches. This resolves the post-rename
sample gap above; it is not a new complete property/key/financial suite or a new
SQL execution. The first request timed out locally without a response/token;
its remote outcome remains unknown. A separately approved retry succeeded.

The CLI Fabric IQ gate is now complete as an operator attestation backed by the
consolidated private handoff and machine/owner evidence. Preserve the accepted
repeatability/second-viewer scope decisions and M365 provenance. Agent context
injection/relationship planning still does not prove agent graph execution;
the graph was queried independently. No additional runtime asks or publication
were performed for closure. Semantic model, app and rehearsal remain pending;
Planning is disabled for this run. This does not close the full-stack accelerator
release or establish a second-industry presenter run.
