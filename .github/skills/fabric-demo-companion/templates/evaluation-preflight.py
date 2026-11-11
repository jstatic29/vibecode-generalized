"""Notebook cell helper; copy into the reviewed evaluation notebook before use."""

import re


def check_evaluation_destination(spark, context, workspace_id, lakehouse_id,
                                 lakehouse_name, table_name):
    if not workspace_id or not lakehouse_id:
        raise ValueError("Verified workspace and lakehouse IDs are required")
    if (context.get("defaultLakehouseId") != lakehouse_id
            or context.get("defaultLakehouseWorkspaceId") != workspace_id
            or context.get("defaultLakehouseName") != lakehouse_name):
        raise RuntimeError("Unexpected default lakehouse or workspace; refusing evaluation")
    for name in (lakehouse_name, table_name):
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("Use simple, reviewed lakehouse and evaluation table identifiers")
    destinations = tuple(f"`{lakehouse_name}`.`eval_result`.`{name}`"
                         for name in (table_name, table_name + "_steps"))
    legacy = tuple(f"`{lakehouse_name}`.`dbo`.`{name}`"
                   for name in (table_name, table_name + "_steps"))
    for destination in destinations + legacy:
        if spark.catalog.tableExists(destination):
            raise RuntimeError(f"Evaluation table already exists: {destination}; refusing reuse")
    return destinations
