# Limited presenter pilot

Status: pilot kit prepared; no new presenter run or Fabric deployment has been
performed. This is a technical-presenter pilot, not a business-viewer release
or a turnkey deployment promise.

## Objective and scope

Have one presenter other than the original builder use a fresh checkout and a
new Copilot conversation to build a small, second-industry synthetic demo:

**Customer brief -> approved story/design -> data -> ontology/graph -> agent.**

Semantic model, Planning and Fabric app are excluded from this pilot. M365
publication is optional and separately approved. The few-hour goal is something
to measure, not a guaranteed duration. One bounded run is enough for the first
pilot; do not start several deployments in parallel.

The existing-data routes are accepted SQL-only walkthroughs, not proof of
existing-data ontology/graph acceptance. A presenter choosing existing data
must use the separate [existing-data flow](../README.md#existing-data-option)
and agree its scope before execution. Do not mix data modes within a run.

## Roles and prerequisites

The sponsor grants private-repository access, identifies the presenter and
approves the workspace/capacity budget. The presenter owns sign-in, scope
approvals, manual portal steps and final acceptance. Copilot prepares proposals,
executes approved supported operations and preserves evidence. A reviewer
compares outputs with baselines and records where builder assistance was needed.

Before customer-specific work, verify:

| Requirement | Check |
|---|---|
| Repository | Presenter can clone the private repository; record its commit SHA |
| Local tools | Python 3.11+, Git and Azure CLI available; PowerShell examples below |
| Copilot host | Repository instructions and `fabric-demo-companion` can be loaded; required file, shell and web tools available |
| Fabric specialists | Current Spark and SQL endpoint guidance, supported generation-2 ontology authoring/graph guidance, and current data-agent API/docs available |
| Execution tools | SQL Endpoint MCP available; identify the agent runtime route or an operator-run portal route before testing |
| Fabric access | Presenter signs in with their own approved identity; existing workspace, capacity, required previews and item permissions confirmed |
| Boundaries | No production records, credentials in files, copied reference state, unapproved writes or destructive cleanup |

Load current specialists before their phases. A skill name alone does not prove
API support. Some installations expose only legacy V1 ontology authoring:
that is not a substitute for generation-2 TMDL. If the required specialist is
missing or conflicts with the selected route, record a blocker and stop that
phase. The sponsor may separately approve a reviewed public-API-assisted route
using the documented `/ontologies` endpoints and current definition format.
Do not silently reuse the original builder's scripts, install plugins or switch
to legacy JSON/Ontology Agent.

See the [ontology REST operations](https://learn.microsoft.com/en-us/rest/api/fabric/ontology/items),
[new ontology definition](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/ontology-definition)
and [graph query API](https://learn.microsoft.com/en-us/fabric/graph/gql-query-api).
Every Fabric REST call, including polls, needs its owning skill's
`x-ms-fabric-skill` header. Never forward credentials through redirects or
outside validated API hosts. Stop on interactive authentication gates.

## Start from a clean presenter environment

Clone the repository through the presenter's own GitHub account:

```powershell
gh repo clone jstatic29/vibecode-generalized
Set-Location vibecode-generalized
git rev-parse HEAD
python --version
az version
python -m demo_accelerator --help
```

Local generation needs no dependency installation. Only install optional SQL
dependencies if the explicitly chosen ODBC route needs them; that route also
requires ODBC Driver 18. Do not copy `.demo-runs`, credentials, generated
envelopes, dependencies or runtime state from the reference builder.

Open a new Copilot conversation rooted in this checkout and paste:

> Use fabric-demo-companion and the presenter pilot guide. Read README.md,
> AGENTS.md and docs/flexible-proposals.md first. Start a new synthetic,
> second-industry demo from my public website, audience and high-level source
> descriptions. Ask for missing inputs and verify required skills/tools before
> writes. Research public pages, cite evidence, propose 2-3 use cases and
> recommend a small deterministic model for my selection. Do not assume a schema
> or relabel the finance/healthcare scenario. Exclude semantic model, Planning
> and Fabric app. Keep explicit approval gates, use durable notebook jobs,
> preserve evidence and stop at unsupported operations. Do not deploy yet.

Supply a real public website, audience, source descriptions, the approved
workspace and an intended demo-duration/data budget. These describe context,
not permission to ingest customer records or proof of their internal systems.
The presenter should not need to author a schema or generator code.

## Preparation and execution

Copilot can prepare the intake with the CLI from the repository root:

```powershell
python -m demo_accelerator init --output pilot-intake.json
# Copilot fills the brief, research and user-selected proposal.
# Set features.app, features.semantic_model and features.planning to false.
python -m demo_accelerator plan pilot-intake.json
# After local review, use a NEW run directory:
python -m demo_accelerator generate pilot-intake.json --run-dir .demo-runs\presenter-pilot-001
python -m demo_accelerator status --run-dir .demo-runs\presenter-pilot-001
```

These are local preparation commands, not deployment approval. Do not execute
them with an incomplete or unselected proposal. Read the generated `OPERATOR.md`.
Keep generated artifacts immutable; put operational evidence in a sibling
folder such as `.demo-runs\presenter-pilot-001-operations`.

| Phase | Exit evidence and manual checkpoint |
|---|---|
| Readiness | Tool/identity/workspace checks, baseline commit, agreed exclusions; record unsupported surfaces before a write |
| Story/design | Cited research, selected scenario, approved assumptions/model and bounded physical rows/compute; no fixed table quota |
| Data | Approved durable notebook job, saved job ID, successful assertions and independent SQL counts/metrics; no long-running interactive Livy |
| Ontology | Reviewed generation-2 definition, stable lineage, friendly names/labels/rules, physical joins and business mappings; export/diff/readback |
| Native binding/graph | Operator checks every property and graph eligibility; separately approved materialization and real bounded graph queries compared with SQL |
| SQL-only agent | Exact selected parent tables AND columns, relevant facts/dimensions, instructions and SQL-validated examples; validator readback |
| Published agent | Approved Preview publication and one initial health ask, then an explicitly approved small analytical sample against SQL |
| Ontology attachment | Operator attaches ontology through portal, separately approved second publication, bounded post-attachment sample with semantic/refusal checks |
| Handoff | Evidence, links, metrics/date caveats, owner reports versus machine checks, deferred/failed items and exact next action |

Preserve the selected [agent sequence and publishing wording](../.github/skills/fabric-demo-companion/references/ontology-and-agent.md).
Example re-saving and source-column reselection are observed workarounds, not
universal requirements or fixes for every error. Recheck current support; never
hide validation failures. M365 publication/access is a separate checkpoint.

Use the CLI's actual gate requirements:

```powershell
python -m demo_accelerator evidence-template --run-dir .demo-runs\presenter-pilot-001 --gate fabric-iq
```

Fill required evidence truthfully and obtain approval before the documented
`complete` command. This checklist and the pilot report do not replace gate
evidence or waive failed checks. Keep owner scope decisions explicit.
The final rehearsal gate still has its own requirements; do not call the whole
run `demo_ready` merely because this limited IQ pilot is accepted.

## Recovery and support

Stop for missing permissions/skills, throttling, invalid examples, unexpected
source identity, baseline mismatch or ambiguous writes. Save request intent,
operation/job ID, response and uncertainty. A local timeout is not remote
cancellation; poll the saved operation/continuation when supported. No blind
create/query retries, state deletion, blanket resets or capacity resizing.

Escalate with the exact phase, sanitized error, saved operation reference,
expected/observed result and last successful checkpoint. Never include tokens,
secrets or raw customer records. `.gitignore` is not a security boundary.
Record every builder intervention: fixing an instruction is useful pilot
feedback; silently copying a private execution script defeats the trial.

## Acceptance and feedback

Copy [pilot-report-template.md](pilot-report-template.md) into the private
operational folder and fill it as work occurs. The report is manual feedback,
not an automated CLI input.

Accept the scoped pilot only when a different presenter demonstrates the
second-industry flow with traceable data/SQL/graph/agent evidence, understood
manual checkpoints and no approval/security bypass. Graph execution must be
proven independently; agent SQL accuracy alone is insufficient. Report sample
size, precision, missing/duplicate groups and repeatability honestly.

Use **accepted**, **accepted with explicit limitations**, or **blocked**;
do not turn unknowns into passes. Record setup, active work, remote wait and
support time separately. A single supported run does not prove turnkey
automation, general availability or a full-stack release.

## Sponsor's launch checklist

Choose one presenter and a second-industry customer context, share this guide
and the private repo at the recorded commit, confirm their prerequisites, then
let them start from the prompt above. Do not supply this conversation as a
hidden prerequisite. Use [the finance reference](finance-reference.md) to
explain evidence quality, not as the new customer's schema or deployment state.
