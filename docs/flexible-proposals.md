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

Supported types are `string`, `int64`, `boolean` and `date`. No arbitrary Python,
SQL or executable strings run from proposals. No silent defaults for unsupported
distributions. Integer values and conservative sum/average bounds must fit the
exact JavaScript-safe range (absolute value at most `2^53 - 1`) so app and data
results agree. More sophisticated correlations (such as payment date >= opened date,
seasonality, bottleneck distributions or balance equations) need a tested recipe
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

SQL views and DAX measure contracts use these same declarations. Aggregate each
fact independently; cross-fact comparisons and additional graph walks need explicit
grain-aware design, not an automatic join. V2 currently emits topology GQL plus the
schema contract, not invented customer-specific graph traversals.

## Scope without an arbitrary table count

There is **no maximum or required number of tables** in the version-2 contract.
Physical Delta count is `len(proposal.tables) + 2` governance tables. Each bronze
table also has a raw JSON extract in Files, which is not a Delta table.

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

## Remaining boundaries

Industry independence of the schema is not the same as a fully automatic deployer.
IQ/data-agent/Rayfin/model/Planning phases still need specialist-assisted execution.
Each generated run documents manual API gaps and evidence gates. Semantic-model
date tables, ambiguity checks, planable grains and viewer permissions must be reviewed
for the approved scenario; any required new physical table changes the proposal.
No live Fabric or few-hour performance claim follows from offline generation.
