"""Read-only CLI checks; skill capability and MCP checks remain host-assisted."""

import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

from .config import DemoError
from .fabric import API, Client, preflight


def command_json(tool, arguments):
    executable = shutil.which(tool)
    if not executable:
        return "missing", None
    try:
        result = subprocess.run(
            [executable, *arguments], capture_output=True, text=True,
            timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "failed", None
    if result.returncode:
        return "failed", None
    try:
        return "ok", json.loads(result.stdout)
    except (ValueError, TypeError):
        return "invalid", None


def version(tool, arguments):
    executable = shutil.which(tool)
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, *arguments], capture_output=True, text=True,
            timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.fullmatch(r"git version (\d+\.\d+(?:\.\d+)?)(?:\.windows\.\d+)?\s*",
                         result.stdout) if result.returncode == 0 else None
    return match[1] if match else None


def check(workspace=None, data_mode=None, semantic_model=False, app=False, fabriciq=False,
          client=None):
    checks = []

    def add(name, status, phase, detail, **evidence):
        checks.append(dict(check=name, status=status, phase=phase, detail=detail, **evidence))

    add("python", "passed" if sys.version_info >= (3, 11) else "blocked",
        "local preparation", "Python 3.11+ required.",
        version=".".join(map(str, sys.version_info[:3])))
    add("accelerator", "passed", "local preparation", "Accelerator CLI loaded.")
    git_version = version("git", ["--version"])
    add("git", "passed" if git_version else "blocked", "repository",
        "Git version check completed." if git_version else "Install or repair Git with approval.",
        version=git_version)
    status, azure = command_json("az", ["version", "-o", "json"])
    az_version = azure.get("azure-cli") if status == "ok" and isinstance(azure, dict) else None
    valid_az = isinstance(az_version, str) and re.fullmatch(r"\d+\.\d+\.\d+", az_version)
    add("azure-cli", "passed" if valid_az else "blocked", "Fabric access",
        "Azure CLI version checked." if valid_az else "Install or repair Azure CLI with approval.",
        version=az_version if valid_az else None)

    status, plugins = command_json("copilot", ["plugin", "list", "--json"])
    valid_plugins = status == "ok" and isinstance(plugins, list) and all(
        isinstance(p, dict) and isinstance(p.get("name"), str)
        and isinstance(p.get("enabled"), bool) for p in plugins)
    if valid_plugins:
        # Allowlist identifiers and versions; never echo raw plugin data or paths.
        selected = []
        wanted = {"fabric-skills", "skills-for-fabric"}
        if semantic_model:
            wanted.add("powerbi-authoring")
        if app:
            wanted.add("rayfin")
        for plugin in plugins:
            if plugin["name"] not in wanted:
                continue
            value = plugin.get("version")
            selected.append({
                "name": plugin["name"], "enabled": plugin["enabled"],
                "version": value if isinstance(value, str) and
                re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", value) else None,
            })
        fabric_enabled = any(p["enabled"] and p["name"] in
                             {"fabric-skills", "skills-for-fabric"} for p in selected)
        add("fabric-plugins", "passed" if fabric_enabled else "blocked", "Fabric skills",
            "Inventory only; Copilot must load skills and inspect their capabilities.",
            plugins=selected)
        if app:
            enabled = any(p["name"] == "rayfin" and p["enabled"] for p in selected)
            add("app-plugin", "passed" if enabled else "blocked", "app",
                "Rayfin plugin inventory; capability checks still required.")
    else:
        add("fabric-plugins", "unverified", "Fabric skills",
            "Structured plugin inventory unavailable; check plugins in the current host.")

    if valid_az:
        status, account = command_json("az", ["account", "show", "--query", "user.type", "-o", "json"])
        signed_in = status == "ok" and account in ("user", "servicePrincipal")
        add("azure-sign-in", "passed" if signed_in else "blocked", "Fabric access",
            "An Azure account is available; confirm the intended tenant privately."
            if signed_in else "Azure account check failed; operator sign-in required.")
        status, expires = command_json("az", [
            "account", "get-access-token", "--resource", API,
            "--query", "expires_on", "-o", "json",
        ]) if signed_in else ("failed", None)
        token_valid = (status == "ok" and isinstance(expires, (int, str))
                       and str(expires).isdigit() and int(expires) > time.time())
        add("fabric-token", "passed" if token_valid else "blocked", "Fabric REST",
            "Unexpired Fabric token acquired without returning its value."
            if token_valid else "Token check failed; operator must review authentication.")
    else:
        token_valid = False
        add("azure-sign-in", "unverified", "Fabric access", "Azure CLI prerequisite blocked.")
        add("fabric-token", "unverified", "Fabric REST", "Azure CLI prerequisite blocked.")

    if workspace and token_valid:
        try:
            preflight({"deployment": {"workspace_name": workspace}}, client or Client(
                skill="onelake-catalog-cli" if data_mode == "existing-lakehouse" else "spark-cli"))
        except (DemoError, OSError, ValueError, subprocess.SubprocessError):
            add("workspace-capacity", "blocked", "Fabric target",
                "Target discovery/capacity check failed; review access, name and active capacity.")
        else:
            add("workspace-capacity", "passed", "Fabric target",
                "Selected workspace is visible and assigned to a visible Active capacity; "
                "write permissions and preview features are not established.")
    else:
        add("workspace-capacity", "unverified", "Fabric target",
            "Select a workspace and pass Azure authentication before target checks.")

    for name, phase, required, detail in (
        ("skill-capabilities", "Fabric skills", True,
         "Copilot must load current skills, verify generation-2 ontology support and "
         "check file/shell/web tools; names and plugin inventory are insufficient."),
        ("sql-endpoint-mcp", "SQL reconciliation", True,
         "Copilot must discover the MCP tool and run an identity-only query on the selected "
         "endpoint; report identity_match only, never the username."),
        ("fabriciq-mcp", "Power BI consumption", fabriciq,
         "Copilot must independently test authenticated artifact discovery when needed."),
        ("modeling-mcp", "semantic model", semantic_model,
         "Copilot must independently verify selected model read access; "
         "an empty connection list does not prove authentication."),
        ("source-read-only", "existing-data assessment", data_mode == "existing-lakehouse",
         "Owner evidence must establish effective read-only permissions for every execution "
         "identity; an admin connection is not proof. Never use a write probe."),
        ("app-tooling", "app", app,
         "Copilot must check selected Rayfin tooling without starting dev/up."),
    ):
        add(name, "unverified" if required else "not applicable", phase,
            detail if required else "Not selected for this check; recheck if scope changes.")
    return {
        "kind": "prerequisite-check", "version": 1,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "fabric_writes": False, "checks": checks,
        "blocked": any(c["status"] == "blocked" for c in checks),
        "complete": False,
        "limitation": "CLI observations only, not approval or end-to-end readiness. "
                      "Copilot must complete host/MCP/permission checks independently. "
                      "No usernames, tenant/resource IDs, tokens or raw command output are saved.",
    }
