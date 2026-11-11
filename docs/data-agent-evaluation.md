# Optional SDK evaluation: output and execution safeguards

SDK evaluation is optional, requires approved agent asks **and result-table
writes**, and does not replace graph queries, draft/published samples or viewer
access checks. It is not an implemented accelerator deployment adapter.

The [Fabric evaluation documentation](https://learn.microsoft.com/en-us/fabric/data-science/evaluate-data-agent)
describes `evaluate_data_agent`, the published `production`/`sandbox` stages, and
two output tables: the supplied name and its `_steps` companion.

## Destination verification and collision guard

The 2026-11-11 pilot SDK wrote both tables in **`eval_result`**, even though the
notebook selected `dbo` with `USE`. The original `dbo`-only collision check was
therefore unsafe. Never infer the SDK destination from the current SQL schema.

Before any future execution:

1. Verify the SDK version's actual destination behavior and the approved
   schema-enabled default lakehouse/workspace. Pin the reviewed SDK version.
2. Copy the [preflight cell helper](../.github/skills/fabric-demo-companion/templates/evaluation-preflight.py)
   into the notebook. Call it with verified context and identifiers immediately
   before evaluation. It checks the actual `eval_result` summary **and** `_steps`
   tables, plus legacy `dbo` collisions, and fails on catalog errors.
3. If either output exists, stop. Do not append, overwrite, drop tables, or
   change the name merely to retry an ambiguous operation. Reconcile saved
   evaluation/job IDs first; a genuinely new sample needs separate approval.
4. Permit only one writer to the reviewed destination. Existence checks are
   not an atomic lock against concurrent evaluations. Use the SDK's unqualified
   `table_name` only after verifying its destination; retain fully qualified
   output names in evidence. Never create evaluation outputs under shortcut paths.

The helper intentionally supports simple identifiers and the observed namespace;
it is not a universal SDK schema resolver. If a reviewed SDK version changes
that behavior, stop and update/retest the guard before execution.
Do not silently treat an inaccessible namespace as empty.

## Durable dependencies and session ownership

The pilot's durable evaluation job failed with generic statement errors;
the failed cell/root cause was not established. The operator's subsequent
interactive notebook succeeded for two scalar questions. That does not prove
durable execution compatibility, and does not establish that inline `%pip`
caused the failure.

For a future approved run, review a pinned Fabric Environment and its published
dependency snapshot, bind it to the notebook/job through supported guidance,
and record SDK/runtime/environment versions. Verify job-identity access and
actual SDK concurrency (at most two asks). Do not use an unpinned inline upgrade
as evidence of a repeatable durable setup. This setup remains unverified.

Save notebook/job/evaluation IDs, timestamped status and execution mode. Record
the identity that owns any interactive session and who will verify its shutdown.
At the pilot's last saved check its evaluation session was still `InProgress`;
this is not its current status. Recheck the existing session and obtain shutdown
approval rather than stopping it automatically. A local timeout is not remote
cancellation; do not start a replacement job blindly.

Preserve original notebook/evidence and make local revisions separately.
The corrected pilot revision is local only, has not been uploaded or run, and
must refuse the already-existing pilot outputs. Its dependency/approval stop
guards are deliberate. Capture readback and wider approved samples before
claiming durable or post-ontology acceptance.
