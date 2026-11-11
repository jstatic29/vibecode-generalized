# Sanitized finance reference

This is a portable explanation of the accepted synthetic finance walkthrough,
not an executable deployment package. It contains no live resource IDs,
credentials or private run scripts. It does not depend on access to the
builder's `.demo-runs` or conversation.

## Story and model

For fictional project-oriented IT/finance teams: compare approved budgets and
actual costs for complete months, then explore related held supplier invoices.
All records, exceptions and financial patterns are invented, not evidence of
customer performance or confirmed customer source systems.

The reference used 16 Delta tables across staging, business and governance
layers, with 14,701 physical rows including copies. These are reference results,
not minimums or caps for another industry. The agent selected eight analytical
tables/41 columns; the ontology projected six entities and 14 descriptive rules.

| Entity | Demonstration purpose |
|---|---|
| Project | Common project context |
| Cost Category | Conformed budget/actual classification |
| Budget | Project/category/month approved amounts |
| Cost Posting | Actual postings aggregated independently from budgets |
| Supplier Invoice | Held-invoice exceptions at a fixed balance snapshot |
| Supplier | Invoice relationship context, not supplier attribution of costs |

Supporting calendar/period dimensions remain relevant to the agent even though
they are not ontology entities. Relationships include actual physical joins and
business-to-physical mappings, not just logical relationship labels.

## Accepted reference results

The original run's SQL independently reconciled table counts, keys, allocations
and financial metrics. The latest bounded graph check on 2026-11-10 reconciled
counts and a two-edge traversal to the saved SQL-verified baseline.
These were direct GQL calls to the materialized graph's beta `executeQuery`
endpoint, not data-agent or SQL endpoint calls. The portable
[graph query handoff](graph-query-handoff.md) captures the actual request shape,
reference traversal, continuation handling and evidence limits without live IDs
or access to the private execution script.

| Figure | Reference value |
|---|---:|
| Q3 2026 approved budget | USD 27,198,660.93 |
| Q3 2026 actual cost | USD 29,434,325.07 |
| Q3 2026 actual-minus-budget variance | USD 2,235,664.14 |
| Graph nodes / directed edges | 3,602 / 7,128 |
| Held-invoice traversal project/supplier groups | 82 |
| Held invoices / open balance | 100 / USD 2,490,036.40 |
| Traversal key mismatches | 0 |

Amounts are stored as integer cents. Invoice balances are fixed as of
2026-10-31; invoice-date filters select cohorts, not historical balances.
Holds do not establish the cause of budget variance. Never add invoice
balances to actual costs or invent supplier-level cost allocation.

The published agent's SQL-only and six post-ontology samples were accepted.
Operator-supplied M365 samples also passed content reconciliation; one
breakdown covered 54 groups and 162 monetary cells exactly. Ontology context
and relationship planning were observed in a supplied agent trace. This is
not proof that the agent executed the materialized graph.

## Lessons a new presenter should carry forward

Use a reviewed generation-2 TMDL definition through the dedicated public
`/ontologies` routes. Finalize friendly entity/relationship/rule names before
the last native binding repair. In the reference, definition writes stripped
native partition identity annotations; the operator reselected source columns
in each entity's Bind data -> Properties and verified graph eligibility.
This is an observed workaround, not a guaranteed platform requirement.

Materialize only with approval and verify actual graph properties, keys,
directions, totals and a real multi-edge traversal against SQL. A successful
refresh, a plausible definition or an SQL join does not establish graph parity.

Select both agent parent tables and columns explicitly. Use approved business
and calendar dimensions, independently validated examples and separate
draft/published evidence. The selected sequence was Lakehouse-first agent,
manual repair of errored examples when necessary, approved Preview publication,
SQL-only sample, manual ontology attachment, approved second publication and
bounded post-attachment sample.

Keep the exact output-as-is publishing suffix from the companion. Do not reuse
the blocked ontology datasource-create route or infer M365 access from normal
publication. The runtime/publication visibility must be checked under the
intended account.

## Acceptance boundary

The finance Fabric IQ gate was closed as an operator attestation backed by
machine and owner evidence. Repeatability was not independently measured;
second-viewer checks were explicitly deferred. M365 verbatim forwarding was
not established. A first graph attempt timed out locally; its remote outcome
remained unknown, while a separately approved retry succeeded.

Semantic model and Fabric app remain on hold; Planning was disabled. This is
not a completed full-stack or second-presenter reference.

`examples\project-finance.json` illustrates reusable recipe patterns but is
not the original immutable run, a preapproved deployment or a guarantee of
identical results after any configuration change. For a new customer, begin
with research and an approved model. Compute that run's own expected outputs
and independently validate them; never copy these reference values as evidence.
