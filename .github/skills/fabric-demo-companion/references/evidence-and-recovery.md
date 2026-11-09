# Evidence, recovery and handoff

Use the repository CLI's gate evidence format for `complete`; do not replace it.
The [companion template](../templates/phase-evidence.json) is an additional
operational note, NOT input to `complete` and NOT authorization.

Copy it outside the immutable run into a new operational package. Fill actual
values; leave unknowns null and checks not assessed. Never store secrets, real
customer data or tokens. Operational IDs belong only in the run's private local
evidence, not in this portable skill. An ignored directory is not a security
boundary. Preserve older evidence rather than rewriting the timeline.

Existing-data mode permits owner-approved metadata and aggregate baselines, never
raw records or sensitive disclosures. setup-lakehouse records creation intent,
operation and destination identity. inspect-shortcuts saves hashed machine
inventory separately from owner permission attestation. shortcuts evidence must
match that inventory; data-readiness needs actual table/metric assessments and a
recent timezone-qualified observation. Neither a checkbox nor shortcut existence
proves read-only ACLs. Ongoing drift/freshness checks are specialist checkpoints.

For the opt-in SQL runner, preserve hashed sql-plan approval separately from
machine sql-execution receipts. Request intent precedes each source read; failed
or timed-out receipts retain uncertainty and never complete a gate or trigger
automatic retries. Identity-only preflight is not aggregate/readiness evidence.
Exact decimal outputs are stored as strings. Driver timeout configuration does
not establish that a remote statement was cancelled.

## Evidence classification

| Kind | What it establishes |
|---|---|
| Validated practice | Named check actually executed, with expected/observed output, target version and evidence reference |
| Observed workaround | Dated sequence and outcome in a particular environment; no universal causal claim |
| Owner attestation | What the operator reports doing/seeing, retaining exact wording and time |
| Unfinished capability | Known implementation/acceptance gap, not an implied deployed adapter |

Operator-supplied query exports can be locally reconciled; record both the
operator provenance and the machine comparison. A screenshot or statement that
examples have no errors is not independent published-state readback. A remote
job status is not its data/graph/model acceptance output.

## Mutation recovery

Before an approved write, persist exact scope, approval reference, target identity,
payload hash/definition version and write intent. Save response/operation/job IDs
immediately, including asynchronous errors and receipts. Protect against concurrent
edits; read before update and stop if state diverges from reviewed content.

On timeout, inspect saved operation state and poll the same ID with specialist
telemetry headers. Do not recreate, blindly retry writes, clear state, reset data
or interpret timeout as cancellation. Surface ambiguous writes and permissions/
capacity/authentication failures; do not replace errors with success-shaped defaults.
If unable to resolve, hand off the saved operation and precise blocker.

## Handoff checklist

- Scenario/run path, immutable artifact version/hash and current feature selection.
- Completed phase actions with separate machine evidence and operator reports.
- Existing identities and outstanding operations located in private evidence.
- Manual checkpoints still required, pending approvals and validation blockers.
- Next exact acceptance check, expected baseline and success criteria.
- Unverified claims explicitly excluded: publication, ontology use, graph execution,
  viewer access, writeback ownership, optional deployments or full readiness.

Never set the IQ gate complete solely because agent examples validate or an
operator published it. Do not make a new runtime call merely to fill a template
without the applicable approval.
