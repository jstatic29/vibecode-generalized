# Fabric customer demo accelerator

A guided, checkpointed starting point for customer-specific Microsoft Fabric IQ
demos: **see a problem -> explore relationships -> ask a grounded question -> record a response**.
Derived from the lessons of a successful synthetic healthcare demo, without its
customer data, workspace identifiers, deployment state or credentials.

## Status: working foundation, not yet a turnkey end-to-end deployer

| Capability | v0.1 |
|---|---|
| Validated customer/audience/source/scope intake | Implemented |
| Healthcare access and manufacturing fulfillment templates | Implemented |
| Deterministic local previews and expected answers | Implemented |
| Raw JSON -> bronze -> silver -> gold Fabric notebook | Generated; not yet executed in a real Fabric workspace |
| Durable notebook deployment/job monitoring | Implemented; mocked recovery checks, not yet live-validated |
| Approval gates, artifact integrity, resumable state and evidence | Implemented |
| Website research and use-case selection | Copilot/operator-assisted; not an automatic website crawler |
| Ontology, graph, data agent and Rayfin app | Contracts/runbook generated; specialist-assisted authoring/deployment |
| Optional semantic model and Fabric Planning | Contracts and gates generated; specialist-assisted implementation |
| Few-hour runtime target | Design goal, not benchmarked |

This repository does **not** yet meet the acceptance bar of an independently
operable, fully deployed end-to-end accelerator. The next implementation milestone
is a live reference run, concrete IQ/app adapters and a second-industry rehearsal.
Do not present generated contracts or operator attestations as deployed features.

## Quick start (PowerShell)

Python 3.11+ is sufficient for local preparation; no third-party runtime packages.
Run commands from this repository's root. Installation is optional:
`python -m pip install -e .` exposes the `fabric-demo` command.

```powershell
python -m demo_accelerator init --scenario healthcare-access --output intake.json
# Edit intake.json: customer URL, audience, sources, scope and approved target.
# Research the website with Copilot; record citations and confirm assumptions.
python -m demo_accelerator plan intake.json
python -m demo_accelerator generate intake.json --run-dir .demo-runs\customer-001
python -m demo_accelerator status --run-dir .demo-runs\customer-001
```

`init` never overwrites an existing file. `generate` requires a new run directory.
Generated artifacts are immutable: editing any artifact invalidates the run.
Change intake and generate a new run rather than trying to preserve stale approvals.
Run directories are ignored by Git and can contain operational workspace IDs and
operator notes. Do not put credentials, tokens, real records or personal data in intake
or evidence. Git ignoring is not a security boundary.

### Intake

- **customer**: name and public HTTPS website. The URL is research context, not a data source.
- **audience**: who is attending and what decision matters.
- **scenario**: `healthcare-access` or `manufacturing-fulfillment`. These are curated,
  fictional patterns; an unsupported use case needs an extended and tested template.
- **sources**: 1-6 high-level descriptions, such as Caboodle transfer data, ERP
  financial records and social-risk screenings. These label simulated extracts;
  no connection to the actual source is established.
- **scope**: 100-10,000 events, 3-12 regions, 6-24 sites, 3-24 months, fixed seed/end date.
- **features**: `app`, `semantic_model`, `planning`. Planning requires a semantic model.
- **deployment**: exact approved existing workspace name, lakehouse name, and a fresh
  schema starting with `demo_`. The tool never creates a workspace.
- **research**: citations, notes and explicit industry confirmation. Website claims
  and synthetic assumptions must be distinguishable.

To include Planning:

```json
"features": {
  "app": true,
  "semantic_model": true,
  "planning": true
}
```

### Stop gates

The sequence is **story -> design -> data-build -> fabric-iq -> optional
semantic-model -> optional planning -> optional app -> rehearsal**.
Later gates cannot be approved before their prerequisites are complete.
An approval permits a phase; it does not assert that the phase worked.

```powershell
python -m demo_accelerator approve --run-dir .demo-runs\customer-001 --gate story --note "Reviewed audience fit, website citations and synthetic assumptions"
python -m demo_accelerator evidence-template --run-dir .demo-runs\customer-001 --gate story
```

Save that JSON **outside the immutable run**, fill the checks only after doing them,
and record notes and references. Then:

```powershell
python -m demo_accelerator complete --run-dir .demo-runs\customer-001 --gate story --evidence story-evidence.json
```

`complete` records an **operator attestation**, not an automated verification and
not a deployment. Disabled phases cannot be marked complete. Data-build cannot be
completed by attestation; only its durable job adapter can advance it.
`status` reports `demo_ready` only after all enabled gates are complete; examine
the evidence kinds, not just this flag.

### Approved data deployment

Requires Azure CLI, `az login` to the intended tenant, an accessible Active Fabric
capacity and appropriate workspace permissions. Only public-cloud Fabric is supported.
Feature availability for IQ, data agents, apps and Planning is a separate operator check.

```powershell
python -m demo_accelerator preflight --run-dir .demo-runs\customer-001
# Complete story and design; review OPERATOR.md and the notebook before approval.
python -m demo_accelerator approve --run-dir .demo-runs\customer-001 --gate data-build --note "Approved this workspace, lakehouse creation, notebook run and fresh schema"
python -m demo_accelerator deploy-data --run-dir .demo-runs\customer-001 --timeout 1800
```

This can create a schema-enabled lakehouse and a uniquely named notebook, then
submit a `RunNotebook` job. **No interactive Livy execution is used.** The notebook
fails if the target schema is populated; it never resets or overwrites it.
An existing non-schema-enabled lakehouse will fail at schema creation, not silently
switch layouts. The existing lakehouse must be schema-enabled.

Monitoring timeout means **the local wait ended, not the remote job**.
Repeat the same `deploy-data` command to resume the saved job/operation. It will
not blindly retry a POST. An ambiguous create with no visible item or a failed
partially written build stops for investigation. Do not clear the state to force a
retry. A failed build normally needs a new, approved schema/run; no cleanup or
resource deletion is automated.

One process at a time may mutate a run. If a process crashes and leaves
`.run.lock`, inspect its recorded PID and job state before removing that specific
lock file. Never delete the run directory to recover an in-flight job.

### Remaining Fabric phases

Every generated run contains `OPERATOR.md` with the current workflow and handoffs
to the ontology, semantic-model and Rayfin skills. Those phases are not executed
by the Python CLI in v0.1. They need a Copilot-assisted session/operator:

1. Verify SQL metadata synchronization and exact totals.
2. Author the generation-2 ontology from its contract; verify readback, graph
   materialization and SQL/GQL parity. Guide portal steps where APIs are unavailable.
3. Configure and publish the data agent, including schema selection and instructions;
   distinguish draft examples from actual published behavior.
4. If selected, build and reconcile the semantic model, then verify Planning
   compatibility, destination permissions and scenario writeback. Direct Lake
   compatibility is **not assumed**. Any Import fallback needs approval.
5. If selected, author/deploy the Rayfin app with live aggregate analytics and a
   server-enforced owned action log. Verify the signed-in deployed connector and
   built bundle; a local fixture is not proof.
6. Rehearse and record links, expected figures, limitations and recovery instructions.

## Data and metric contract

Each run builds **17 Delta tables**, not a 98-table enterprise replica:

| Layer | Contents |
|---|---|
| Raw | Three source-shaped JSON extracts under lakehouse Files |
| Bronze | Events, finance and risk; includes a deliberate duplicate and invalid site |
| Silver | Cleaned events, finance, risk and quarantined events |
| Gold | Region, location, resource, reason and contiguous date dimensions; three facts |
| Supporting | Lineage and catalog metadata, including a catalog entry for itself |

All records are synthetic. Labels explicitly say illustrative region/site.
Financial amounts use integer cents. Contextual risk is undated and belongs to
an independent population. Finance and risk must be aggregated independently
before joining to operational figures. Do not imply event-level linkage or causality.
The date window and data quarter are fixed for reproducibility; partial quarters
are explicitly flagged. Ranks have a name tie-break; display rounding occurs once.

`expected.json` provides exact global and selected-quarter metrics. The notebook
asserts counts, referential integrity, dates, money and headline totals.
The SQL view provides regional quarterly aggregates, including zero-event regions.
The semantic-model contract uses the same metric rules, date dimension and money units.

The action app's database and Planning writeback database are separate. Actions do
not flow back into the ontology/agent in v0.1. Governance metadata is illustrative,
not enforcement or evidence of production readiness.

## Development

```powershell
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python -m compileall -q demo_accelerator tests
```

Tests cover both industries, exact row/metric shapes, SQL aggregation reconciliation,
date coverage, approval ordering, artifact/evidence drift, notebook syntax/schema and mocked
Fabric recovery. They do **not** execute Spark, DAX, ontology APIs or Rayfin in Fabric.
No live-validation claim should be inferred from them.
The optional `dev` extra installs the official Jupyter notebook schema validator;
without it that one check is explicitly skipped and the remaining tests use the standard library.

## Repository layout

| Path | Purpose |
|---|---|
| `demo_accelerator\config.py` | Strict intake validation and curated scenarios |
| `demo_accelerator\data.py` | Portable deterministic synthetic generator |
| `demo_accelerator\artifacts.py` | Notebook, SQL, expected answers and specialist work packages |
| `demo_accelerator\state.py` | Approval gates, integrity manifests and evidence |
| `demo_accelerator\fabric.py` | Capacity preflight, safe create, durable jobs and resume |
| `demo_accelerator\cli.py` | Operator commands |
| `tests\` | Offline behavioral checks |
| `AGENTS.md` | Copilot execution rules and phase boundaries |
