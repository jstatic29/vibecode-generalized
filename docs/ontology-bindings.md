# Native ontology bindings: verify before repairing

This is a handoff of observed behavior, not a deployment adapter or a universal
binding fix. Use current generation-2 authoring guidance and the approved
`/ontologies` route. Export, review the diff, obtain write approval and preserve
stable lineage, physical joins, business mappings and rules.

## Required checkpoint after the final definition write

Inspect every entity's native source identity, **Bind data -> Properties**
mappings, key types and graph eligibility. Record definition readback as machine
evidence and the operator's rendering/eligibility observations separately.
If everything is correct, no source-column reselection is required.

For unresolved mappings only, select the correct **Source column** from the
existing bound lakehouse table, save and recheck all properties. In the finance
reference, one reselection restored an entity's other properties; that behavior
is not guaranteed. Do not recreate the primary binding, add secondary sources
or change approved keys/grains to make the checklist pass.

Later definition writes can remove native metadata. Repeat inspection after
each final write; neither a successful update nor a source card proves bindings.
Stop on unresolved mappings or unsupported sources.

## Second-industry pilot observation, 2026-11-11

An approved Weston pilot update preserved/restored eight native partition
annotations on all eight backing tables. Definition readback confirmed their
presence and expected source identities without unexpected entity/relationship
changes. The operator reported eligibility and correct properties without
source-column reselection.

| Annotation | Meaning to verify from the actual native definition |
|---|---|
| `ONT_WorkspaceId` | Bound lakehouse workspace identity |
| `ONT_ItemId` | Bound lakehouse identity |
| `ONT_ItemKind` | Native source kind |
| `ONT_ItemName` | Bound item name |
| `ONT_WorkspaceName` | Bound workspace name |
| `ONT_SqlEndpoint` | Actual bound SQL endpoint |
| `ONT_SqlDatabase` | Actual bound SQL database |
| `ONT_PinnedAtUtc` | Native binding timestamp |

Preserve these on the partition where the exported definition places them;
do not move them to table/entity scope or copy values from another demo.
The exported expression used an `ONT_ALM_SQL_DATABASE-Lakehouse:` source reference
containing the actual workspace/item identities. Treat that as observed native
ALM metadata, not permission to handcraft a placeholder or an undocumented API.
Review the current definition format before proposing another update.

This differs from earlier finance writes that lost native metadata. It is not
proof that the eight annotations alone fix every source or that an untouched
copy will work. The pilot explicitly skipped graph execution, so its successful
binding observation does **not** establish graph-runtime acceptance.

After separate materialization approval, follow the
[graph query handoff](graph-query-handoff.md) to verify actual graph keys,
properties, edges, traversal and SQL parity. Keep that gate even when no native
repair was necessary. See [pilot findings](second-industry-pilot.md).
