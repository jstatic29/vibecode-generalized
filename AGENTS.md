# Working on this accelerator

Read README.md before execution. This is a private, synthetic-data demo toolkit.
Do not touch the original healthcareindustry2 project or reuse its resource IDs.
Do not copy its generated envelopes, credentials, node_modules or runtime state.

## Operating contract

- Website + audience + source descriptions inform a proposed scenario, not claims
  about actual customer systems or problems. Research public pages, cite sources
  and ask the operator to approve assumptions. Do not ingest customer data.
- Use a tested scenario template. Unsupported industries/use cases require a
  reviewed extension; do not silently relabel healthcare to force a fit.
- Keep core data small and deterministic. One scenario specification must drive
  metric semantics across SQL, ontology, graph, agent, app and optional semantic model.
- Run `python -m demo_accelerator` from the repository root. Read each run's
  OPERATOR.md. No dependency installation is needed for local commands/tests.
- Respect explicit stop gates. Never auto-approve, invent evidence or report a
  contract as deployed. Record machine evidence separately from owner attestation.
- Generated runs are immutable. Change intake and generate a new run if artifacts
  change. Never delete state to bypass approvals or restart an ambiguous write.
- Fabric writes, notebook runs, graph materialization, model refresh, publication,
  Rayfin dev/up and writeback tests require the applicable approval.
- Use existing approved workspaces and freshly scoped demo schemas. No blanket
  reset, destructive overwrite, broad cleanup, capacity resizing or resource deletion.
- Long-running Spark work uses submitted notebook jobs, not interactive Livy.
  Persist IDs, poll existing runs, respect capacity throttling and never blindly retry creates.
- A local timeout is not remote cancellation. Explain the saved job/operation and resume.
- Every Fabric REST call includes its owning skill's x-ms-fabric-skill header,
  including polls. Never send tokens outside the validated API host.
- Keep runtime credentials out of configuration, logs, Git, evidence and generated
  app bundles. Follow interactive sign-in; do not work around authentication gates.

## Specialist execution

Load current installed skills before the phase; verify current API/CLI support.
Historical product limitations are leads to recheck, not immutable platform facts.

- **Spark**: spark-cli authoring; inspect the generated notebook. The CLI currently
  automates only this phase. Live execution is still required to validate the adapter.
- **Ontology**: fabriciq-ontology-cli authoring/consumption. Generation-2 TMDL,
  stable lineage tags, preserve portal bindings, diff/readback. Manual portal
  attachment/materialization where APIs are blocked. Verify properties and edges
  with actual graph queries, not just successful refresh status.
- **Data agent**: consult current Fabric knowledge for authoring/publishing.
  Instructions + selected lakehouse source + ontology meaning; do not claim agent
  SQL answers prove graph traversal. Preserve output-as-is publishing instructions.
  Test draft/published separately, small repeated samples, <=2 concurrent asks.
- **Semantic model**: semantic-model-authoring. The registered modeling MCP here
  only supports workspace models, not offline PBIP/Desktop. Discover actual schema;
  use a supported authoring route and persist/export definitions. Verify DAX,
  selected-quarter filters, credentials and viewer access. Keep model identity stable.
- **Planning**: optional, requires model. Verify feature and storage-mode compatibility.
  Ask before Import fallback. Dedicated approved writeback database, Planning-owned
  destination tables, portal permissions and scenario readback.
- **App**: rayfin-getting-started plus generated in-project skills and installed CLI
  docs. Live aggregate-only connector, clearly labelled approved snapshot fallback,
  separate action database and service-enforced ownership. No source-level entities.
  Run actual bundle parseability and signed-in deployed connector/CRUD checks.
  Never assume a successful Vite build or local stub proves the deployed app.

## Current acceptance boundary

The v0.1 CLI generates work packages for IQ/app/model/Planning; those are not yet
deployment adapters. Be explicit about this gap. A full accelerator release needs
a successful live reference run and a second-industry run by another presenter.
Keep speculative features out of the default few-hour path.

## Validation

`python -m unittest discover -s tests -v`

`python -m compileall -q demo_accelerator tests`

The optional `.[dev]` extra enables the official notebook schema check.

Add targeted tests for every scenario/configuration/approval/recovery change.
Do not count mocked API tests as Fabric verification. Do not run capacity-heavy
agent suites immediately before a demo.
