# Fabric customer demo accelerator

A guided, checkpointed starting point for customer-specific Microsoft Fabric IQ
demos: **see a problem -> explore relationships -> ask a grounded question -> record a response**.
Derived from the lessons of a successful synthetic healthcare demo, without its
customer data, workspace identifiers, deployment state or credentials.

## Customer-led, not industry-template-led

Start with a **customer website, audience and high-level existing-source descriptions**.
Copilot researches the context and suggests use cases and a synthetic data design.
The presenter selects/revises the recommendation and approves the story and schema
before Fabric writes.

There is **no industry allowlist and no fixed table count** in the default intake.
An approved model can have 10, 25 or another justified number of Delta tables.
Scope guardrails bound physical rows, staging copies and reviewed complexity, not
an arbitrary quota. Healthcare/manufacturing scenarios remain opt-in regression
examples, not the only supported industries.

Read [Flexible proposals](docs/flexible-proposals.md) for the discovery workflow,
supported declarative recipes and approval contract.

## Status: working foundation, not a turnkey end-to-end deployer

| Capability | Current implementation |
|---|---|
| Customer brief without preselected industry/schema | Implemented |
| Website research and use-case recommendations | Copilot/operator-assisted in Chat; no embedded LLM/crawler |
| Flexible proposed schema, grains, sources, references and metrics | Implemented, validated declarative recipes |
| Deterministic local previews and exact expected answers | Implemented |
| Raw JSON -> bronze -> silver -> gold notebook | Generated from the proposal; one synthetic project-finance data build live-validated |
| Durable notebook deployment/job monitoring | One live notebook build completed, including recovery after an async create response; mocked recovery checks also retained |
| Approval gates, artifact integrity and evidence | Implemented |
| Ontology, graph, data agent and Rayfin app | Dynamic contracts/runbook; specialist-assisted authoring/deployment |
| Optional semantic model and Fabric Planning | Dynamic contracts and gates; specialist-assisted implementation |
| Few-hour runtime target | Design goal, not benchmarked |

Generated contracts are **not deployed features**. A full accelerator release still
needs concrete specialist deployment adapters and live reference/rehearsal runs.
The project-finance data-stage reference reconciled all 16 Delta table counts,
headline totals and selected-quarter project rankings through the SQL endpoint,
with additional allocation, invoice, calendar and reference checks. This is not
live verification of other scenarios, DAX, ontology/graph, agents or apps, nor a
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
  and terminology. Test draft/published separately and use bounded question samples.
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
