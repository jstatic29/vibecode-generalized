# Materialized graph query handoff

This is the portable procedure used to verify the finance ontology's materialized
graph. It is specialist-assisted guidance, not an implemented accelerator query
adapter or permission to run queries. The private reference scripts and resource
IDs are not prerequisites for a new presenter.

**Validated practice (2026-11-10):** direct read-only GQL requests to the Graph
Query API reconciled materialized finance graph results against saved,
independently verified SQL baselines. This was separate from the data agent:
agent answers, ontology context injection and SQL joins do not prove graph
execution.

## Prerequisites and target identity

Read the current [GQL Query HTTP API reference](https://learn.microsoft.com/en-us/fabric/graph/gql-query-api)
and load the current ontology/graph specialist before execution. The documented
query endpoint is beta and not recommended for production. Recheck support,
permissions and the selected generation-2 ontology route; a legacy V1 authoring
skill is not a substitute. Missing/conflicting guidance is a blocker until the
sponsor separately approves a reviewed public-API route.

Use the presenter's own approved Azure CLI sign-in and existing approved
workspace. The ontology must already be bound to the intended tables, eligible
for graph creation, and materialized with the applicable approval. Querying
does not repair bindings or materialize/refresh a graph; those are separate
actions and approvals. Existing-data materialization also needs its own
disclosure approval because it can copy data.

Discover and record these identities in private operational evidence:

| Target | Discovery/readback |
|---|---|
| Workspace | `GET /v1/workspaces`; match the approved workspace, following list pagination |
| Ontology | Dedicated `/v1/workspaces/{workspaceId}/ontologies` routes; read back the selected generation and definition |
| Materialized graph | `GET /v1/workspaces/{workspaceId}/graphModels`; confirm which graph belongs to the selected ontology |

The graph model ID is **not the ontology ID**. Do not select the first graph,
infer identity from a similar name, reuse reference IDs or create a replacement
when discovery is ambiguous. Resolve the association through supported
readback/portal confirmation and retain the evidence. Read actual graph labels,
properties and directions; business-friendly ontology names need not be the
runtime graph labels, especially after renames.

## Request contract and authentication

With approval for the exact bounded read-only queries, use:

```http
POST https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/graphModels/{graphModelId}/executeQuery?beta=true
Authorization: Bearer <access-token-held-only-in-memory>
Content-Type: application/json
Accept: application/json
x-ms-fabric-skill: <owning-loaded-specialist-name>
```

In the finance reference, the owning specialist header value was `ontology-cli`.
Use the current owning skill's required value, including discovery calls and
continuation requests. The reference Python client acquired its token through
`az account get-access-token --resource https://api.fabric.microsoft.com`,
capturing output in memory without printing or persisting it. `az rest` can
obtain the token automatically with explicit
`--resource https://api.fabric.microsoft.com`.

Only send credentials to the validated HTTPS `api.fabric.microsoft.com` host;
do not forward them through redirects. Stop for interactive sign-in, missing
access or unsupported operations. Never place tokens in a request receipt,
configuration, Git or a shared report.

The body contains GQL, not SQL or a natural-language agent question:

```json
{
  "query": "MATCH (n) LET node_labels = LABELS(n) RETURN node_labels, COUNT(*) AS node_count GROUP BY node_labels"
}
```

This was the actual reference node-count query. Aggregated output is not proof
of a cheap scan: approve graph/scan scope, expected groups, disclosure/row bounds,
query hash and local wait budget before execution. Do not return raw entities
or use an unrestricted graph exploration as a health check.

The finance traversal followed these actual runtime labels and directions:

```gql
MATCH (p:`Project`)<-[:`Supplier_Invoice_Billed_For_Project`]-
      (i:`Supplier_Invoice`)-[:`Supplier_Invoice_Issued_By_Supplier`]->
      (s:`Supplier`)
FILTER i.is_on_hold = TRUE
LET project_key = p.project_id, supplier_key = s.supplier_id
RETURN project_key, supplier_key, COUNT(*) AS held_count,
       SUM(i.open_balance_cents) AS held_open_cents,
       COUNT(*) FILTER (
         WHERE CAST(i.project_id AS STRING) <> p.project_id
            OR CAST(i.supplier_id AS STRING) <> s.supplier_id
       ) AS key_mismatches
GROUP BY project_key, supplier_key
ORDER BY project_key, supplier_key
```

This is a reference example, not another customer's approved query or schema.
The string casts reflected observed graph key types differing from integer SQL
keys; inspect actual types and verify values rather than copying the casts
blindly. The query checks traversal link consistency, not all key uniqueness,
nullness or property coverage.

## Response handling and recovery

Persist request intent before submission, then save redacted HTTP/GQL responses
and timestamps outside the immutable generated run. HTTP 200 alone is not success:

| Response | Required handling |
|---|---|
| `status.code: "00000"` | Check result kind, columns/types, rows, additional statuses and expected output before accepting |
| `status.code: "02000"` with `result.nextPage` | Query is pending; preserve the opaque token and continue the same query |
| `02000` without `nextPage` | Can be an empty result; compare with expectations rather than treating it as pending or automatically passing |
| `additionalStatuses`, warnings or nested causes | Inspect and disclose them; do not silently accept partial results |
| HTTP/application errors | Preserve the error and stop or follow the documented recovery; no success-shaped fallback |

For a pending query, POST the **identical body** to:

```text
https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/graphModels/{graphModelId}/executeQuery?beta=true&continuationToken={encodedToken}
```

Treat `result.nextPage` as opaque: percent-encode it exactly once as a query
parameter value, without decoding or modifying its contents. Keep the same
authentication protections and specialist header on every continuation request.
Save each receipt/token before continuing. This continues the running query;
it is not permission to start a new one.

The current API documents a total query lifetime of up to 20 minutes and an
HTTP 408 `QueryTimeout` if exceeded. Choose a bounded local wait budget. The
successful finance retry used a 240-second per-request timeout and a separate
600-second continuation-wait budget; these were observed settings, not universal
requirements or proof of remote cancellation.

If a local timeout occurs, preserve the outstanding query, any continuation
token and the unknown remote outcome. Resume that continuation when supported.
If no response/token was received, stop and resolve the uncertainty; do not
blindly resubmit. The reference's first 60-second timeout remained an unknown
remote outcome; a separately approved attempt succeeded. A later success does
not prove the earlier request was cancelled. Respect throttling/`Retry-After`;
do not turn an error into a new query automatically.

Truncation is not normal continuation: the documented 64 MB internal result
limit can add an `additionalStatuses` warning with public code `01000` and
canonical GQLSTATUS `01M11`, without a token to retrieve omitted rows. Reject
that output as complete evidence. Obtain approval for a narrowed query; do not
hide missing groups with `LIMIT` or claim totals from an incomplete result.

## Acceptance evidence and handoff

Save private evidence for target association, definition/materialization version,
approval, exact GQL/hash, scan/output bounds, request intent, HTTP status,
primary/additional GQL statuses, typed rows and all continuation/error receipts.
Keep tokens and detailed live identities out of portable documentation.

Compare every expected group/value, edge direction and traversal relationship
against independently verified SQL for the same grain, filter, units and
snapshot/date semantics. Check missing/duplicate groups and key mismatches,
not just headline sums. Preserve the baseline timestamp and say whether SQL
was freshly executed or a saved verified result.

The 2026-11-10 finance check reconciled 3,602 nodes, 7,128 directed edges and
82 project/supplier groups covering 100 held invoices, 249,003,640 open cents
and zero traversal key mismatches. It reused saved SQL-verified baselines.
That fresh three-query sample did not rerun the earlier full property/key/
financial suite, refresh the graph or invoke the agent.

In the handoff, state which checks actually ran, which remain unverified,
outstanding continuations/unknown outcomes and the exact next approval/action.
Use the [pilot report](pilot-report-template.md) to record the evidence references,
but retain the CLI's actual gate requirements: this runbook or a successful
refresh does not complete the IQ gate or prove agent graph execution.
