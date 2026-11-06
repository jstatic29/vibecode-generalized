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

## Local preparation

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
