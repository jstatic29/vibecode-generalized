# Fabric customer demo accelerator

A guided, checkpointed starting point for customer-specific Microsoft Fabric IQ
demos: **see a problem -> explore relationships -> ask a grounded question -> record a response**.
Derived from the lessons of a successful synthetic healthcare demo, without its
customer data, workspace identifiers, deployment state or credentials.

## Customer-led, not industry-template-led

Start with a **customer website, audience and high-level existing-source descriptions**.
Copilot researches the context and suggests use cases and a synthetic data design,
or an opt-in, read-only assessment of existing lakehouse tables through shortcuts.
The presenter selects/revises the recommendation and approves the story and schema
before synthetic Fabric deployment. Existing mode first obtains separate approval
for its dedicated destination and read-only assessment.

There is **no industry allowlist and no fixed table count** in the default intake.
An approved model can have 10, 25 or another justified number of Delta tables.
Scope guardrails bound physical rows, staging copies and reviewed complexity, not
an arbitrary quota. Healthcare/manufacturing scenarios remain opt-in regression
examples, not the only supported industries.

Read [Flexible proposals](docs/flexible-proposals.md) for the discovery workflow,
supported declarative recipes and approval contract.

## Companion skill

The repository-local
[fabric-demo-companion](.github/skills/fabric-demo-companion/SKILL.md) skill
captures the guided workflow and lessons learned, alongside the installed Fabric
specialist skills. Ask Copilot to "use fabric-demo-companion to build or resume
this demo." It provides phase routing, manual checkpoints, evidence/recovery
guidance and an operational evidence template; it does not install dependencies
or add deployment adapters. See
[GitHub's skill discovery documentation](https://docs.github.com/en/copilot/concepts/customizations/agent-skills)
for supported hosts. Host discovery/reload may be needed after adding a skill;
the file can also be read directly. No personal/global installation is performed.

Version 0.2.0 preserves validated practices separately from observed workarounds
and owner attestations. It includes the lakehouse-first, two-publication agent
flow and the current post-ontology acceptance handoff; live IDs remain in private
run evidence, not in the portable skill.

## Status: working foundation, not a turnkey end-to-end deployer

| Capability | Current implementation |
|---|---|
| Customer brief without preselected industry/schema | Implemented |
| Website research and use-case recommendations | Copilot/operator-assisted in Chat; no embedded LLM/crawler |
| Flexible proposed schema, grains, sources, references and metrics | Implemented, validated declarative recipes |
| Deterministic local previews and exact expected answers | Implemented |
| Existing lakehouse data through manual table shortcuts | Gated setup/inventory and opt-in timeout-controlled SQL assessment; full live assessment/downstream acceptance pending |
| Raw JSON -> bronze -> silver -> gold notebook | Generated from the proposal; one synthetic project-finance data build live-validated |
| Durable notebook deployment/job monitoring | One live notebook build completed, including recovery after an async create response; mocked recovery checks also retained |
| Approval gates, artifact integrity and evidence | Implemented |
| Ontology and graph | Dynamic contracts/runbook; one specialist-assisted six-entity finance projection live-verified after native binding repair |
| Data agent and Rayfin app | Dynamic contracts/runbook; specialist-assisted authoring/deployment, live reference pending |
| Optional semantic model and Fabric Planning | Dynamic contracts and gates; specialist-assisted implementation |
| Few-hour runtime target | Design goal, not benchmarked |

Generated contracts are **not deployed features**. A full accelerator release still
needs concrete specialist deployment adapters and live reference/rehearsal runs.
The project-finance data-stage reference reconciled all 16 Delta table counts,
headline totals and selected-quarter project rankings through the SQL endpoint,
with additional allocation, invoice, calendar and reference checks. Its focused
six-entity ontology/graph also reconciled node/edge counts, sampled properties,
key uniqueness, financial totals, Q3 project aggregates and an actual two-edge
invoice traversal against SQL. Native portal property reselection was required
to repair lakehouse bindings; exported ontology key types and materialized graph
key types differ, as documented in [Flexible proposals](docs/flexible-proposals.md).
The selected ontology flow uses the dedicated `/ontologies` API, not Ontology
Agent. After the final API write, the operator opens each entity's **Bind data ->
Properties**, reselects the correct **Source column** from its already bound
lakehouse table, saves and verifies all mappings and graph eligibility.
This is not live verification of other scenarios, DAX, agents or apps, nor a
completed full-stack reference or second-presenter run.
New industries do not require new Python code when their schemas fit the supported
recipes. Richer correlations or transformations do require tested extensions; the
engine fails explicitly rather than substituting a healthcare pattern.

## Quick start (PowerShell)

Python 3.11+ is sufficient for local preparation, with no third-party runtime packages.
Run commands from this repository's root. Optional installation:
`python -m pip install -e .` exposes `fabric-demo`.

```powershell
python -m demo_accelerator init --output intake.json
# Edit customer URL, audience, source descriptions, optional features and scope.
python -m demo_accelerator plan intake.json
```

With `proposal: null`, `plan` returns Copilot's **research and recommendation brief**:
read the site, cite findings, suggest 2-3 audience-relevant use cases, recommend a
synthetic schema and ask the user to select/approve. A website is context, not a
source of customer records or proof of internal systems.

After selection, put the proposed design in intake.proposal, record research
citations/notes and confirm industry with the presenter. Copilot prepares this
configuration; the presenter need not author generator code.

```powershell
python -m demo_accelerator plan intake.json
python -m demo_accelerator generate intake.json --run-dir .demo-runs\customer-001
python -m demo_accelerator status --run-dir .demo-runs\customer-001
```

`plan` now reports the actual schema size and physical-row budget. `generate`
creates local previews and immutable work packages, never Fabric resources.
`init` never overwrites a file; `generate` requires a new run directory. Changing
an artifact invalidates the run: change intake and obtain new approvals.

For a **fictional worked example** with claims, policies, adjuster teams and payments:

```powershell
python -m demo_accelerator plan examples\insurance-claims.json
python -m demo_accelerator generate examples\insurance-claims.json --run-dir .demo-runs\claims-example
```

This example has 10 Delta tables because of its proposed design, not a 10-table
rule. It is not researched or approved for a customer. It remains at the story gate.

`examples\project-finance.json` is another fictional worked example: a contiguous
calendar, project/category/month budgets, exactly allocated actual postings and
consistent invoice balances. It includes grain-aware cost variance and ratios,
an optional semantic model and app, but no Planning. Its 16-table design has
14,701 physical rows including raw/staging copies and governance. It makes no
claims about a customer's finance systems or performance.

Legacy fixture generation remains available explicitly:

```powershell
python -m demo_accelerator init --scenario healthcare-access --output legacy-intake.json
```

## Inputs and optional features

| Input | Purpose |
|---|---|
| `customer` | Name and public HTTPS website |
| `audience` | Roles, priorities and decisions to demonstrate |
| `sources` | High-level existing systems/data, no credentials or real records |
| `scope` | Fixed date window/seed, per-table rows and total physical-row budget |
| `features` | App, semantic model and Planning options |
| `deployment` | Approved existing workspace, lakehouse and fresh `demo_` schema |
| `research` | Public citations, inference caveats and industry confirmation |
| `proposal` | Selected use case, rationale, decision, assumptions, tables and metrics |
| `data_mode` | Optional version-2 choice: `synthetic` (default) or `existing-lakehouse` |
| `existing_data` | Existing mode only: individual shortcut aliases and business purposes |

### Existing-data option

Synthetic remains the default; old intake/run hashes are unchanged. Existing mode
uses a **new accelerator-created demo lakehouse** in an approved existing workspace.
The operator manually creates individual **OneLake table shortcuts** to selected
existing tables in that destination, then Copilot assesses only approved metadata
and bounded aggregates. It never generates synthetic substitutes or writes to sources.

**Shortcuts alone do not ensure read-only access.** Source owners must verify
effective read-only permissions for every execution identity, including delegated
SQL/Direct Lake item owners. Writes through a shortcut can affect its target.
If source read-only access cannot be established, stop; do not try a test write.
See [OneLake shortcuts and security](https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts).

```powershell
python -m demo_accelerator init --data-mode existing-lakehouse --output existing-intake.json
# Copilot researches/gets use-case selection and fills research, target and table aliases.
python -m demo_accelerator plan existing-intake.json
python -m demo_accelerator generate existing-intake.json --run-dir .demo-runs\existing-001
python -m demo_accelerator approve --run-dir .demo-runs\existing-001 --gate lakehouse-setup --note "Approved creation of this new dedicated demo lakehouse"
python -m demo_accelerator setup-lakehouse --run-dir .demo-runs\existing-001
# STOP: operator creates individual table shortcuts in the returned lakehouse's demo_ schema.
python -m demo_accelerator approve --run-dir .demo-runs\existing-001 --gate shortcuts --note "Manual shortcuts ready for inventory and source-permission review"
python -m demo_accelerator inspect-shortcuts --run-dir .demo-runs\existing-001
python -m demo_accelerator evidence-template --run-dir .demo-runs\existing-001 --gate shortcuts
```

In the new intake, keep `proposal: null` and fill, for example:

```json
"existing_data": {
  "tables": [
    {"name": "orders", "purpose": "Order fulfillment measures"},
    {"name": "customers", "purpose": "Approved customer segment relationships"}
  ]
},
"scope": {
  "max_query_seconds": 60,
  "max_result_rows": 100,
  "baseline_max_age_hours": 24
}
```

These are alias/purpose examples, not customer data or an imposed schema. Copilot
helps select the tables; the presenter need not define generators or column schemas.
`inspect-shortcuts` reads the paginated inventory, rejects missing/extra aliases,
unsupported/external targets and wrong destination paths, and persists the actual
OneLake target identities. Only individual internal OneLake table shortcuts are
supported; whole-schema shortcuts are not part of this flow.

Save the evidence template outside the run, fill the exact targets and
`inventory_sha256` from inventory readback plus owner permission/SQL-visibility
evidence, then `complete --gate shortcuts --evidence <file>`. Inventory readback
does **not** prove effective ACLs; permission verification remains an explicit
owner attestation, without a write probe.

Next approve `data-readiness` **before** reads; use its evidence template to record
actual columns/types, grains, key/null/duplicate/orphan findings, relationships,
date coverage/roles, units, sensitivity, metric mappings and timestamped aggregate
baselines. Agree scan/partition/time-window budgets; result limits alone do not
bound scanned data. No raw record previews/exports, `SELECT *`, source maintenance,
automatic copies, metadata edits through shortcuts or automatic cleanup.
The CLI checks baseline age on readiness completion; ongoing freshness, source
drift and permission checks before publication/rehearsal are specialist checkpoints,
not an automatic monitor. Baselines are observations, not synthetic expected values.

#### Optional timeout-controlled SQL runner

The specialist SQL MCP remains the default execution surface. When it cannot
enforce the approved timeout, the operator can explicitly opt into this toolkit's
ODBC runner instead; this is not an automatic fallback or a change to the installed
specialist skill. It preserves existing run hashes and completed gates. Requires
Microsoft ODBC Driver 18 for SQL Server and the optional `.[sql]` Python extra
(`python -m pip install -e ".[sql]"` only if missing). Normal local generation/tests
still need no dependencies. Authentication uses the current Azure CLI profile;
set `AZURE_CONFIG_DIR` to the approved isolated profile before execution.
Interactive sign-in is never bypassed.

```powershell
# After shortcuts completion: identity-only, no source metadata/records/aggregates.
python -m demo_accelerator sql-preflight --run-dir .demo-runs\existing-001 --expected-login reader@example.com
# Copilot prepares an assessment plan OUTSIDE the immutable generated artifacts.
python -m demo_accelerator sql-plan --run-dir .demo-runs\existing-001 --plan assessment-plan.json
# STOP for operator approval of both the gate and this exact plan.
python -m demo_accelerator approve --run-dir .demo-runs\existing-001 --gate data-readiness --note "Approved reviewed metadata/aggregate scope"
python -m demo_accelerator approve-sql-plan --run-dir .demo-runs\existing-001 --plan assessment-plan.json --note "Approved exact queries, scan budget and disclosure"
python -m demo_accelerator run-sql-plan --run-dir .demo-runs\existing-001 --plan assessment-plan.json
```

`sql-plan` validates/previews locally; it does not approve or execute anything.
The JSON plan has `version: 1`, the run's `config_hash`, accepted
`inventory_sha256`, `expected_login` and a nonempty `queries` array. Each query has
an `id`, approved `table` alias, `kind`, owner-reviewed `scan_budget` and `disclosure`.
`kind: "columns"` returns only catalog column metadata. `kind: "aggregate"` uses
`measures`, for example `{"name":"total","function":"sum","column":"Total Amount"}`,
and optional `filters`, for example
`{"column":"Invoice Date Key","op":">=","value":"2016-01-01"}`.
Supported functions are `count_rows` (omit column), `count_distinct`, `null_count`,
`sum`, `min`, `max`; comparisons are `=`, `<>`, `>`, `>=`, `<`, `<=`, ANDed together.
All filters use bound parameters; identifiers are quoted and columns checked
against live metadata. SUM is numeric-only; MIN/MAX are numeric/date/time-only.

`kind: "relationship"` accepts a `relationship` object with child `column`,
approved `parent_table` and `parent_column`. It returns only full-table child/
parent counts, null-key counts, nonnull orphan count and distinct parent-key
count using fixed EXISTS checks. Both columns are live-checked for matching
SQL types. Duplicate parents do not multiply children. No measures or filters
are accepted for this kind; include both tables' scan costs in plan approval.

There is **no arbitrary SQL, raw-row selection, grouping, general joins, expressions,
DDL/DML or automatic profiling**. Unsupported assessments (including business-grain
and fiscal semantic checks) remain specialist work; this runner cannot by itself complete
data-readiness. Scan budgets are reviewed scope, not an engine-enforced byte/row
scan quota; filters and result caps do not guarantee partition pruning.

The runner validates the live endpoint host/destination, rechecks shortcut target
drift, verifies login/database before each query, applies the run's ODBC command
timeout per statement and rejects result overflow instead of silently truncating.
Approval is bound to the exact plan hash and retained as integrity-checked evidence.
It persists request intent/results/failures separately, never credentials. Decimal
results are exact strings, not binary floats. Source ACLs/delegation still require
owner verification. Timeouts request driver cancellation, **not proof of remote
termination**; no automatic retry, session kill or automatic gate completion.

Live observation on 2026-11-09: the isolated read-only assessment identity
connected successfully with a configured 60-second ODBC command timeout; an
approved metadata-only plan automatically returned columns/types/nullability
for all 14 shortcuts in one Lakehouse walkthrough. This is not a fixed table
count. It verifies connection and metadata execution, not aggregate baselines,
remote timeout cancellation, Warehouse-source behavior or completed readiness.
SQL MCP authentication was independent of the Azure CLI profile; verify the
actual SQL session identity rather than assuming either sign-in switches both.

The existing-data gate order is:

**lakehouse-setup -> shortcuts -> data-readiness -> story -> design -> fabric-iq ->
optional semantic-model -> optional planning -> optional app -> rehearsal**.

Read `OPERATOR.md`, `source-contract.json`, `assessment-metadata.sql` and
`downstream-handoff.md`. After readiness, the approved assessment in
`evidence/data-readiness.json` is the shared analytical model for specialist
ontology/agent/model/app work; no synthetic notebook or `expected.json` is emitted.
`deploy-data` is prohibited for this mode. Any curated output needs separate
approval outside shortcut paths; Planning/app actions use separate owned destinations.
Graph materialization, Import models and publication can copy/expose existing data
even without source mutation and require sensitivity/disclosure approval.

Lakehouse creation and shortcut inventory are CLI adapters; assessment and downstream
authoring remain specialist-assisted. This path has local/mocked coverage, **not a
live existing-data reference run**. Resume `setup-lakehouse` after a timeout; it
retains create intent/operation/identity and never blindly resubmits an ambiguous create.
An existing lakehouse without this run's creation intent is rejected.

To include Planning:

```json
"features": {
  "app": true,
  "semantic_model": true,
  "planning": true
}
```

Planning requires the model. Compatibility, planable grain, credentials, permissions
and writeback are separate checks. Direct Lake support is not assumed; any Import
fallback requires approval.

## Stop gates and evidence

**story -> design -> data-build -> fabric-iq -> optional semantic-model ->
optional planning -> optional app -> rehearsal**

Later gates cannot be approved before prerequisites complete. Approval permits a
phase; it does not assert success.

```powershell
python -m demo_accelerator approve --run-dir .demo-runs\customer-001 --gate story --note "Reviewed recommendations, audience fit, citations and synthetic assumptions"
python -m demo_accelerator evidence-template --run-dir .demo-runs\customer-001 --gate story
```

Save that JSON **outside the immutable run**, fill checks only after doing them,
and record notes and references:

```powershell
python -m demo_accelerator complete --run-dir .demo-runs\customer-001 --gate story --evidence story-evidence.json
```

`complete` is an **operator attestation**, not automated verification or a deployment.
Data-build can complete only through its successful durable notebook job.
In existing mode, lakehouse-setup completes only through `setup-lakehouse`;
shortcuts and data-readiness require their specific inventory and assessment evidence.
Review evidence kinds as well as `status.demo_ready`.

Runs are ignored by Git and can hold operational IDs and notes. Never put tokens,
credentials, real records or personal data in intake, evidence or generated bundles.
Git ignoring is not a security boundary.

## Approved data deployment and resume

Requires Azure CLI, `az login` to the intended tenant, an accessible Active Fabric
capacity and workspace permissions. Public-cloud Fabric only. Feature availability
for IQ/apps/Planning remains a separate operator check.

```powershell
python -m demo_accelerator preflight --run-dir .demo-runs\customer-001
# Complete story/design; review generated OPERATOR.md, schema and notebook.
python -m demo_accelerator approve --run-dir .demo-runs\customer-001 --gate data-build --note "Approved target, fresh schema, proposed workload and notebook job"
python -m demo_accelerator deploy-data --run-dir .demo-runs\customer-001 --timeout 1800
```

This may create a schema-enabled lakehouse and uniquely named notebook, then submit
a `RunNotebook` job. **No interactive Livy execution.** Existing lakehouses must be
schema-enabled. Populated schemas fail; the notebook never resets or overwrites one.
The generated notebook validates exact rows, keys, references, metrics and periods.

Local timeout is not remote cancellation. Repeat the same `deploy-data` command to
monitor saved operation/job IDs. Ambiguous writes and partial failures stop for
investigation, not POST retries or resets. Do not erase state to force a new run.
A failed partially written build normally needs a fresh approved schema/run.
No cleanup or deletion is automated.

One process may mutate a run at a time. If a crash leaves `.run.lock`, inspect its
PID and operation state before removing that specific lock file.

## Remaining phases

Each run's `OPERATOR.md` guides the specialist-assisted stages:

- Verify SQL endpoint synchronization, rows and metric reconciliation.
- Author generation-2 ontology from the actual proposed entities/keys/relationships;
  guide portal-only materialization/attachment as needed. Verify properties and
  edges through GQL, not refresh status alone.
- Configure and publish the data agent from the same metric rules, source grains
  and terminology. Select relevant facts and supporting business/calendar/period
  dimensions from the approved analytical model, not just ontology entities;
  include dimension-based slicing/grouping examples. Test draft/published
  separately and use bounded question samples.
- If selected, build/reconcile the semantic model; inspect date dimensions and
  relationship ambiguity. For Planning, verify compatibility, approved destination,
  permissions and scenario readback.
- Author/deploy the Rayfin experience using only approved aggregate views, an owned
  action log and actual business context keys (not an assumed county). Test bundle
  parseability and signed-in deployed connector/CRUD/ownership.
- Rehearse and record links, expected figures, limitations and recovery instructions.

App actions and Planning use separate databases. Actions do not update the
ontology/agent in this version. Governance metadata is illustrative, not enforcement
or evidence of production readiness.

## Development

```powershell
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python -m compileall -q demo_accelerator tests
```

Tests cover legacy fixtures and independent insurance/utilities schemas, 10/25-table
designs, typed recipes, data/SQL/metric reconciliation, notebook schema, workload
budgets, gates, drift and mocked durable-job recovery. They do **not** execute
Spark, DAX, ontology APIs or Rayfin in Fabric. The optional `dev` extra installs the
official Jupyter schema validator; without it those checks are explicitly skipped.

## Layout

| Path | Purpose |
|---|---|
| `demo_accelerator\config.py`, `discovery.py` | Brief validation and research-led proposal instructions |
| `demo_accelerator\blueprint.py` | Flexible schema/metric/recipe validation and dependencies |
| `demo_accelerator\flexible_data.py` | Deterministic proposed-schema execution |
| `demo_accelerator\flexible_artifacts.py` | Dynamic notebooks, SQL and specialist contracts |
| `demo_accelerator\data.py`, `artifacts.py` | Legacy reference generator and version dispatch |
| `demo_accelerator\state.py`, `fabric.py`, `cli.py` | Approvals, evidence, durable jobs and commands |
| `examples\`, `docs\`, `tests\` | Worked example, operator contract and behavioral coverage |
| `AGENTS.md` | Copilot execution rules and phase boundaries |
