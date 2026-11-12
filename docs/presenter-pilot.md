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
| Usage accounting | Identify the Copilot usage source and a capacity owner who can provide pilot-filtered Fabric CU metrics; see usage tracking below |
| Boundaries | No production records, credentials in files, copied reference state, unapproved writes or destructive cleanup |

### Prerequisite checklist

Run these read-only checks in two stages. Do not require a target just to check
local tooling, or require optional-phase connections for the core pilot.

| Stage | Check | Evidence |
|---|---|---|
| Before discovery | Installed/enabled Fabric plugins and discoverable specialist skills | Plugin versions and successful skill loading; inspect actual capabilities, especially generation-2 ontology authoring, not just names |
| Before discovery | Local tools and Copilot host | Python/Git/Azure CLI versions, accelerator CLI availability, repository instructions and required file/shell/web tools |
| Before discovery | Authentication and MCP availability | Current Azure account/tenant and Fabric token acquisition without displaying the token; discover required MCP tools. Tool discovery alone does not prove sign-in |
| After data-mode/target selection | Azure CLI/REST target access | Permission-checked workspace discovery/readback, assigned capacity and its state; record required feature availability as verified or operator-attested |
| After data-mode/target selection | SQL Endpoint MCP | Identity-only query against the selected endpoint: `SELECT DB_NAME() AS database_name, USER_NAME() AS database_user, SUSER_SNAME() AS execution_login;`. Verify endpoint/database and actual identity; do not read source records |
| After data-mode/target selection | FabricIQ MCP, when needed | Authenticated artifact discovery using a relevant search term; this proves discovery access, not data-agent authoring/publication or access to every artifact |
| After data-mode/target selection | Power BI modeling MCP, only for a requested semantic-model phase | Inspect connections and verify authenticated read access to the selected workspace/model. No connections is unverified, not proof of failed authentication; no selected model means defer the check |
| Existing-data mode, before assessment | Effective source-read-only permissions | Separate owner evidence for every execution identity, including delegated owners; SQL identity or an admin connection does not prove read-only access. No write probe |

Present a dated report with **passed, blocked, unverified or not applicable** for
each check, its evidence, affected phase and remaining owner decision. Distinguish
machine results from owner attestations. Availability is not authentication, and
authentication is not permission. Azure CLI and each MCP can use different
identities; test them independently rather than assuming shared sign-in.

Use Azure CLI/REST for control-plane checks; the general Fabric MCP is not a
prerequisite. Load the owning skill before calls and include its attribution
header. Optional ODBC/app tooling is checked only if that route is selected.
Do not initiate sign-in, install software, refresh models, run notebooks, or
substitute unsupported execution routes automatically. Report a blocker and
stop only the affected phase; retain the existing approval gates.

Keep account identities, tenant/resource IDs and dated receipts in private
operational evidence outside immutable generated artifacts, never portable docs.
Never save tokens. Recheck after identity, target, plugin or connection changes
and before the affected phase; a previous pilot's results are not reusable
prerequisite approval. This checklist is Copilot-assisted, not a new automatic
CLI preflight or gate-completion adapter.

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
> AGENTS.md and docs/flexible-proposals.md first. Before generation, ask me to
> choose between synthetic data and eligible existing data; do not make the
> choice for me. Explain that synthetic data is generated for the demo, while
> the existing-data path uses approved individual Lakehouse or Warehouse table
> shortcuts, verified source read-only permissions, and bounded metadata and
> aggregate assessment. Explain that the synthetic pilot covers ontology/graph
> and agent, while the existing-data walkthrough is accepted only for its
> SQL-only scope. Follow the selected path and do not mix modes in a run.
>
> Follow the presenter guide's prerequisite checklist before execution. Check
> tools, plugins and skill capabilities first; after I select the data path and
> targets, verify authentication and target access independently for Azure CLI
> and each required MCP. Report passed, blocked, unverified and not-applicable
> checks, and stop only the affected phase. Do not initiate sign-in, install
> software or switch execution routes without approval.
>
> Start a second-industry demo from my public website, audience and high-level
> source descriptions. Ask for missing inputs and verify required skills/tools
> before writes. Research public pages, cite evidence and propose 2-3 use cases.
> For synthetic data, recommend a small deterministic model for my selection;
> for existing data, use the approved readiness assessment to inform the model.
> Do not assume a schema or relabel the finance/healthcare scenario. Exclude
> semantic model, Planning and Fabric app from this pilot. Keep explicit approval
> gates, use durable notebook jobs when applicable, preserve evidence and stop
> at unsupported operations. Prepare pilot usage
> tracking before work. Use pilot-copilot-usage against this session's own
> native usage state at phase boundaries and handoff, saving private snapshots.
> Capture Fabric CU measurements separately with their provenance, and never
> substitute token counts or premium request multipliers for credits.
> Do not deploy yet.

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
For the graph checkpoint, follow the
[materialized graph query handoff](graph-query-handoff.md): discover the graph
model separately from the ontology, execute approved GQL through the beta
Graph Query API, preserve continuation/error receipts and reconcile typed
results with SQL. A data-agent answer is not a substitute. The runbook includes
reference queries and recovery behavior without requiring private builder scripts.
Example re-saving and source-column reselection are observed workarounds, not
universal requirements or fixes for every error. Recheck current support; never
hide validation failures. M365 publication/access is a separate checkpoint.

Read the [second-industry pilot findings](second-industry-pilot.md) before
repeating the exercise. [Native binding inspection](ontology-bindings.md) remains
mandatory after final writes; source-column repair is conditional on unresolved
mappings. Optional [SDK evaluation](data-agent-evaluation.md) needs actual-namespace
collision checks, approved result-table writes and a reviewed dependency path;
interactive success is not a durable-job benchmark.

Use the CLI's actual gate requirements:

```powershell
python -m demo_accelerator evidence-template --run-dir .demo-runs\presenter-pilot-001 --gate fabric-iq
```

Fill required evidence truthfully and obtain approval before the documented
`complete` command. This checklist and the pilot report do not replace gate
evidence or waive failed checks. Keep owner scope decisions explicit.
The final rehearsal gate still has its own requirements; do not call the whole
run `demo_ready` merely because this limited IQ pilot is accepted.

Keep the final evidence somewhere private outside Copilot's session storage,
in a new sibling operational package, not inside the immutable generated run.
Use relative paths, a source-reference index and SHA-256 manifest. Preserve
historical reports/readbacks unchanged; label later corrections and omissions.
Include the matching final usage worksheet/report, pending gate status and
outstanding job/session owner/status/required approval. If ownership was not
recorded, say so and assign it before further execution. Do not copy credentials,
native conversation events or unrelated scripts. An ignored folder is not an
access control boundary; retain private evidence locally or in an approved
private store, and return only sanitized findings to Git.

## Pilot usage and cost tracking

The local CLI reads **native Copilot session AI credits**, totals those credits
and operator-supplied Fabric CU-seconds, and optionally values them using
supplied, sourced rates. It does not retrieve account billing records, read
another presenter's Copilot history, query the Capacity Metrics model or change
Fabric resources. No extra dependencies are needed for native local-session
capture; collecting Fabric measurements needs the capacity owner's help.

Before the first pilot question, create a private worksheet outside the immutable
generated run (this can happen before a run exists):

```powershell
python -m demo_accelerator pilot-usage-template --output .demo-runs\presenter-pilot-001-operations\usage-v1.json
```

Record timezone-qualified `window.start` and `window.end` for the whole pilot,
including research/setup. Fill `coverage_notes` with missing sessions, waits,
delayed measurements, shared activity and exclusions. Numbers may be JSON
numbers or decimal strings. Leave unavailable quantities as `null`, never zero.
An empty array means no measurements supplied, not verified zero consumption.
Each measurement needs a distinct `scope_ref`, `evidence_ref` and timezone-qualified
`captured_at`. These references identify private saved evidence; the CLI does
not open or independently verify that evidence.

### Collect Copilot credits

**Copilot should capture this itself, rather than asking the presenter to type
credit totals.** In the installed CLI, `/usage` is the equivalent of a session
`/cost` display. For the accelerator's read-only equivalent, have Copilot use
its host-provided current session folder (do not guess a UUID or scan other
presenters' sessions):

```powershell
python -m demo_accelerator pilot-copilot-usage --session-dir "<current-session-folder>" --output .demo-runs\presenter-pilot-001-operations\copilot-credits-end.json
```

This reads the native accounting checkpoint plus newer usage records, deduplicates
them by source-session sequence and converts the runtime's `totalNanoAiu`:
**1,000,000,000 nano-AI units = 1 AI credit**. It does not infer a price from tokens,
launch Copilot, resume the session, make a model call or require an SDK install.
Capture at the start, phase boundaries and handoff using distinct output names.
It is a snapshot of recorded usage; in-flight work and the final reply can add
credits. On a reused session, the full session total is not the pilot total:
use same-session start/end snapshots and disclose their difference/coverage,
or use the required fresh pilot conversation.

The output preserves `ai_credits_status` and includes a ready-to-use
`worksheet_entry`. Copilot copies that entry into the usage worksheet, changing
`evidence_ref` to the saved snapshot path. Partial or unavailable totals retain
their reported subtotal separately and leave the worksheet's complete credit
quantity unknown. Unsupported native schemas, missing checkpoints, sequence gaps
and torn writes fail explicitly. This adapter is runtime-specific; it was checked
against the installed session format on 2026-11-11, not every Copilot host.

For a presenter starting the standalone CLI, its native final export is another
route:

```powershell
copilot --usage-output-file .demo-runs\presenter-pilot-001-operations\copilot-native-final.json
# After that session exits:
python -m demo_accelerator pilot-copilot-usage --usage-file .demo-runs\presenter-pilot-001-operations\copilot-native-final.json --session-ref "<pilot-session-id>" --output .demo-runs\presenter-pilot-001-operations\copilot-credits-final.json
```

Run the launch command only when the presenter intends to start their pilot CLI,
not inside an active agent as a way to read its usage. Check `copilot --help`
and `copilot help billing` for support. Existing SDK integrations can instead
call the experimental
[`session.usage.getMetrics`](https://github.com/github/copilot-sdk/blob/main/docs/features/usage-and-billing.md#accumulated-ai-credit-and-token-totals)
on the session they already own and save its result; do not create a new empty
session to measure an existing conversation. Native imports require both the
credit total and its completeness status; legacy request counts are not credits.

Record one non-overlapping cumulative entry per session, including support work
when attributable. Runtime-attributed subagent consumption is already included:
do not add its per-agent breakdown again. Separate sessions count separately only
when not already included in the parent total. Resumed cumulative totals replace
earlier totals rather than being added to them.

**Fallback only:** if the host cannot expose native usage, record the limitation
and use `/usage` output or
[GitHub's AI usage view](https://docs.github.com/en/copilot/how-tos/manage-and-track-spending/monitor-ai-usage):
Business/Enterprise users can view consumption in Copilot settings; individual
users can use Billing and licensing -> AI usage. Save timestamped before/after
consumed-credit readings from the **same billing cycle**, wait for reporting
to settle, and enter `after - before` as `credits`. Do not subtract remaining
allowances, budgets or percentages. If a cycle reset occurs, split at the reset
using valid cycle-specific evidence; do not turn a negative difference into zero.
Use `isolated-account-delta` only when no other account activity occurred.
Otherwise use `shared-account-delta`, which the report marks approximate, and
disclose unrelated activity. GitHub does not generally guarantee prompt/session
attribution in billing reports. If isolation is impossible, leave usage unknown
instead of claiming exact pilot credits.

Do not mix overlapping account deltas and session totals. Tokens, request counts,
legacy premium requests and a host's internal model billing multipliers are not
AI credits; no conversion is implemented. Included credits consumed are not
necessarily additional charges. Record actual incremental billing separately
in the private pilot report.

### Collect Fabric CU consumption

Ask the capacity owner to use the
[Capacity Metrics app compute page](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app-compute-page)
and save evidence filtered to the pilot's capacity, workspace, exact items,
operations and time range. Record the filters and capture timestamp. The compute
page has a rolling 14-day view; save evidence promptly. Capture operation CU
processing seconds, **not duration seconds, utilization percentages or smoothed
timepoint percentages**. A shared capacity's entire usage is not pilot usage.
Do not export unrelated users' activity or customer records.

Use separate, non-overlapping entries for `billing_mode`:
`capacity`, `spark-autoscale` and `nonbillable`. The CLI divides CU-seconds by
3,600 to report CU-hours separately for each mode; it never prices nonbillable
operations. Autoscale Spark needs its own metering evidence and rate, not the
base capacity rate. Record missing/unsupported metrics as unknown. Do not sum
item totals with the same operations' detail rows.

Allow for delayed metrics, background jobs and smoothing after the chat ends.
Record unfinished jobs and extend the accounting window for their consumption
when possible; a local timeout does not end a remote job or its cost. Save a
new worksheet/report revision when late evidence arrives, without modifying
generated artifacts or double-counting earlier totals.

### Produce the report and optional estimate

```powershell
python -m demo_accelerator pilot-usage-report .demo-runs\presenter-pilot-001-operations\usage-v1.json --output .demo-runs\presenter-pilot-001-operations\usage-report-v1.json
```

All three accounting commands refuse to overwrite existing files and make no network calls.
The report preserves measurements/rate provenance, missing usage, unpriced
entries, credits by attribution and CU-hours by billing mode. `reported` means
all supplied entries have quantities, **not independently verified complete
pilot coverage**. Unknown usage stays unknown; measured subtotals are not
complete totals.

Keep `rate: null` for usage-only reporting. To calculate an optional estimate,
replace it on each priced entry with this structure (replace every placeholder):

```json
{
  "per_unit": "<verified decimal rate>",
  "currency": "<three-letter currency code>",
  "source": "<private billing evidence or live pricing reference>",
  "as_of": "<YYYY-MM-DD>"
}
```

For Copilot the unit is **one AI credit**, not a token or premium request.
For Fabric the unit is **one CU-hour**; also add `"region": "<verified Azure region>"`.
Before supplying Fabric rates, load the cost-estimation specialist, resolve the
actual region and fetch the current
[Azure Retail Prices API](https://prices.azure.com/api/retail/prices)
rates, preserving the selected meter, currency and capture date as evidence.
Base capacity and autoscale Spark are distinct meters; no hardcoded rate or
fallback is provided. For contracted/internal allocations, document the approved
basis rather than representing it as public pricing. Have the billing owner
confirm the applicable Copilot rate and treatment of included credits.

The report computes `credits * rate` and `CU-seconds / 3600 * rate`, separately
by service and currency, only when all supplied billable entries for that service
are measured and priced. It does not convert currencies or claim a combined
invoice total. Capacity consumption valued at a per-CU-hour rate is an
**allocation estimate**, not the incremental charge for an already provisioned
shared capacity. Actual capacity billing depends on SKU, billed uptime,
reservations and separately billed usage. Storage, networking, licenses,
other services and post-window activity are excluded; record these limitations
and any actual billing evidence in the pilot report.

Keep completed worksheets, billing exports and reports private. Return only a
sanitized summary with the pilot feedback. Usage evidence does not grant
deployment approval or complete any demo gate.

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
