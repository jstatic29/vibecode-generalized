"""Small durable-job adapter. No Livy, destructive resets or automatic POST retries."""

import base64
import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import DemoError, existing_mode
from .state import audit, now, read, require_gate, save


API = "https://api.fabric.microsoft.com"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, skill="spark-cli"):
        self.opener = urllib.request.build_opener(NoRedirect())
        self.skill = skill

    def request(self, method, path, body=None):
        url = urllib.parse.urljoin(API + "/", path)
        parsed = urllib.parse.urlparse(url)
        if (parsed.scheme != "https" or parsed.netloc != "api.fabric.microsoft.com"
                or parsed.username or parsed.password):
            raise DemoError("Refusing to send a token outside the public Fabric API")
        az = shutil.which("az")
        if not az:
            raise DemoError("Azure CLI is required for Fabric operations; install it and run az login")
        auth = subprocess.run(
            [az, "account", "get-access-token", "--resource", API,
             "--query", "accessToken", "--output", "tsv"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if auth.returncode != 0 or not auth.stdout.strip():
            raise DemoError("Azure CLI authentication failed; run az login for the approved target tenant")
        request = urllib.request.Request(
            url, method=method,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={"Authorization": f"Bearer {auth.stdout.strip()}",
                     "Content-Type": "application/json", "x-ms-fabric-skill": self.skill},
        )
        try:
            with self.opener.open(request, timeout=60) as response:
                text = response.read().decode("utf-8")
                body = json.loads(text) if text else {}
                if body is None and response.status in {202, 204}:
                    body = {}
                if not isinstance(body, dict):
                    raise ValueError("Fabric response must be an object or an empty async response")
                return response.status, dict(response.headers), body
        except urllib.error.HTTPError as exc:
            # Do not log request headers, tokens or potentially sensitive response bodies.
            raise DemoError(f"Fabric {method} failed with HTTP {exc.code}; "
                            "inspect the operation in Fabric before retrying any write") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise DemoError("Fabric response unavailable or unreadable. A write may have succeeded; "
                            "resume using persisted operation state instead of resubmitting.") from exc

    def listing(self, path):
        values = []
        seen = set()
        while path:
            if path in seen:
                raise DemoError("Fabric returned a repeated pagination link")
            seen.add(path)
            _, _, body = self.request("GET", path)
            values.extend(body.get("value", []))
            next_path = body.get("continuationUri")
            if not next_path and body.get("continuationToken"):
                parsed = urllib.parse.urlsplit(path)
                query = urllib.parse.parse_qs(parsed.query)
                query["continuationToken"] = [body["continuationToken"]]
                next_path = urllib.parse.urlunsplit((
                    parsed.scheme, parsed.netloc, parsed.path,
                    urllib.parse.urlencode(query, doseq=True), parsed.fragment,
                ))
            path = next_path
        return values


def unique(values, name, label):
    matches = [item for item in values if item.get("displayName") == name]
    if len(matches) > 1:
        raise DemoError(f"Multiple {label} items named {name!r}; resolve duplicates explicitly")
    return matches[0] if matches else None


def header(headers, name):
    return next((value for key, value in headers.items() if key.lower() == name.lower()), None)


def preflight(config, client):
    workspace = unique(client.listing("/v1/workspaces"), config["deployment"]["workspace_name"], "workspace")
    if not workspace:
        raise DemoError("Approved workspace not found; this tool does not create or choose a workspace")
    capacity_id = workspace.get("capacityId")
    if not capacity_id:
        raise DemoError("Workspace has no assigned capacity")
    capacity = next((row for row in client.listing("/v1/capacities") if row["id"] == capacity_id), None)
    if not capacity or capacity.get("state") != "Active":
        raise DemoError("Assigned capacity is not visible and Active; ask its administrator")
    return workspace


def ensure_item(client, root, state, workspace_id, item_type, name, body, timeout, require_new=False):
    resources = state["resources"]
    key = item_type.lower()
    path = f"/v1/workspaces/{workspace_id}/items"
    operation = resources.get(f"{key}_operation")
    if operation:
        poll_operation(client, operation, timeout)
        del resources[f"{key}_operation"]
        resources[f"{key}_operation_completed"] = True
        save(Path(root) / "state.json", state)
    items = [row for row in client.listing(path) if row.get("type") == item_type]
    existing = unique(items, name, item_type)
    if existing:
        if require_new and not resources.get(f"{key}_attempted"):
            raise DemoError(f"{item_type} already exists without this run's creation intent; "
                            "choose a new dedicated demo lakehouse name")
        # A notebook with our unique name is reusable only after a recorded creation attempt.
        if item_type == "Notebook" and not resources.get(f"{key}_attempted"):
            raise DemoError("Notebook name already exists without this run's creation intent; refusing to reuse")
        saved = resources.get(f"{key}_id")
        if saved and saved != existing["id"]:
            raise DemoError(f"{item_type} identity changed since approval; investigate before continuing")
        resources[f"{key}_id"] = existing["id"]
        save(Path(root) / "state.json", state)
        return existing["id"]
    if resources.get(f"{key}_id"):
        raise DemoError(f"Previously recorded {item_type} is missing; refusing to recreate automatically")
    if resources.get(f"{key}_operation_completed"):
        raise DemoError(f"{item_type} operation finished but item is not visible; resume later")
    if resources.get(f"{key}_attempted"):
        raise DemoError(f"{item_type} create outcome is ambiguous; inspect Fabric. No duplicate POST will be sent")
    resources[f"{key}_attempted"] = now()
    save(Path(root) / "state.json", state)
    status, headers, result = client.request("POST", path, dict(body, displayName=name, type=item_type))
    if result.get("id") and status != 202:
        resources[f"{key}_id"] = result["id"]
    elif status == 202:
        operation = header(headers, "Location")
        if not operation:
            raise DemoError(f"{item_type} create returned 202 without Location; inspect Fabric")
        resources[f"{key}_operation"] = operation
    else:
        raise DemoError(f"Unexpected {item_type} create response: HTTP {status}")
    save(Path(root) / "state.json", state)
    return ensure_item(client, root, state, workspace_id, item_type, name, body, timeout, require_new)


def poll_operation(client, url, timeout):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme == "https"
            and re.fullmatch(r"wabi-[a-z0-9-]+\.analysis\.windows\.net", parsed.netloc)
            and re.fullmatch(r"/v1/operations/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
                             r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", parsed.path)
            and not parsed.query and not parsed.fragment):
        # Preserve the operation identity without sending credentials to its regional host.
        url = parsed.path
    deadline = time.monotonic() + timeout
    while True:
        _, _, body = client.request("GET", url)
        status = body.get("status")
        if status == "Succeeded":
            return
        if status in {"Failed", "Cancelled"}:
            raise DemoError(f"Fabric operation {status}; inspect in portal, no automatic retry")
        if time.monotonic() >= deadline:
            raise DemoError("Local polling deadline reached; resume the same run to monitor its saved operation")
        time.sleep(10)


def deploy_data(root, timeout=1800, client=None):
    config, state = read(root)
    if existing_mode(config):
        raise DemoError("deploy-data is prohibited in existing-lakehouse mode; use setup-lakehouse "
                        "then manual shortcuts and read-only assessment")
    if state["gates"]["data-build"]["status"] == "complete":
        return {"status": "already-complete", "job_id": state["resources"]["job_id"]}
    require_gate(state, "data-build", approved=True)
    client = client or Client()
    workspace = preflight(config, client)
    wid = workspace["id"]
    resources = state["resources"]
    if resources.get("workspace_id") and resources["workspace_id"] != wid:
        raise DemoError("Workspace identity changed since this run began")
    resources["workspace_id"] = wid
    save(Path(root) / "state.json", state)
    lakehouse = ensure_item(
        client, root, state, wid, "Lakehouse", config["deployment"]["lakehouse_name"],
        {"creationPayload": {"enableSchemas": True}}, timeout,
    )
    notebook = json.loads((Path(root) / "notebooks" / "build_demo.ipynb").read_text(encoding="utf-8"))
    notebook["metadata"]["dependencies"] = {"lakehouse": {
        "default_lakehouse": lakehouse,
        "default_lakehouse_name": config["deployment"]["lakehouse_name"],
        "default_lakehouse_workspace_id": wid,
    }}
    name = f"nb_{config['deployment']['schema']}_{state['config_hash'][:12]}"
    payload = base64.b64encode(json.dumps(notebook).encode("utf-8")).decode("ascii")
    nbid = ensure_item(client, root, state, wid, "Notebook", name, {
        "definition": {"format": "ipynb", "parts": [
            {"path": "notebook-content.ipynb", "payloadType": "InlineBase64", "payload": payload}
        ]},
    }, timeout)
    job_path = f"/v1/workspaces/{wid}/items/{nbid}/jobs/instances"
    if not resources.get("job_id"):
        jobs = client.listing(job_path)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        candidates = []
        for job in jobs:
            start = job.get("startTimeUtc")
            recent = False
            if start:
                try:
                    recent = datetime.fromisoformat(start.replace("Z", "+00:00")) >= cutoff
                except (ValueError, TypeError) as exc:
                    raise DemoError("Fabric returned an invalid job start timestamp; inspect job history") from exc
            if job.get("status") in {"NotStarted", "InProgress"} or recent or resources.get("job_attempted"):
                candidates.append(job)
        if len(candidates) > 1:
            raise DemoError("Multiple possible notebook runs; inspect and reconcile the saved job ID")
        if candidates:
            resources["job_id"] = candidates[0]["id"]
            save(Path(root) / "state.json", state)
        elif resources.get("job_attempted"):
            raise DemoError("Job submission outcome is ambiguous; inspect Fabric before any resubmission")
        else:
            resources["job_attempted"] = now()
            save(Path(root) / "state.json", state)
            _, headers, body = client.request("POST", job_path + "?jobType=RunNotebook", {
                "executionData": {"configuration": {"useStarterPool": True, "defaultLakehouse": {
                    "id": lakehouse, "name": config["deployment"]["lakehouse_name"], "workspaceId": wid,
                }}},
            })
            location = header(headers, "Location")
            job_id = body.get("id") or (urllib.parse.urlparse(location).path.rstrip("/").split("/")[-1]
                                        if location else None)
            if not job_id:
                raise DemoError("Run submitted without readable job ID; resume to discover it, never repeat POST")
            resources["job_id"] = job_id
            save(Path(root) / "state.json", state)
    deadline = time.monotonic() + timeout
    while True:
        _, _, result = client.request("GET", job_path + "/" + resources["job_id"])
        status = result.get("status")
        if status == "Completed":
            state["gates"]["data-build"].update(status="complete", completed_at=now(),
                                               verification="notebook-job-with-embedded-assertions")
            audit(root, state, "complete-job", "data-build", job_id=resources["job_id"])
            return {"status": "Completed", "job_id": resources["job_id"]}
        if status in {"Failed", "Cancelled", "Deduped"}:
            audit(root, state, "job-stopped", "data-build", status=status, job_id=resources["job_id"])
            raise DemoError(f"Notebook {status}. Inspect diagnostics; no automatic reset or new run")
        if status not in {"NotStarted", "InProgress"}:
            raise DemoError(f"Unrecognized notebook status {status!r}; inspect Fabric")
        if time.monotonic() >= deadline:
            raise DemoError(f"Job {resources['job_id']} remains {status}. "
                            "Local monitoring stopped, not the remote job. Run deploy-data again to resume.")
        time.sleep(20)
