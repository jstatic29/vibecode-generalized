# Discovery and data

## Research and approval

Collect the website, audience roles/decisions and high-level source descriptions.
Only ask for missing information; the presenter need not choose an industry
template or write a schema. Research public pages in Chat, cite URLs and distinguish
public facts, operator-provided context and synthetic assumptions. An inaccessible
site is a disclosed gap, not permission to invent evidence. Do not ingest customer
records or imply an embedded crawler/LLM exists in the accelerator.

Propose 2-3 use cases with audience relevance, decision, source mapping, invented
supporting context and an insight-to-action story. Recommend a deterministic model:
table purpose/grain/key, lineage, relationships, distributions, date window,
physical row budget, metrics/units and optional features. No industry allowlist
or arbitrary table quota. Ask the operator to select/revise and approve assumptions.

Use the tested declarative recipes in `docs/flexible-proposals.md`. Validate
unsupported distributions/relationships through an explicit tested extension;
never silently approximate them. Version-1 healthcare/manufacturing examples are
opt-in regression fixtures, not a default model.

## Choose the data path

Offer synthetic (default) or existing-lakehouse data before generation. Synthetic
uses the recipes and notebook below; existing mode does not generate replacements
or require column schemas/generator code from the presenter. Public research and
use-case selection still precede generation. Record notes/citations and industry
confirmation in intake; final story/design follow assessment.

### Existing-lakehouse path

Use `init --data-mode existing-lakehouse`. Copilot helps fill
`existing_data.tables` with individual shortcut aliases and purposes,
`scope.max_query_seconds`, `max_result_rows` and `baseline_max_age_hours`, plus
approved workspace/new lakehouse/demo_ schema. Keep `proposal: null`. `plan`
returns discovery/assessment guidance; `generate` freezes a distinct work package
with no synthetic notebook, previews or expected.json.

1. Approve lakehouse-setup, then run setup-lakehouse. Only a NEW dedicated,
   schema-enabled demo lakehouse is created; save/reuse its exact identity.
2. STOP for the operator to create individual internal OneLake table shortcuts
   under Tables in the approved demo_ schema of that CREATED lakehouse. No
   whole-schema shortcuts, direct source attachment or automatic copies.
3. Approve shortcuts, run inspect-shortcuts and review the exact paginated source
   target inventory. Fill the evidence template with its inventory_sha256 and
   matching targets plus owner permission/SQL-visibility evidence; complete shortcuts.
4. Approve data-readiness BEFORE metadata or aggregate assessment. Load current
   OneLake and SQL specialist guidance. Discover columns/types, grains, keys and
   duplicates/nulls, relationships/orphans, date coverage/roles, units and sensitivity.
   Use the two-package assessment flow below; agree scan/partition/time-window
   budgets and apply timeout and result limits.
5. Propose only scenarios supported by actual data; ask the owner to approve
   metrics/mappings. Missing tables or measures are gaps, not invented facts.
   Save timestamped aggregate baselines with query references, filter/grain,
   source version/drift limitations and disclosure approval. Complete data-readiness
   using its evidence template, then story/design, then common downstream gates.

**Shortcuts are not a read-only security boundary.** Verify effective source
permissions for operator, services/connections and delegated SQL/Direct Lake item
owners; do not assume viewer identity passthrough. If they can mutate targets,
stop and obtain read-only execution identities; never test with writes. Inventory
readback proves paths/identities only, not ACLs or SQL visibility. No SELECT *,
raw previews/exports, source DDL/DML, description edits through shortcuts,
optimize/vacuum or automatic cleanup. Sensitive aggregates still need approval.

#### Two-package assessment flow

Use this flow for both Lakehouse- and Warehouse-backed table shortcuts. It is
Copilot/operator orchestration, not a new automatic profiler or notebook adapter.
Do not repeat the development walkthrough's small approval round for every
key, period or relationship query.

1. **Metadata discovery package.** After shortcuts completion and data-readiness
   approval, present one exact metadata-only plan for the approved aliases:
   column names/types/nullability and supported structural metadata, with catalog
   scope, timeout, result limits and disclosure boundaries. Obtain exact-plan
   approval, execute automatically through the approved route and retain receipts.
   No source records, business-value aggregates or inferred key guarantees.
2. **Scenario-focused assessment package.** From observed metadata, propose the
   minimum relevant facts/dimensions and explicitly exclude unrelated tables.
   Present one reviewed package covering candidate grains/keys, null/duplicate
   and relationship/orphan checks, date roles/coverage, period baselines, units,
   negative/zero values, missing-value policy and metric definitions. Include the
   exact queries, per-table/time-window/partition scan scope, timeout/result limits,
   disclosure rules, execution identity and unsupported checks. Obtain exact-plan
   approval before executing the package automatically. Full-history scans need
   explicit justification/approval; result caps alone do not bound scanned data.

Within an approved package, do not request permission for every query. Stop for
failed checks, identity/target drift, timeout, unsupported operations or genuinely
new scope/disclosure/cost decisions. A changed plan requires fresh approval; never
use a broad "proceed" to approve unreviewed queries. Do not retry failed queries
automatically. If discovery reveals a new necessary check, explain and approve
the plan delta rather than rerunning completed checks or restarting the intake.

Finish with **one consolidated readiness report**: selected/excluded tables,
passed/failed/unknown checks, exact timestamped baselines and query references,
metric/date/unit definitions, sensitivity, limitations, freshness/drift policy
and remaining owner decisions. Explicitly excluded tables are not quality-certified;
record their exclusion in every table entry required by the evidence template.
Review observed findings and obtain acceptance before completing data-readiness.
The two packages do not merge shortcut, readiness, story/design or downstream
write/materialization/publication approvals.

#### SQL default; notebooks by exception

Prefer the destination Lakehouse SQL endpoint for scenario-focused relational
checks and metric baselines, including Warehouse-backed shortcuts. It verifies
the SQL experience relevant to the data agent. Use the specialist MCP by default,
or the explicitly opted-in timeout-controlled runner below when appropriate.
Check supported query kinds before approval; extend/test unsupported checks or
use a supported specialist route, never silently skip them.

Consider a submitted Spark notebook only for a concrete need such as
Delta-specific metadata, distributed assessment or complex checks that SQL cannot
efficiently support. Explain startup/capacity overhead and why it improves this
assessment; obtain approval for reviewed code and scan/disclosure/compute scope.
Load current Spark guidance, verify all runtime/delegated identities remain
source-read-only, and persist submitted job IDs and results. No long-running
interactive Livy, unapproved writes, persisted caches or copies of source records.
A local timeout is not remote cancellation; resume the saved job, do not resubmit.
Notebook execution is an optional specialist-assisted route, not an implemented
accelerator assessment adapter.

If both engines are used, share metric definitions, filters, date roles and
disclosure boundaries. Spark results do not prove SQL synchronization, SQL security
or agent access; retain destination SQL acceptance checks. Warehouse-source live
validation remains separate from Lakehouse-source evidence.

#### Timeout-controlled execution option

The installed SQL specialist's MCP is primary. If it cannot enforce the run's
timeout, ask for explicit opt-in to this repository's optional ODBC runner;
do not silently switch transports, relax limits or edit an immutable run.
This project-owned route needs ODBC Driver 18 and optional `.[sql]`, not new
Fabric resources. Keep sign-in interactive and source permissions read-only.

After shortcuts completion, `sql-preflight --expected-login <approved-UPN>`
verifies only SQL login/database with the configured timeout; no source queries.
Prepare a structured plan outside generated artifacts, then `sql-plan --plan`
to preview it. Obtain data-readiness approval plus exact-plan/scan/disclosure
approval before `approve-sql-plan --plan --note` and `run-sql-plan --plan`.
All commands also take `--run-dir`. See README's optional runner section for
the plan schema. Plan approvals are hash-bound; changes require fresh approval.
Reauthentication must not silently change the expected identity.

Only allowlisted column metadata, single-table aggregates and fixed count-only
relationship checks are supported, with parameterized filters and quoted/live-checked
columns. Relationship plans identify child/parent columns and an approved parent
table; matching live types are required. EXISTS avoids parent-duplicate fanout;
null/orphan and parent distinct counts are separate. No arbitrary SQL, raw rows,
grouping, general joins or automatic model inference. Unsupported business-grain
or fiscal checks remain specialist work; disclose gaps.
The runner rechecks shortcut target drift, enforces per-statement ODBC timeout
and rejects result overflow. Scan budgets are owner-reviewed, not a byte quota.
Timeout requests cancellation but does not prove remote termination; inspect
saved requests, never blindly retry. No automatic readiness gate completion.
Distinguish local/mock coverage, live identity preflight, actual live results
and timeout-cancellation verification; none substitutes for the others.

Source model/metrics live in accepted `evidence/data-readiness.json`, shared by
ontology, graph, agent, model and app. Read downstream-handoff.md; do not call
deploy-data. Curated local outputs require separate approval outside shortcut
paths. Model Import, graph materialization and publication can copy/expose data;
source read-only does not authorize them. App/Planning writes remain separate.

CLI enforces freshness at readiness acceptance, not continuously. Recheck schema,
permissions, shortcut targets and baseline age/drift before publication/rehearsal;
retain old evidence and record new reconciliations outside immutable artifacts.
One live Lakehouse run verified destination setup, exact shortcut inventory and
approved column-metadata execution through the opt-in ODBC runner. Configured
timeout and identity checks passed, but remote timeout cancellation, aggregate
readiness and Warehouse-source execution remain unverified. Product references:
[shortcuts/security](https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts)
and [inventory API](https://learn.microsoft.com/en-us/rest/api/fabric/core/onelake-shortcuts/list-shortcuts).

## Synthetic local preparation

Run from the repository root; no dependency installation is needed:

```powershell
python -m demo_accelerator init --output intake.json
python -m demo_accelerator plan intake.json
python -m demo_accelerator generate intake.json --run-dir .demo-runs\customer-001
python -m demo_accelerator status --run-dir .demo-runs\customer-001
```

These are command shapes, not authorization to create a particular run or reuse
the example paths. Read generated `OPERATOR.md`. Inspect scenario, expected
answers, proposed SQL and notebook before approval. Generation is local only.
Keep story/design approval and evidence distinct. Use the existing CLI's
`approve`, `evidence-template` and `complete` commands per README; do not bypass
their prerequisite checks. `complete` records owner attestation, not deployment.

## Approved live data phase

Load current `spark-cli` and its required references. Review raw -> bronze ->
silver -> gold and supporting/governance rows against the approved workload.
Use durable submitted notebook jobs, not interactive Livy for long-running work.
With data-build approved, use repository `preflight` and `deploy-data` commands
as documented. Persist create receipts and operation/job IDs immediately.

Resume saved jobs after local timeout; do not submit duplicates. Respect capacity
throttling. On ambiguous writes inspect state/readback; never erase locks or
state to force a retry. A partially populated schema is not permission to reset;
investigate and obtain approval for a new schema/run if needed.

## Independent acceptance

Notebook success is necessary but insufficient. Discover the actual SQL schema
and endpoint through supported tools; verify synchronization and reconcile:

- Exact table/physical-row counts, unique keys, references and expected grains.
- Full and selected-period totals, rankings, grouped measures and derived ratios.
- Calendar continuity, completeness labels and alternate date roles.
- Allocation/snapshot invariants declared by the scenario.

Aggregate facts independently at matching grain before joining. Recompute ratios
from summed components, keep missing operands/zero denominators null and round
once. Monthly budget must not multiply through daily joins or be compared with
partial-month actuals. Invoice cohorts are not historical snapshot balances;
supplier invoice filters do not invent supplier attribution for unrelated costs.

Save actual query outputs, time, target identity, expected/observed results and
limitations separately from operator confirmations. Mocked tests and local
generation are not Fabric verification.
