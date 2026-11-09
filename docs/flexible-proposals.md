# Research-led, industry-independent proposals

## What the presenter supplies

A public customer website, audience (roles and decision priorities), and a high-level
description of current sources/data are enough to **start discovery**. Optional inputs
include a preferred topic, demo length, history/volume budget, geography, deployment
target and semantic-model/Planning needs. They need not supply an industry template,
schema, table count or synthetic generator code.

Copilot researches the website, proposes use cases and a synthetic model, and asks the
presenter to choose/approve. An inaccessible or ambiguous website requires a disclosed
gap and clarification, not a guessed industry. Public evidence does not establish
internal systems, sensitive policies or actual operational problems.

## Sequence

This sequence is the default **synthetic** branch. Version-2 briefs can instead
select `data_mode: "existing-lakehouse"`; see
[Existing-data option](../README.md#existing-data-option) and the companion
[discovery/data reference](../.github/skills/fabric-demo-companion/references/discovery-and-data.md).
The alternative creates a dedicated lakehouse, stops for manual individual table
shortcuts and effective source-read-only permission verification, then assesses
only approved metadata/aggregates. It does not reinterpret existing tables as
generator recipes, generate synthetic facts or label real data synthetic.
`proposal` stays null; the accepted data-readiness assessment supplies one shared
analytical model and timestamped baselines to downstream specialists.
Source mutation is prohibited; shortcuts alone do not enforce that boundary.

For automated assessment with a stricter timeout than the SQL MCP exposes,
the operator may explicitly select the optional project-owned ODBC runner.
See [timeout-controlled SQL runner](../README.md#optional-timeout-controlled-sql-runner).
It accepts hash-approved structured metadata, single-table aggregate and count-only
relationship plans, not
arbitrary SQL or raw records. It preserves immutable runs, verifies execution
identity and shortcut drift, and retains per-request evidence. It does not infer
relationships, enforce a byte-scan quota, prove remote timeout cancellation or
complete readiness automatically.

1. `python -m demo_accelerator init --output intake.json` writes a version-2 customer
   brief with `proposal: null`; no industry is preselected.
2. Fill the customer, audience, sources, optional features and workload budget.
   `plan intake.json` returns a research/ideation brief for Copilot.
3. In Chat, Copilot reads public pages and suggests 2-3 use cases. Each recommendation
   includes audience fit, the decision to demonstrate, source relevance, invented
   supporting data and the intended insight-to-action story.
4. Copilot proposes a schema with source mappings, entities, table grains, dates,
   relationships, metrics, distributions, assumptions and table-by-table purpose.
   The table count is an **output** of that design. Do not pad it to a quota or omit
   a useful table to meet a ceiling.
5. The presenter selects/revises the proposal. Copilot puts the selected design in
   `proposal`, with citations/notes in `research`. Record `industry_confirmed` only
   after user confirmation. Local previews may be generated for review before final
   approval; they make no Fabric writes.
6. `plan` validates recipes, dependencies and row budget, generates data in memory
   and reports actual counts. `generate` freezes the selected design into a new run.
   Explicit story/design approvals and evidence are required before data deployment.
   Changing schema or metrics means a new run and fresh approval.

The CLI has **no embedded LLM or website crawler**. Copilot performs research and
suggestions using its web tools and conversation with the presenter. `plan` on an
empty proposal is a task brief, not a falsely claimed automatic recommendation.

## Version-2 data contract

Use `examples\insurance-claims.json` as a worked example, not a required pattern.
It demonstrates claims, teams and settlement entries with **no transfer, capacity,
county, risk-screening or uncompensated-care assumptions**. It is intentionally
fictional and not already approved.

`proposal` contains:

| Field | Meaning |
|---|---|
| `industry`, `title` | Researched industry and proposed demo title; arbitrary text, no allowlist |
| `business_question` | Primary question the live artifacts will answer |
| `audience_rationale`, `decision` | Why this audience cares and what action the demo enables |
| `assumptions` | Synthetic assumptions, inferred context, time/grain limitations and caveats |
| `tables` | Explicit schema and deterministic generation/transformation recipes |
| `metrics` | Exact typed aggregations, filters, groups, time semantics and units |

Each table has a lowercase SQL `name`, `layer` (`bronze`, `silver`, `gold`,
`supporting`), `grain` and `purpose`. Gold tables have a unique `key` for ontology
binding. Metadata tables use reserved `meta_` names.

A generated table declares `rows`, a zero-based `source` index into intake.sources,
and `columns`. Each column has a name, type, business description and generator:

| Recipe | Parameters | Types |
|---|---|---|
| `sequence` | optional integer `start` (default 1) | `int64` |
| `integer` | `min`, `max` inclusive | `int64` (including minor-unit money) |
| `choice` | typed nonempty `values` | Any supported type |
| `boolean` | `true_percent` from 0 to 100 | `boolean` |
| `date` | Samples the configured date window | `date` |
| `label` | Fictional `prefix`, followed by sequence | `string` |
| `reference` | `table`, `column` pointing to a same-typed declared unique key | Matching type |
| `date_sequence` | `frequency`: `day` or `month`; rows must exactly cover the configured window | `date` |
| `date_part` | earlier date `column`, `part`: `year`, `quarter`, `month`, `month_start` | `int64`, or `date` for month start |
| `date_offset` | earlier date `column`, `min_days`, `max_days` (0-365) | `date` |
| `lookup` | parent `table`, `column`, `via` an earlier direct reference to that table; optional bounded date offsets | Matching type |
| `map` | earlier `column`, explicit typed `cases` of `when`/`value` | Any supported type |
| `scaled_integer` | earlier integer `column` and `factor_column`, positive `divisor` | `int64` |
| `difference` | earlier integer `left`, `right` | `int64` |
| `allocate` | parent `table`, cycle-reference `via`, parent `total_column`, `factor_column`, positive `divisor` | `int64` |

`choice` supports `mode: "cycle"` for an ordered repeating sequence; its default
is deterministic random selection. `reference` also supports `mode: "cycle"` with
positive integer `stride` (default 1). Combine cycle strides and declare table
`unique_by` columns to enumerate a unique Cartesian grain, rather than randomly
sampling budget cells. `unique_by` is checked locally and in the notebook.

Dependent columns must appear after their inputs; table dependencies remain
topologically ordered. Lookups copy from the exact parent row identified by `via`,
not from independently drawn foreign keys. A column can declare
`references: {"table": "...", "column": "..."}` to validate business key lineage
and expose it to graph/model authoring. Otherwise references and copied lookup
keys retain their inferred lineage. Every relationship targets a same-typed
declared unique key and is checked against generated rows.

`allocate` requires a stride-1 cycle reference and at least one child per parent.
It computes `floor(parent_total * parent_factor / divisor)` and divides that
integer total among the parent's children, assigning remainder cents in child
order. It preserves exact totals even when children are unevenly distributed.
`scaled_integer` also uses floor division. Inputs and intermediate products are
bounded before generation. A missing map case is an explicit generation error,
not a null/default value.

Optional table `checks` are assertions, not row-dropping filters. They use the
same typed `column`/`op`/`value` format as filters, or `other_column` instead of
`value` for same-typed row comparisons (not `in`). For example, assert
`paid_cents <= invoice_amount_cents` or `invoice_date <= due_date`. A failed
check stops local generation or the notebook explicitly.

Supported types are `string`, `int64`, `boolean` and `date`. No arbitrary Python,
SQL or executable strings run from proposals. No silent defaults for unsupported
distributions. Integer values and conservative sum/average bounds must fit the
exact JavaScript-safe range (absolute value at most `2^53 - 1`) so app and data
results agree. These recipes support explicit date ordering, balance equations
and dependent allocations; they do not automatically infer realistic distributions.
Other correlations, seasonality or process constraints still need a tested recipe
extension. Disclose unsupported realism rather than passing independent random
values off as a realistic business process.

A transformed table declares `from`, inherits its source schema, and can declare
`filters` and `deduplicate_by`. It omits `rows`, `source` and `columns`.
Filters have `column`, `op` and `value`; operators are `eq`, `ne`, `gt`, `ge`,
`lt`, `le`, `in`. Deduplication picks the lexicographically first full row per key,
deterministically in both Python and Spark. Empty transformed outputs are supported
unless another generator must draw references from them.

Dependencies are topologically ordered, including generated foreign keys.
Unknown targets, cycles, type mismatches and invalid/nonunique keys fail explicitly.
Gold-to-gold references populate the ontology and semantic-model contracts; staging
relationships do not automatically become business entities.

Each metric declares a unique SQL-safe `name`, business `label`, a gold `table`,
`aggregation` (`count`, `sum`, `avg`), optional numeric `column`, typed `filters`,
optional `group_by` and `time_column`, `unit` and `interpretation`. `count` counts
rows. Money stays in the declared minor units; do not silently divide by 100.
Undated metrics are not given a period. Dated metrics have a selected-quarter
expected answer and explicit completeness flag.

`period_grain: "month"` produces monthly period views and expected groups;
the default is quarter. Expected outputs also list covered quarters and their
completeness. Partial coverage is not a full-quarter financial result.

Optional `derived_metrics` declare `name`, `label`, `operation` (`difference` or
`ratio`), `left`, `right`, `unit` and `interpretation`. Operands must be earlier
additive sums/differences with identical grouping, period grain, conformed
dimension/date lineage and units. Difference preserves units; ratio uses unit
`ratio`, where `0.10` represents 10%. Independent aggregate views are joined on
every group/period key, never raw facts. Missing operands remain null and zero
denominators yield null. Recompute ratios after aggregating their components;
never average or sum displayed ratios. DAX uses the same definitions and
intersects explicit metric filters with viewer filters.

Optional `reporting` identifies the gold `calendar_table`/`calendar_column` and
`period_table`/`period_column`, a snapshot `as_of_date`, and explanatory `notes`.
This context is propagated to every specialist contract. It is not a deployed
filter or permissions rule: the model/app author must enforce its reporting grain.
For monthly budgets, use complete-month selectors, not arbitrary daily ranges.
Invoice-date filters define cohorts, not historical AP balances.

SQL views and DAX measure contracts use these same declarations. Aggregate each
fact independently; cross-fact comparisons and additional graph walks need explicit
grain-aware design, not an automatic join. V2 currently emits topology GQL plus the
schema contract, not invented customer-specific graph traversals.

## Scope without an arbitrary table count

There is **no maximum or required number of tables** in the version-2 contract.
Physical Delta count is `len(proposal.tables) + 2` governance tables. Each bronze
table also has a raw JSON extract in Files, which is not a Delta table.
Governance row count is `2 * len(proposal.tables) + 2` (one lineage row per
declared table, plus a catalog row for every declared/governance table).

The guardrails bound actual work:

- Per-generated-table row ceiling (`scope.max_rows_per_table`).
- Total physical-row budget, counting raw copies, Delta staging/derived tables
  and governance rows (`scope.max_total_rows`).
- A fixed, reproducible date window and seed.
- Operator review of purpose, transformation complexity, Spark write overhead,
  IQ graph size, capacity and app/Planning requirements.

Transforms use conservative inherited row bounds at validation; `plan` then reports
actual generated rows. A 25-table design with small dimensions can be cheaper than
a 10-table design with larger facts. Budgets are review guardrails, not runtime
guarantees. Additional per-table Spark writes and exact checks still cost time.

The model can therefore have 10, 25 or another justified number of Delta tables.
Legacy version-1 healthcare/manufacturing examples remain regression fixtures only.

## Ontology business vocabulary and binding acceptance

The generated ontology contract is a physical mapping, not a finished business
vocabulary. During specialist review, propose singular business entity names and
meaningful, direction-aware relationship names. A reader should understand an
`entity -> relationship -> entity` statement without decoding SQL naming
conventions. Do not expose `dim_`/`fact_` prefixes or foreign-key-derived names as
the default customer-facing ontology vocabulary. Keep physical tables, columns
and backing joins unchanged; preserve ontology lineage tags when renaming
elements. Relationship names must be unique. Native portal edits can store a
business-readable relationship `label` while retaining its internal `name` and
backing relationship identifier; this preserves identity without exposing the
technical name as the displayed business meaning on label-aware surfaces.
However, the portal Relationship Types sidebar displays the ontology relationship
`name`, not its `label`. Give both a business-readable value at initial authoring;
keep technical identifiers only on the separate physical backing relationships.
When renaming an ontology relationship, preserve its lineage tag and backing
relationship reference, and update every rule's `ruleReferencedRelationship`
to the new ontology name. Verify names, labels and rule references in readback
before the final native binding checkpoint.

For example, `Budget -> Budgeted Under -> Cost Category` and
`Cost Posting -> Charged To -> Project` describe business meaning; a name such as
`fact_budget_cost_category_id` describes an implementation detail. Confirm the
meaning against the approved scenario: an invoice association does not establish
causation for a cost variance. See Microsoft's
[ontology overview](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
and [relationship guidance](https://learn.microsoft.com/en-us/fabric/iq/ontology/how-to-create-relationship-types).

A live specialist-assisted finance run exposed the following **observations**,
not universal or permanent platform limitations:

- A SQL-endpoint-backed TMDL definition round-tripped successfully while the portal
  showed generic table/property bindings. Structural readback alone did not prove
  lakehouse identity or runtime source access.
- A portal-created binding supplied a OneLake expression and explicit lakehouse
  identity metadata. A subsequent `updateDefinition` accepted that expression but
  omitted seven requested `ONT_` identity annotations from all six primary
  partitions on readback. Do not assume replaying portal-exported annotations
  preserves native binding state; avoid another whole-definition update merely
  to rename elements after native bindings are repaired.
- A separately approved same-workspace copy experiment submitted the freshly
  repaired full definition in one `createItem` call, changing only the platform
  name/logical ID in its parts. Creation succeeded, but readback again omitted
  `ONT_WorkspaceId`, `ONT_ItemId`, `ONT_ItemKind` and `ONT_ItemName` from all six
  primary partitions. The remaining non-platform parts were preserved. Thus a
  fresh create, not just an update, failed to round-trip this native identity
  metadata in that run. Before any manual rebinding, the operator also reported
  both ineligible entities and generic property bindings on the copy. This copy
  failed rebind-free acceptance. The operator subsequently clarified that the
  entities themselves were correctly bound to the lakehouse; the properties
  were not. Do not describe this as a missing entity-level lakehouse binding or
  infer that from the absent exported annotations. The original ontology was independently
  confirmed unchanged. Keep this operator observation separate from machine
  readback evidence. Portal rendering/eligibility and runtime acceptance remain
  distinct checks.
- The operator reported that the primary source already displayed the correct
  lakehouse while properties still rendered generically. Native property
  reselection for two entities restored their rendering; readback also restored
  `ONT_WorkspaceId`, `ONT_ItemId`, `ONT_ItemKind` and `ONT_ItemName` on those
  partitions. This is stronger evidence than treating the issue as cosmetic,
  but it is not graph or runtime-query verification.
- The same reselection changed those entities' key property types from `int64`
  to `unknown` in the exported definition, although the backing columns remained
  `int64`. Repeating native reselection for the four remaining entities restored
  their identity metadata too, and the operator reported all six graph-eligible;
  all six exported entity keys then showed `unknown`. Do not automatically
  overwrite this drift or call it cosmetic: inspect native eligibility and source
  key types before materialization, then verify actual graph keys, properties and
  query results afterward. Eligibility is not runtime type verification.
- Subsequent live graph readback represented all six primary keys as `STRING`,
  while foreign-key properties remained integer. Runtime queries confirmed
  unique, non-null, integer-convertible keys, all six node/edge counts and
  directions, financial totals, and actual two-edge traversal parity with SQL.
  This supports the repaired projection for that run; it does not establish that
  `unknown` is always safe or that graph keys retain SQL integer types. Use the
  actual graph schema and typed values when writing predicates.

The public [GQL query API](https://learn.microsoft.com/en-us/fabric/graph/gql-query-api)
now supports querying a materialized graph directly, even where an installed
ontology skill still describes source-table joins only. Discover the actual graph
item and exported labels; do not infer them from physical SQL names. Quote labels
and identifiers with backticks (for example, `Project` is a reserved word), and
use explicit `GROUP BY` for non-aggregate return expressions. Inspect GQL status,
additional warnings and continuation state rather than treating HTTP 200 as
success. A pending response must resume the same query with its opaque
continuation token, encoded exactly once. Source SQL joins are independent parity
evidence, not a substitute for graph execution.

Check the source card, each property mapping, supported entity-key types, native
graph eligibility and actual source-query results separately. Preserve the full
latest portal definition before any change, inspect its diff, obtain the required
write confirmation, and read it back afterward. Keep operator rendering
observations separate from machine definition and query evidence. A native portal
repair may be required; use supported UI actions, not guessed private endpoints.
Record these specialist observations outside the immutable generated run.

### Required native binding checkpoint

The selected flow is specialist-authored generation-2 TMDL through the dedicated
Ontology endpoints: `POST /v1/workspaces/{workspaceId}/ontologies` for creation
and `POST /v1/workspaces/{workspaceId}/ontologies/{ontologyId}/updateDefinition`
for approved definition updates. Author both physical backing joins and business
relationships. Do not use the Ontology Agent in this flow.
Native property reselection is an explicit operator step after the final API
write and before graph materialization, including for copies of repaired definitions:

Finish rule authoring before this checkpoint too: use business-readable rule
names rather than numbered placeholders or internal metric IDs, preserve rule
lineage when renaming, and explicitly link applicable ontology elements.
The public TMDL uses `ruleReferencedEntity`, nested
`propertyScope: specific` / `ruleReferencedProperty`, and peer-level
`ruleReferencedRelationship` references to actual relationship names, not labels.
Read back every reference and statement; prose mentioning an entity is not a
linked element. Rules describe approved metric meaning and illustrative
constraints, not executable enforcement or undisclosed customer policies.
Keep synthetic-data disclosures explicit.

The clean finance redeployment completed this sequence on 2026-11-05:
dedicated API create, business-named linked-rule update, final per-entity native
reselection, then operator-triggered graph materialization. Live GQL verified
3,602 nodes, 7,128 directed edges, all entity property sets, unique/non-null
integer-convertible string keys, full/Q3 totals, all 12 project Q3 aggregates,
and the 82-group Project-Invoice-Supplier held-invoice traversal against the
previously captured independent live SQL baseline (not re-queried this pass).
The repaired ontology, including all 14 linked rules, was unchanged after
materialization. Machine evidence is saved in the ignored
`clean-redeploy-v1/graph-runtime-v1` finance IQ package. This verifies the
ontology/graph portion of the selected flow, not the still-pending data agent,
semantic model or app.

1. In the native ontology editor, click each entity, then **Bind data**, then
   **Properties**. In the **Source column** dropdown, expand the existing bound
   lakehouse table and reselect the correct source column for a property, then
   click **Save**. For example, Project's `project_id` maps to
   `dim_project.project_id`. In the finance test, reselecting one property restored
   the whole entity's property bindings; verify every mapping and reselect any
   still unresolved. Repeat for every entity. Keep the existing primary lakehouse
   binding; do not add a secondary binding or change approved keys, grains or joins.
2. Verify property rendering and all selected entities' graph eligibility. A source
   card showing the right lakehouse is insufficient. Stop on unsupported sources
   or unresolved mappings rather than materializing an incomplete projection.
3. Capture a fresh definition and compare source identity, mappings, key types,
   lineage and business labels. Preserve the native repairs; a subsequent
   whole-definition update may remove them again.
4. After the applicable approval, materialize once and verify actual graph keys,
   properties, every relationship type and SQL parity. Do not equate eligibility
   or successful materialization status with runtime acceptance.

Retain this checkpoint until a supported alternative passes an untouched-copy
binding/eligibility test and runtime verification. Do not modify immutable
generated runs to retrofit these instructions.

### Native Ontology Agent experiment

Historical investigation only: the operator explicitly excluded Ontology Agent
authoring from the selected deployment flow. Do not suggest or invoke it as an
automatic alternative to the API-plus-native-reselection procedure above.

A separate empty finance test ontology was authored through the native Ontology
Agent, with discovery/draft/validation in Plan mode and an explicitly approved
partial apply/publish in Act mode. The operator reported correct entity property
bindings without manual reselection. Independent definition readback confirmed
all 32 property mappings, native lakehouse identity metadata on all six backing
tables, and `int64` entity key types. This differs from the API-copy result and
shows native agent property-binding behavior, not an accepted deployment route.

The same readback contained six business entity relationships but no physical
backing-table relationships and no relationship `backingConfiguration`. The
agent reported that its available draft tools could not represent the two-layer
physical relationship structure. This is a limitation observed in that agent
session, not proof of a universal platform restriction. Its apply operation
reported no warnings, despite six physical-binding warnings in the preceding
draft validation; warning-free apply is not traversal acceptance.

These relationships require physical source/target key mappings, not additional
edge properties. Native relationship binding and graph runtime verification
remain outstanding for this experiment. Preserve the untouched post-apply
snapshot and avoid a whole-definition API update that could strip the working
native property bindings. Do not replace the required deployment checkpoint
with this experimental route.

### Dedicated ontology endpoint experiment

Read-only review of the earlier healthcare implementation found an important
untested difference: its generation-2 creator and updater used the dedicated
`/workspaces/{workspaceId}/ontologies` routes, whereas the finance create,
copy and repair experiments used generic `/items` routes. The historical builder
also emitted the public OneLake DFS expression, pinned identity annotations,
table/column source lineage, key markers and the two-layer physical/business
relationship structure. The finance copy already included those binding markers
and six physical relationships; their presence alone did not prevent metadata
loss through the generic route.

The healthcare documentation records a matching post-update definition after
native pinning, but does not establish a fresh untouched-copy deployment with
no initial portal intervention. Its claim that generic item creation necessarily
means generation 1 is too broad: current documentation resolves generation from
definition parts. Do not infer the cause of the finance failure from that history.

The dedicated [create](https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/create-ontology)
and [update definition](https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items/update-ontology-definition)
routes are supported public APIs. An explicitly approved dedicated-create
experiment on 2026-11-05 created a separate finance ontology from a fresh export
of the working reference. Only the display name and logical ID changed within
the definition. All 33 definition parts returned, but all six table partitions
again lost `ONT_WorkspaceId`, `ONT_ItemId`, `ONT_ItemKind` and `ONT_ItemName`.
Both physical and business relationship definitions were unchanged, as were
the property mapping definitions. The original ontology remained unchanged.
Evidence is in the ignored `dedicated-endpoint-test-v1` package under the
finance IQ work area.

Changing the create endpoint alone did not preserve the missing identity
annotations. The operator subsequently reported property-binding problems and
graph ineligibility on the untouched copy. After reselecting one Project
property, the operator reported that all Project properties appeared bound and
Project became graph-eligible. Dedicated-endpoint definition readback changed
only `tables/dim_project.tmdl`: native reselection restored the four partition
identity annotations and updated `ONT_PinnedAtUtc`. No entity, column mapping,
expression or relationship definition changed. This supports a table-partition
pinning explanation for this instance, rather than a missing individual
property mapping. Portal eligibility remains operator evidence, not proof of
materialized graph behavior. No graph was materialized.
An explicitly approved full-definition overwrite through the dedicated
`/ontologies/{id}/updateDefinition` route was then attempted on this copy only.
Its payload preserved Project's native repair and restored the four identity
annotations on the other five partitions; all other parts were unchanged.
The update succeeded, but readback again omitted all four annotations on every
partition, including the natively repaired Project partition. All 33 parts
returned and both relationship definitions were preserved. The working original
was unchanged and no graph was materialized. Evidence is in the nested
`dedicated-update-v1` package. Post-overwrite portal inspection is still pending.
Thus neither dedicated create nor dedicated full-definition update preserved
the native partition identity annotations in these tests; full updates can
also remove a native repair already present on the target.
Do not generalize this result to every
authoring route or claim missing annotations alone prove traversal failure.
Keep the native checkpoint until untouched portal property/relationship checks
and graph runtime acceptance pass.
Do not run the historical scripts or reuse their resource IDs, envelopes or state.

### Data agent authoring and publication checkpoints

**Selected sequence:** add the lakehouse and select the analytical facts/dimensions
first; configure instructions/examples; manually repair draft example errors;
publish the SQL-only agent in **preview runtime**; capture a bounded answer
baseline; manually add ontology context; **publish again**; verify examples remain
error-free and repeat a bounded answer sample. Both publications require approval
and preservation of the output-as-is instruction. Do not attach the ontology
before the first publication in this selected flow.

Use the approved scenario and actual SQL schema to author agent instructions,
source descriptions/instructions, selected gold tables/columns and a small set
of examples. The ontology supplies business meaning; the lakehouse source
supplies T-SQL numerical answers. A SQL response is not proof of graph traversal.
Keep source requests below 1,000 characters, aggregate facts independently,
preserve complete-month and snapshot semantics, and disclose synthetic data.
Source selection and aggregate-only instructions are not substitutes for Fabric
permissions or a service-enforced security boundary.

**Analytical scope is broader than a focused ontology projection.** Select the
approved scenario's relevant facts and supporting dimensions, including calendar
and period tables where declared. Do not derive the SQL source allowlist only
from ontology entities or impose a fixed table count. The agent should support
combined dimension filters, grouping and drill-down along valid relationships.
For finance, this includes project/portfolio, cost category and month/quarter/year
for budget/actual measures, and project/supplier with invoice-date cohorts for
invoice measures. Supplier does not filter costs/budgets; invoices have no
cost-category attribution in this model.

Verify actual columns and date-role joins. Join monthly budget month-start to
the unique calendar date, not every date in its month; independently aggregate
facts at matching keys before joining. Invoice due dates can exceed the bounded
calendar: do not silently discard those invoices through an inner date join.
Keep invoice cohort periods distinct from the fixed balance snapshot. Include
live-checked dimension joins and multi-dimensional examples, not just headline
totals. Calendar dimensions need not become graph entities to be agent SQL sources.

The current public REST surface supports dedicated
[data agent creation](https://learn.microsoft.com/en-us/rest/api/fabric/dataagent/items/create-data-agent)
and [staging source configuration](https://learn.microsoft.com/en-us/rest/api/fabric/dataagent/staging/create-datasource).
The datasource contract now lists Ontology under supported Fabric item types.
Recheck the target service instead of treating the healthcare run's historical
`OntologyAddAsDataSourceBlocked` response as a permanent limitation. An explicitly
approved attachment attempt must preserve the error and stop at portal attachment
if blocked; never manufacture a definition that merely looks attached.
Do not modify the ontology definition while configuring the agent.

Run every example against the live SQL endpoint before staging it, then inspect
the agent's separate example validation status. The historical healthcare run
had valid SQL and portal-valid draft examples but invalid published examples;
successful SQL or a warning-free publish did not prove examples were used.
Preserve both draft and published evidence, surface invalid/pending examples,
and do not bypass them or publish without explicit approval.
After agent creation, include a **manual draft-example repair checkpoint**:
the operator opens each example showing a validation error, makes a harmless
SQL edit (for example, appends a newline followed by the empty comment `--`),
saves and checks validation again. Do not change query semantics, append the
comment where it could comment out executable SQL, or mark validation successful
until the portal confirms it. This is the operator-reported workaround for this
flow, not an automatic API repair or a guaranteed fix for every validation error.
[Fewshots are not supported for Ontology sources](https://learn.microsoft.com/en-us/rest/api/fabric/dataagent/staging/create-datasource-fewshot);
attach SQL examples to the lakehouse source only.

Publication and Microsoft 365 Copilot listing are separate approvals/operations.
Preserve the following publishing instruction exactly:

> Note for Microsoft Copilot description_for_model: The output from Fabric data agent should be delivered as-is, without summarizing, rephrasing, or adding extra interpretation.

The published agent's MCP runtime is separate from draft testing; do not query
it as a draft substitute. Begin approved runtime checks with one capacity-health
question, then a small repeated sample at no more than two concurrent asks.
Do not run the historical healthcare deployment scripts or reuse their resource
identities, state or credentials.

On 2026-11-05 the approved finance draft was created with six gold tables,
32 selected columns, finance-specific agent/source instructions and six
examples. Every example executed successfully against the live SQL endpoint
and reconciled the applicable totals/rankings. Draft readback verified all
instructions, selected columns and saved queries; no other table was selected.
However, all six examples were `Invalid` in the agent validator with a SQL
server connection error. This reproduces the historical validation symptom;
it does not establish a general cause or imply the queries fail in SQL.
Portal re-saving/revalidation remains an operator checkpoint, not a guaranteed fix.

The current documented `FabricItem` ontology-datasource create was attempted
once and failed asynchronously with `OntologyAddAsDataSourceBlocked`, explicitly
instructing callers to use the ontologies surface instead. The operator must use
the documented **Sources -> Add sources -> Add an ontology** experience to
attach the finance ontology as context. See
[Ontology context guidance](https://learn.microsoft.com/en-us/fabric/data-science/data-agent-ontology-sources),
which recommends preview runtime and distinguishes ontology context from
source-native query execution. No private attachment route was guessed.
The finance ontology definition was independently confirmed unchanged.
At this checkpoint the draft was not published or runtime-tested, and the IQ gate remained incomplete.
Evidence and durable operation receipts are in the ignored `data-agent-v1`
finance work area; do not rerun creation to recover configuration.

Later on 2026-11-05, the operator approved correcting that draft's analytical
scope. The existing agent now selects **eight gold tables / 41 columns**,
including `dim_date` and `dim_period`; the original six business tables remain
selected. Agent/source instructions now describe dimension slicing, valid filter
paths, date roles and monthly-budget fanout safeguards. Four existing examples
were updated to join calendar/period dimensions and two examples were added:
month/portfolio/cost-category budget-versus-actual, and invoice-month/supplier
held-balance cohorts at the fixed snapshot. All eight queries executed in live
SQL; the two new breakdowns matched independent synthetic previews across 54 and
24 groups respectively. Draft readback verified selection, instructions and all
eight saved examples. No ontology, graph or source-data writes were made, no
source was added/removed and the agent was not published.

At the API update checkpoint the separate agent validator reported all eight
examples `Invalid` with the same SQL-server connection error. That was a readiness
blocker, not a successful runtime test. The update evidence and per-write receipts are preserved
in ignored `data-agent-v2`; the original package and immutable generated run were
not modified. Future generated guidance explicitly follows the analytical model
rather than deriving selections from the narrower ontology projection.

At 15:22 -06:00 on 2026-11-05, the operator reported switching the finance data
agent to **preview runtime**, publishing it and seeing **no errors in the example
queries**. Record this as owner attestation, separate from the earlier machine
readback: no subsequent API validation-status or published-definition readback
has yet been captured. This sequence supports checking preview runtime when the
agent validator fails despite valid direct SQL, but does not establish a general
root cause or universal fix. Do not silently switch runtime or auto-publish future
runs; retain the applicable approval checkpoints.

The reported publication does not establish ontology attachment, preservation of
the output-as-is publishing instruction, published answer accuracy or viewer/source
access. Those checks remain separate. No runtime questions have yet been executed
by the assistant, and the Fabric IQ gate remains incomplete.

At 15:34 -06:00, the operator supplied five published-agent answers before
ontology attachment, including a Q3 tabular export with its executed SQL. The
headline budget/actual/variance, six over-budget projects and fixed-snapshot
held-invoice count/balance matched the saved live SQL baselines. Local comparison
of the export verified all **54 month/portfolio/category groups and 162 monetary
cells exactly to the cent**, with no duplicate, missing or extra groups. Totals
reconciled to budget $27,198,660.93, actual $29,434,325.07 and variance
+$2,235,664.14. Query inspection confirmed unique calendar-date joins,
year-and-quarter filters, independent fact aggregation and a full outer join at
the requested grain. Its source trace identifies lakehouse SQL, not graph traversal.
The fifth response correctly refused unsupported supplier attribution for cost
variance and offered separately scoped invoice analytics.

This is a passing **five-question SQL-only published-answer sample**, based on
operator-supplied runtime outputs; only the third answer included an exported
query/result trace. It is not independent assistant invocation, repeated-sample
acceptance, second-viewer verification or evidence of ontology use. The first
answer omitted variance percentage, which the question did not explicitly require;
the returned monetary metrics and complete-month scope were correct. Local
reconciliation evidence is preserved in ignored
`data-agent-v2/published-sample-v1.json`. Attach ontology through the supported
portal flow, explicitly save/publish that change, then repeat a bounded sample
to assess semantic behavior without treating SQL responses as graph proof.
The full Fabric IQ gate remains incomplete.

At 15:37 -06:00, the operator confirmed the ontology was added manually to the
finance agent. Record attachment as owner attestation, not API readback. For the
selected accelerator flow, **ontology attachment to the data agent is a required
manual portal step**: **Sources -> Add sources -> Add an ontology**. Do not retry
the blocked datasource-create route or claim automatic attachment. The passing
five-question SQL-only sample above remains the pre-attachment baseline.
Publication of the newly attached configuration has not yet been confirmed, and
post-attachment answer accuracy/ontology use has not yet been assessed. The IQ
gate remains incomplete.

At 15:40 -06:00, the operator clarified the required example-query step after
agent creation: manually edit the errored draft examples with a safe change,
such as an empty SQL comment `--`, and save to trigger revalidation. This
clarification is recorded as operator guidance; it does not independently prove
the cause of the earlier connection errors or validation status of a future run.
Keep this checkpoint alongside preview-runtime selection and manual ontology
attachment, before approved publication and published-answer acceptance.

At 15:42 -06:00, the operator confirmed publication in preview runtime with the
added ontology and no SQL example-query errors. This supersedes the earlier
unconfirmed post-attachment publication status. The operator selected the
lakehouse-first, repair-examples, publish, manually-attach-ontology, publish-again
sequence above for future runs. This is owner attestation, not a fresh machine
readback or proof of a universal product dependency. Post-attachment answer
accuracy and actual ontology use remain unverified; the IQ gate remains incomplete.

### Approved finance vocabulary reference

On 2026-11-06, the post-ontology sample's first three answers passed:
headline amounts and 8.2% variance, all 54 monthly/portfolio/category groups
(162 exact-to-cent monetary cells), and 100 held invoices / $2,490,036.40 at
the fixed snapshot. The fourth answer correctly explained the invoice-mediated
Project/Supplier relationship and rejected hold-to-variance causation.

The operator-supplied Q4 diagnostics explicitly show `ontology.context.injected`
for one ontology / six selected entities and a successful two-hop
`trace.plan_ontology_traversal` with the correct project/invoice and
invoice/supplier predicates. `ontology.answer_path.traversal` chose
`single_engine_join`. This is evidence of ontology context injection and
relationship planning in that response, not materialized graph execution;
no SQL execution event is present for the conceptual Q4 answer.
The planner requested `Supplier.hold_reason`, although that property belongs
to Supplier Invoice. The returned path and final answer are correct, but
`found=true` must not be interpreted as validation of every requested field.
Eight fewshots loaded; that alone does not prove which examples were used.
The local trace assessment is preserved in ignored
`data-agent-v2/post-ontology-q4-trace-assessment.json`.
Questions 5 and 6 and the other outstanding acceptance checks remain pending.

At 10:06 -06:00 on 2026-11-06, the operator completed the remaining two
post-ontology answers and corrected the earlier numbering: the July cohort/
October snapshot answer was Q6. It correctly rejected historical July 31 AP
interpretation. Q5 correctly refused supplier attribution of cost variance,
explained invoice-path fanout/unsupported allocation, retained the matching
project/category/month grain, and offered separately scoped alternatives.
The **six-question post-ontology sample passes**. Each question has one
operator-supplied result; Q2 includes an exactly reconciled tabular/query export,
and Q4 includes diagnostic evidence of ontology context injection and relationship
planning, with the field-ownership caveat recorded above.
This does not establish repeatability, second-viewer/source access, exact
publishing-instruction preservation, materialized graph execution by the agent
or post-rename graph re-verification. The full Fabric IQ gate remains incomplete.
Per-question evidence is preserved in ignored `data-agent-v2`.

At 11:26 -06:00 on 2026-11-06, the operator accepted the existing published
six-question sample without an additional repeat and deferred second-viewer
verification out of the current demo scope. Do not request those checks again
for this run unless scope changes; do not represent these decisions as measured
repeatability or verified viewer/source access. The operator also confirmed
the graph relationship names changed correctly. Record this as owner
attestation of displayed names, not post-rename GQL count/property/aggregate
reconciliation. Exact output-as-is publishing-instruction preservation remains
unconfirmed. No CLI gate completion was performed or required checks bypassed.
The decision is preserved in ignored
`data-agent-v2/operator-readiness-scope-decision.json`; these scope choices are
specific to this run, not relaxed defaults for future presenter acceptance.

On 2026-11-06, the operator approved setting a fitting publishing description
with the exact output-as-is note at its end. Live definition inspection found
the prior publishing description empty, preview runtime enabled and all draft
configuration equal to published configuration, including ontology context and
eight examples. The supported `staging/publish` operation set the description;
response and independent definition readback confirmed its exact value and suffix.
All other exported JSON configuration parts remained unchanged. Preview runtime
and ontology attachment were preserved. No runtime questions or M365 listing
were performed. Durable intent, receipts and readback are in ignored
`publication-description-v1`. This resolves publishing-wording verification,
not any other unperformed gate check.

At 15:57 -06:00 on 2026-11-06, the operator reported publication to M365 Copilot
and supplied its six-question answers. All six answer-content checks pass.
Q2 was supplied in `agentanswer.docx`: local extraction/reconciliation verified
all 54 month/portfolio/category groups and 162 monetary cells exactly against
the saved live SQL baseline, without duplicate, missing or extra groups. Q1/Q3
totals match, Q4 preserves relationship and non-causality meaning, Q5 refuses
unsupported supplier cost attribution, and Q6 preserves fixed-snapshot semantics.
Its additional July cohort claim (27 invoices dated July 1-28) matches the
deterministic invoice preview. The Q4 practical implications are illustrative
possibilities, not new measured project findings.

This is operator-supplied M365 publication/runtime evidence plus local artifact
comparison, not independent assistant invocation or listing verification.
The exact output-as-is publishing suffix was previously verified, but these
outputs do not establish verbatim forwarding without paired upstream answers
and traces. No new graph execution, second-viewer check or CLI gate completion
is claimed. Evidence is preserved in ignored `data-agent-v2/m365-sample-v1.json`.

The live finance reference uses **Project, Supplier, Cost Category, Budget,
Cost Posting, and Supplier Invoice**, without physical `dim_`/`fact_` prefixes.
Its exact displayed relationship labels are:

| From | Displayed relationship label | To |
|---|---|---|
| Budget | Budget Applies To Project | Project |
| Budget | Budget Budgeted Under Cost Category | Cost Category |
| Cost Posting | Cost Posting Charged To Project | Project |
| Cost Posting | Cost Posting Classified Under Cost Category | Cost Category |
| Supplier Invoice | Supplier Invoice Billed For Project | Project |
| Supplier Invoice | Supplier Invoice Issued By Supplier | Supplier |

These six labels also became the ontology relationship names in an approved
dedicated API update on 2026-11-05, with all 11 referencing rules updated and
lineage/backing joins preserved. Readback confirmed the names and links, but
again removed the native identity annotations on all six table partitions.
The operator must repeat property reselection and graph materialization/refresh
as needed; the earlier runtime verification predates this rename and does not
establish post-rename graph acceptance.

These are scenario-specific examples, not fixed templates for other industries.
Propose business vocabulary for each approved scenario before deployment.
Preserve existing technical relationship names and lineage when changing display
labels; do not rebuild bindings merely to improve naming.

## Remaining boundaries

Industry independence of the schema is not the same as a fully automatic deployer.
IQ/data-agent/Rayfin/model/Planning phases still need specialist-assisted execution.
Each generated run documents manual API gaps and evidence gates. Semantic-model
date tables, ambiguity checks, planable grains and viewer permissions must be reviewed
for the approved scenario; any required new physical table changes the proposal.
No live Fabric or few-hour performance claim follows from offline generation.
