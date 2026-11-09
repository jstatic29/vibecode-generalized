# Optional phases and final acceptance

These are execution requirements and uncompleted boundaries, not claims that
the current finance build has deployed these features. Follow feature selection
and gate prerequisites; do not broaden the default few-hour path speculatively.

For existing-lakehouse mode, consume the approved data-readiness model and
timestamped SQL baselines through the created lakehouse's approved shortcuts.
Recheck schema, targets, effective runtime/delegated-owner permissions and
freshness before refresh/publication/rehearsal. Import and graph materialization
can copy source data; source read-only permission does not approve that exposure.
Curated outputs need separate approval outside shortcut paths. Never put app or
Planning writes on shortcut targets or label existing data synthetic.

## Semantic model

Load installed `semantic-model-authoring` and inspect actual deployed schema.
The registered modeling MCP supports Fabric workspace models, not offline
PBIP/Desktop. Use a currently supported authoring route and persist/export
definitions. Discover before create; keep model identity stable on updates.

Preserve metric filters/units/grains, calendar/period relationships, date roles,
ratio/null handling and unambiguous single-direction filters where declared.
Reconcile DAX, including selected-quarter filters, against SQL expectations.
Verify credentials and a second viewer/source permissions. A locally authored
definition or successful refresh alone is not model acceptance.

## Fabric Planning

Optional and dependent on the semantic model. Verify current feature and
storage-mode compatibility; do not assume Direct Lake support. Ask before an
Import fallback. Use a dedicated approved writeback database and Planning-owned
destination tables; guide native permissions/destination setup where needed.
Preserve model identity and verify a separately approved scenario write/readback.
Do not claim readiness from a configuration contract.

## Rayfin / Fabric app

Load `rayfin-getting-started`, generated in-project skills and current CLI docs.
Use scenario-owned aggregate views, never source-level entities in the client.
Validate proposed SQL before applying approved views. A live aggregate connector
is the default; snapshot fallback must be explicitly approved and clearly labelled.

App actions use a separate action database from source facts and Planning.
Enforce ownership in the service, not just the UI. Do not imply action writeback
updates ontology, agent or customer source data.

Rayfin dev/up write resources and need applicable approval. Use the current
workspace-specific dry run, no force shortcuts. Verify actual built-bundle
parseability, including the supported lowering of connector decorators, not
just a successful Vite build. Have the operator sign in; do not automate around
authentication gates. Check deployed connector totals and signed-in CRUD
persistence, viewer permissions and service-enforced ownership. Local stubs
are not evidence of deployed behavior.

## Rehearsal and release boundary

Rehearse the approved story: see the exception -> inspect relationships ->
ask a grounded question -> record an owned response. Save links, period/snapshot
labels, expected figures, manual checkpoints, known limitations and recovery.
Run a short health/sample check rather than a heavy suite before presenting.

Gate completion requires the existing accelerator checks and durable evidence.
Keep owner attestation separate from actual tool/query observations; unknown
ontology use, unpublished changes or blocked access cannot be marked passed.
Respect selected optional phases and all prerequisite gates.

The data adapter has a successful live finance build. IQ, semantic model,
Planning and app still require specialist-assisted implementation/acceptance;
generated work packages are not deployment adapters. A full release requires a
successful live full-stack reference and a second-industry run by another
presenter. A few-hour target is not a measured performance guarantee.
