import typer
from aiac.client import AIACClient
from aiac.console import console
from rich.table import Table
import json
from urllib.parse import urlencode

governance_api_app = typer.Typer(help="Governance related commands for AIAC.")


def _is_html_error_blob(text: str) -> bool:
    t = (text or "").lower()
    return "<!doctype html>" in t or "<html" in t


def _friendly_backend_error(prefix: str, error_text: str) -> str:
    text = str(error_text or "")
    lowered = text.lower()
    if (
        "401" in lowered
        or "token_not_valid" in lowered
        or "given token not valid" in lowered
        or "token is expired" in lowered
        or "user_not_found" in lowered
    ):
        return "Session expired or authentication is invalid. Please run `aiac auth login` and try again."
    if "API server is not reachable" in text:
        return text
    if "OperationalError" in text:
        return (
            f"{prefix}: backend database is not ready.\n"
            "Start the API server with migrations:\n"
            "  aiac server run --migrate\n"
            "Then retry the command."
        )
    if _is_html_error_blob(text):
        return (
            f"{prefix}: backend returned an internal server error.\n"
            "Check backend logs with:\n"
            "  aiac server status\n"
            "  type %USERPROFILE%\\.aiac\\server.log"
        )
    return f"{prefix}: {text}"


def _friendly_apply_policy_error(error_text: str) -> str:
    if '"deployment"' in error_text and "does not exist" in error_text:
        return (
            "Deployment not found. Check the deployment ID and try again."
        )
    if '"policy"' in error_text and "does not exist" in error_text:
        return (
            "Policy not found. Check the policy ID and try again."
        )
    if (
        "non_field_errors" in error_text
        and ("already exists" in error_text or "must make a unique set" in error_text)
    ):
        return "This policy is already applied to that deployment."
    return _friendly_backend_error("Failed to apply policy", error_text)


def _friendly_violation_action_error(action: str, error_text: str, violation_id: int) -> str:
    text = str(error_text or "")
    lowered = text.lower()
    if "404" in lowered and "no policyviolation matches" in lowered:
        return (
            f"Violation '{violation_id}' was not found or is not accessible with the current account.\n"
            "Run `aiac auth me` to confirm your account, then run `aiac governance view-violations` and use an ID visible in that same session."
        )
    if "404" in lowered and '"detail":"not found' in lowered:
        return (
            f"Cannot {action} violation: this backend does not expose the `{action}` endpoint yet.\n"
            "Restart/update the API server, then retry."
        )
    if "404" in lowered and "not found" in lowered:
        return (
            f"Violation '{violation_id}' was not found or is not accessible with the current account.\n"
            "Run `aiac auth me` to confirm your account, then run `aiac governance view-violations` and use an ID visible in that same session."
        )
    if "403" in lowered and "access denied" in lowered:
        return (
            f"You don't have permission to {action} this violation.\n"
            "Use an admin account or the owner of the deployment."
        )
    return _friendly_backend_error(f"Failed to {action} violation", text)


def _print_current_account_hint() -> None:
    try:
        user_client = AIACClient(base_path="users")
        resp = user_client.get("/me/")
        payload = resp.json() if resp.text else {}
        if isinstance(payload, dict):
            typer.echo(
                f"Current account: id={payload.get('id', 'N/A')} "
                f"email={payload.get('email', 'N/A')} role={payload.get('role', 'N/A')}"
            )
    except Exception:
        # Best-effort hint only; main command should continue.
        pass


def _print_visible_violation_ids_hint(client: AIACClient, resolved: str, limit: int = 15) -> None:
    """Best-effort helper to show violation IDs visible in current session."""
    try:
        response = client.get(f"/policy-violations/?resolved={resolved}")
        payload = response.json() if response.text else []
        items = payload if isinstance(payload, list) else [payload]
        ids = [item.get("id") for item in items if isinstance(item, dict) and item.get("id") is not None]
        if not ids:
            typer.echo(f"No visible violations found for resolved={resolved} in this session.")
            return
        shown = ids[:limit]
        suffix = " ..." if len(ids) > limit else ""
        typer.echo(f"Visible violation IDs for resolved={resolved}: {shown}{suffix}")
    except Exception:
        # Best-effort hint only.
        pass


def _prompt_manual_rules() -> dict:
    """Prompt for rules interactively as key/value fields."""
    typer.echo("Enter policy rules fields (at least one).")
    typer.echo("Leave rule name empty to finish.")
    rules_data = {}

    while True:
        key = typer.prompt("Rule name", default="", show_default=False).strip()
        if not key:
            if rules_data:
                return rules_data
            typer.echo("At least one rule is required.")
            continue

        raw_value = typer.prompt(
            f"Value for '{key}' (JSON literal or plain text)"
        ).strip()

        try:
            # Allows typed JSON values such as numbers, booleans, arrays, objects.
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            # Plain text is stored as string if value is not valid JSON literal.
            value = raw_value

        rules_data[key] = value


def _build_metadata_template(scope: str) -> dict:
    metadata = {
        "version": "1.0",
        "target": scope,
        "role_permissions": {
            "admin": ["deployment:*", "monitoring:*", "governance:*", "audit:read"],
            "engineer": ["deployment:read", "deployment:write", "monitoring:read"],
            "auditor": ["audit:read"],
        },
    }

    if scope in ("deployment", "both"):
        metadata["deployment"] = {
            "id": "deployment.id",
            "name": "deployment.name",
            "port": "deployment.port",
            "status": "deployment.status",
        }

    if scope in ("monitoring", "both"):
        metadata["drift_monitoring"] = {
            "enabled": True,
            "check_strategy": {
                "type": "request_based",
                "every_n_requests": 1000,
                "interval_minutes": 60,
            },
        }
        metadata["monitoring"] = {"enabled": True}
        metadata["metrics"] = {
            "psi": {"enabled": True, "warning": 0.1, "critical": 0.25},
            "ks_test": {"enabled": True, "p_value_threshold": 0.05},
            "wasserstein": {"enabled": True, "warning": 0.2},
        }

    return metadata


def _prompt_metadata_scope() -> str:
    valid_scopes = {"deployment", "monitoring", "both"}
    while True:
        scope = typer.prompt(
            "Apply policy metadata to (deployment/monitoring/both)",
            default="both",
        ).strip().lower()
        if scope in valid_scopes:
            return scope
        typer.echo("Invalid value. Choose one of: deployment, monitoring, both.")


def _prompt_rules() -> dict:
    """Prompt for metadata template first, then fallback to manual rules."""
    scope = _prompt_metadata_scope()
    metadata = _build_metadata_template(scope)
    typer.echo("Generated metadata template:")
    typer.echo(json.dumps(metadata, indent=2))

    if typer.confirm("Use this metadata as policy rules?", default=True):
        return metadata
    return _prompt_manual_rules()


@governance_api_app.command("create-policy")
def create_policy(
    name: str = typer.Argument(None, help="Policy name."),
    policy_type: str = typer.Argument(None, help="Policy type (deployment or drift)."),
    description: str = typer.Option(
        "",
        "--description",
        "-d",
        help="Optional policy description.",
    ),
    rules: str = typer.Option(
        None,
        "--rules",
        "-r",
        help='Optional JSON object of policy rules, for example \'{"max_latency_ms": 500}\'. If omitted, rules are prompted interactively.',
    ),
):
    """Create a new governance policy."""

    client = AIACClient(base_path="governance")

    try:
        if not name:
            name = typer.prompt("Policy name").strip()
        if not policy_type:
            policy_type = typer.prompt("Policy type (deployment or drift)").strip()
        policy_type = policy_type.strip().lower()
        if policy_type == "monitoring":
            policy_type = "drift"
        if policy_type not in {"deployment", "drift"}:
            typer.echo("Invalid policy type. Use deployment or drift.")
            return

        if rules is None:
            rules_data = _prompt_rules()
        else:
            rules_data = json.loads(rules) if isinstance(rules, str) else rules
        if not isinstance(rules_data, dict):
            typer.echo("Failed to create policy: rules must be a JSON object.")
            return
        if not rules_data:
            typer.echo("Failed to create policy: rules cannot be empty.")
            return

        data = {
            "name": name,
            "policy_type": policy_type,
            "description": description,
            "rules": rules_data,
        }

        while True:
            try:
                response = client.post("/policies/", json=data)
                created = response.json()
                typer.echo(
                    f"Policy '{created.get('name', data['name'])}' created successfully with id {created.get('id')}."
                )
                return
            except Exception as e:
                err = str(e)
                if '"name"' in err and "already exists" in err:
                    typer.echo(f"Policy name '{data['name']}' already exists.")
                    new_name = typer.prompt(
                        "Enter a new policy name",
                        default=f"{data['name']}-1",
                    ).strip()
                    if not new_name:
                        typer.echo("Failed to create policy: policy name cannot be empty.")
                        return
                    data["name"] = new_name
                    continue
                raise
    except json.JSONDecodeError as e:
        typer.echo(f"Failed to create policy: invalid rules JSON ({e.msg}).")
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to create policy", str(e)))

@governance_api_app.command("list-policies")
def list_policies():
    """List all governance policies."""

    client = AIACClient(base_path="governance")
    try:
        response = client.api_request("/policies/")
        policies = response.json()

        table = Table(title="Governance Policies")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Type", style="green")
        table.add_column("Active", style="yellow")
        table.add_column("Owner", style="cyan")
        table.add_column("Created By", style="cyan")
        table.add_column("Created At", style="green")
        table.add_column("Description")
        table.add_column("Rules Preview", style="white")

        for policy in policies:
            rules = policy.get("rules", {})
            rules_preview = json.dumps(rules, ensure_ascii=True)
            if len(rules_preview) > 80:
                rules_preview = f"{rules_preview[:77]}..."
            table.add_row(
                str(policy.get("id", "")),
                str(policy.get("name", "")),
                str(policy.get("policy_type", "")),
                "yes" if policy.get("is_active", False) else "no",
                str(policy.get("user") or ""),
                str(policy.get("created_by") or ""),
                str(policy.get("created_at") or ""),
                str(policy.get("description") or ""),
                rules_preview,
            )

        console.print(table)
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to retrieve policies", str(e)))

@governance_api_app.command("delete-policy")
def delete_policy(policy_id: int):
    """Delete a governance policy by its ID."""

    client = AIACClient(base_path="governance")
    try:
        client.delete(f"/policies/{policy_id}/")
        typer.echo(f"Policy with ID '{policy_id}' deleted successfully.")
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to delete policy", str(e)))

@governance_api_app.command("view-violations")
def view_violations():
    """View all policy violations."""

    client = AIACClient(base_path="governance")
    try:
        response = client.get("/policy-violations/")
        violations = response.json()
        if not violations:
            typer.echo("No violations found yet.")
            typer.echo("Tips:")
            typer.echo("- Run `aiac governance run-policy-engine` to evaluate current policies.")
            typer.echo("- Ensure policies are applied to deployments with `aiac governance apply-policy`.")
            typer.echo("- Use `aiac governance debug-policy-engine --policy <id>` for detailed evaluation.")
            return
        table = Table(title="Policy Violations")
        table.add_column("ID", style="white", no_wrap=True)
        table.add_column("Deployment", style="cyan", no_wrap=True)
        table.add_column("Policy", style="magenta")
        table.add_column("Type", style="green")
        table.add_column("Severity", style="yellow")
        table.add_column("Resolved")

        for violation in violations:
            metrics = violation.get("violation_metrics", violation)
            table.add_row(
                str(metrics.get("id", "")),
                str(metrics.get("deployment", "")),
                str(metrics.get("policy", "")),
                str(metrics.get("violation_type", "")),
                str(metrics.get("severity", "")),
                str(metrics.get("resolved", "")),
            )
        console.print(table)
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to retrieve violations", str(e)))


@governance_api_app.command("resolve-violation")
def resolve_violation(
    violation_id: int = typer.Option(..., prompt=True, help="Violation ID to mark as resolved."),
):
    """Resolve a policy violation."""
    client = AIACClient(base_path="governance")
    _print_current_account_hint()
    try:
        response = client.post(f"/policy-violations/{violation_id}/resolve/", json={})
        payload = response.json() if response.text else {}
        typer.echo(payload.get("message", f"Violation {violation_id} resolved successfully."))
    except Exception as e:
        error_text = str(e)
        if "404" in error_text:
            try:
                # If detail endpoint exists, action endpoint is likely missing on backend.
                client.get(f"/policy-violations/{violation_id}/")
                typer.echo(
                    "Resolve endpoint is not available on this backend version.\n"
                    "Update/restart the API server to a version that supports violation actions."
                )
                return
            except Exception:
                pass
        typer.echo(_friendly_violation_action_error("resolve", error_text, violation_id))
        if "not found" in error_text.lower() or "no policyviolation matches" in error_text.lower():
            _print_visible_violation_ids_hint(client, resolved="false")


@governance_api_app.command("reopen-violation")
def reopen_violation(
    violation_id: int = typer.Option(..., prompt=True, help="Violation ID to reopen."),
):
    """Reopen a resolved policy violation."""
    client = AIACClient(base_path="governance")
    _print_current_account_hint()
    try:
        response = client.post(f"/policy-violations/{violation_id}/reopen/", json={})
        payload = response.json() if response.text else {}
        typer.echo(payload.get("message", f"Violation {violation_id} reopened successfully."))
    except Exception as e:
        error_text = str(e)
        if "404" in error_text:
            try:
                # If detail endpoint exists, action endpoint is likely missing on backend.
                client.get(f"/policy-violations/{violation_id}/")
                typer.echo(
                    "Reopen endpoint is not available on this backend version.\n"
                    "Update/restart the API server to a version that supports violation actions."
                )
                return
            except Exception:
                pass
        typer.echo(_friendly_violation_action_error("reopen", error_text, violation_id))
        if "not found" in error_text.lower() or "no policyviolation matches" in error_text.lower():
            _print_visible_violation_ids_hint(client, resolved="true")


@governance_api_app.command("resolve-all-violations")
def resolve_all_violations(
    deployment_id: int = typer.Option(None, "--deployment-id", help="Optional deployment ID filter."),
    policy_id: int = typer.Option(None, "--policy-id", help="Optional policy ID filter."),
):
    """Resolve all unresolved violations, optionally filtered by deployment or policy."""
    client = AIACClient(base_path="governance")
    payload = {}
    if deployment_id is not None:
        payload["deployment"] = deployment_id
    if policy_id is not None:
        payload["policy"] = policy_id

    try:
        response = client.post("/policy-violations/resolve-all/", json=payload)
        body = response.json() if response.text else {}
        typer.echo(body.get("message", "Bulk violation resolution completed."))
        if body.get("resolved_count") is not None:
            typer.echo(f"resolved_count: {body.get('resolved_count')}")
    except Exception as e:
        error_text = str(e)
        lowered = error_text.lower()
        # Fallback path for older backends where resolve-all action is not available yet.
        if "405" in lowered or ("404" in lowered and "resolve-all" in lowered):
            try:
                query_parts = ["resolved=false"]
                if deployment_id is not None:
                    query_parts.append(f"deployment={deployment_id}")
                if policy_id is not None:
                    query_parts.append(f"policy={policy_id}")
                query = "&".join(query_parts)
                list_resp = client.get(f"/policy-violations/?{query}")
                items = list_resp.json()
                violations = items if isinstance(items, list) else [items]
                if not violations:
                    typer.echo("No unresolved violations matched the filter.")
                    return

                resolved_count = 0
                for item in violations:
                    vid = item.get("id")
                    if vid is None:
                        continue
                    try:
                        client.post(f"/policy-violations/{vid}/resolve/", json={})
                        resolved_count += 1
                    except Exception:
                        # Continue resolving others; show summary at the end.
                        pass

                typer.echo(
                    f"Bulk endpoint is unavailable on this backend. "
                    f"Resolved {resolved_count} violation(s) using per-item fallback."
                )
                return
            except Exception as fallback_error:
                typer.echo(
                    _friendly_backend_error(
                        "Failed to resolve violations in bulk",
                        str(fallback_error),
                    )
                )
                return

        typer.echo(_friendly_backend_error("Failed to resolve violations in bulk", error_text))

@governance_api_app.command("metrics")
def violation_metrics(
    deployment_id: int = typer.Option(None, "--deployment-id", help="Optional deployment ID filter."),
    severity: str = typer.Option("", "--severity", help="Optional severity filter: low|medium|high."),
    resolved: str = typer.Option(
        "all",
        "--resolved",
        help="Filter by resolution state: all|true|false.",
    ),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """View aggregated policy violation metrics."""

    client = AIACClient(base_path="governance")
    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return

        resolved_opt = (resolved or "all").strip().lower()
        if resolved_opt not in {"all", "true", "false"}:
            typer.echo("Invalid --resolved value. Use: all, true, or false.")
            return

        severity_opt = (severity or "").strip().lower()
        if severity_opt and severity_opt not in {"low", "medium", "high"}:
            typer.echo("Invalid --severity value. Use: low, medium, or high.")
            return

        params = []
        if deployment_id is not None:
            params.append(f"deployment={deployment_id}")
        if severity_opt:
            params.append(f"severity={severity_opt}")
        if resolved_opt != "all":
            params.append(f"resolved={resolved_opt}")
        query = f"?{'&'.join(params)}" if params else ""

        response = client.get(f"/policy-violations/metrics/{query}")
        metrics = response.json() if response.text else {}

        if fmt == "json":
            typer.echo(json.dumps(metrics, indent=2, default=str))
            return

        table = Table(title="Policy Violation Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Total Violations", str(metrics.get("total_violations", 0)))
        table.add_row("Unresolved Violations", str(metrics.get("unresolved_violations", 0)))
        table.add_row("Resolved Violations", str(metrics.get("resolved_violations", 0)))
        table.add_row("High Severity Violations", str(metrics.get("high_severity_violations", 0)))
        table.add_row("Medium Severity Violations", str(metrics.get("medium_severity_violations", 0)))
        table.add_row("Low Severity Violations", str(metrics.get("low_severity_violations", 0)))
        console.print(table)

        if int(metrics.get("total_violations", 0) or 0) == 0:
            typer.echo("No violations match the current filters.")
            typer.echo("Tips:")
            typer.echo("- Run `aiac governance run-policy-engine` to generate fresh violations.")
            typer.echo("- Use `aiac governance view-violations` to inspect violation details.")
            typer.echo("- Review applied policies with `aiac governance list-policies`.")
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to retrieve violation metrics", str(e)))


@governance_api_app.command("run-policy-engine")
def run_policy_engine_cmd():
    """Trigger policy engine execution immediately."""
    client = AIACClient(base_path="governance")
    try:
        response = client.post("/policy-violations/run-engine/", json={})
        payload = response.json()
        typer.echo(payload.get("message", "Policy engine triggered successfully."))
        if payload.get("task_id"):
            typer.echo(f"task_id: {payload.get('task_id')}")
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to run policy engine", str(e)))


@governance_api_app.command("debug-policy-engine")
def debug_policy_engine(
    policy_id: int = typer.Option(None, "--policy", "-p", help="Policy ID to inspect."),
    deployment_id: int = typer.Option(None, "--deployment", "-d", help="Optional deployment ID filter."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max logs to inspect (1-200)."),
):
    """Debug policy evaluation to understand why violations are or are not produced."""
    client = AIACClient(base_path="governance")
    try:
        if policy_id is None:
            policy_id = typer.prompt("Policy ID", type=int)

        params = {"policy": policy_id, "limit": max(1, min(limit, 200))}
        if deployment_id is not None:
            params["deployment"] = deployment_id
        endpoint = f"/policy-violations/debug-engine/?{urlencode(params)}"
        response = client.get(endpoint)
        payload = response.json()

        summary = payload.get("summary", {})
        typer.echo(
            f"Policy {payload.get('policy_id')} ({payload.get('policy_name')}) target={payload.get('target')}"
        )
        typer.echo(
            f"Evaluated={summary.get('evaluated_logs', 0)} | "
            f"Violations={summary.get('violations', 0)} | "
            f"Matched={summary.get('matched', 0)} | "
            f"ScopeSkipped={summary.get('scope_skipped', 0)}"
        )

        assigned = payload.get("assigned_deployments", [])
        typer.echo(f"Assigned deployments: {assigned if assigned else 'none'}")

        note = payload.get("note")
        if note:
            typer.echo(note)

        results = payload.get("results", [])
        if not results:
            return

        table = Table(title="Policy Engine Debug")
        table.add_column("Log ID", style="cyan", no_wrap=True)
        table.add_column("Deployment", style="magenta")
        table.add_column("Action", style="green")
        table.add_column("Service")
        table.add_column("Status", style="yellow")
        table.add_column("Reason")
        table.add_column("Timestamp", style="green")

        for row in results:
            table.add_row(
                str(row.get("log_id", "")),
                str(row.get("deployment_id", "")),
                str(row.get("action", "")),
                str(row.get("service", "")),
                str(row.get("status", "")),
                str(row.get("reason", "")),
                str(row.get("timestamp", "")),
            )
        console.print(table)
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to debug policy engine", str(e)))


@governance_api_app.command("policy-insights")
def policy_insights(
    policy_id: int = typer.Option(None, "--policy", "-p", help="Optional policy ID filter."),
    days: int = typer.Option(7, "--days", "-d", help="Lookback window in days (1-90)."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or csv."),
):
    """Advanced governance insights: coverage, risk, and recommendations."""
    client = AIACClient(base_path="governance")
    try:
        params = {"days": max(1, min(days, 90))}
        if policy_id is not None:
            params["policy"] = policy_id
        endpoint = f"/policies/insights/?{urlencode(params)}"
        response = client.get(endpoint)
        payload = response.json()

        items = payload.get("items", [])
        if not items:
            typer.echo("No policy insights found.")
            return

        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "csv"}:
            typer.echo("Invalid format. Use 'table' or 'csv'.")
            return

        if fmt == "csv":
            headers = [
                "policy_id",
                "policy_name",
                "policy_type",
                "target",
                "is_active",
                "assignment_count",
                "recent_violations",
                "unresolved_violations",
                "high_unresolved_violations",
                "risk_level",
                "deployment_ids",
                "recommendations",
            ]
            typer.echo(",".join(headers))
            for item in items:
                row = [
                    str(item.get("policy_id", "")),
                    str(item.get("policy_name", "")).replace(",", ";"),
                    str(item.get("policy_type", "")),
                    str(item.get("target", "")),
                    str(item.get("is_active", "")),
                    str(item.get("assignment_count", 0)),
                    str(item.get("recent_violations", 0)),
                    str(item.get("unresolved_violations", 0)),
                    str(item.get("high_unresolved_violations", 0)),
                    str(item.get("risk_level", "")),
                    "|".join(str(x) for x in item.get("deployment_ids", [])),
                    "|".join(str(x).replace(",", ";") for x in item.get("recommendations", [])),
                ]
                typer.echo(",".join(row))
            return

        typer.echo(
            f"Policy insights (days={payload.get('days')}, policies={payload.get('policy_count')})"
        )

        table = Table(title="Governance Policy Insights")
        table.add_column("Policy ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Target", style="green")
        table.add_column("Assignments", style="yellow")
        table.add_column("Recent Viol.", style="yellow")
        table.add_column("Unresolved", style="yellow")
        table.add_column("High Unres.", style="red")
        table.add_column("Risk", style="bold")

        for item in items:
            table.add_row(
                str(item.get("policy_id", "")),
                str(item.get("policy_name", "")),
                str(item.get("target", "")),
                str(item.get("assignment_count", 0)),
                str(item.get("recent_violations", 0)),
                str(item.get("unresolved_violations", 0)),
                str(item.get("high_unresolved_violations", 0)),
                str(item.get("risk_level", "")),
            )
        console.print(table)

        typer.echo("Recommendations:")
        for item in items:
            recommendations = item.get("recommendations", [])
            if not recommendations:
                continue
            typer.echo(f"- Policy {item.get('policy_id')} ({item.get('policy_name')}):")
            for rec in recommendations:
                typer.echo(f"  * {rec}")
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to get policy insights", str(e)))


@governance_api_app.command("apply-policy")
def apply_policy(
    policy_id: int = typer.Argument(None, help="Policy ID."),
    deployment_id: int = typer.Argument(
        None,
        help="Deployment ID. If omitted, you will be prompted.",
    ),
):
    """Apply a policy to a deployment."""
    client = AIACClient(base_path="governance")
    if policy_id is None:
        policy_id = typer.prompt("Policy ID", type=int)
    if deployment_id is None:
        deployment_id = typer.prompt("Enter deployment ID", type=int)
    data = {
        "policy": policy_id, "deployment": deployment_id
    }
    try:
        response = client.post("/policy-assignments/", json=data)
        payload = response.json()
        typer.echo(f"Policy '{policy_id}' applied to deployment '{deployment_id}' successfully.")
        typer.echo(f"applied_at: {payload.get('applied_at')}")
        applied_by_username = payload.get("applied_by_username")
        applied_by_id = payload.get("applied_by")
        if applied_by_username:
            typer.echo(f"applied_by: {applied_by_username}")
        else:
            typer.echo(f"applied_by: {applied_by_id}")
    except Exception as e:
        typer.echo(_friendly_apply_policy_error(str(e)))




@governance_api_app.command("alert-logs")
def alert_logs():
    """View alert logs for policy violations."""

    client = AIACClient(base_path="governance")
    try:
        response = client.get("/alerts/")
        logs = response.json()
        if not logs:
            typer.echo("No alert logs found.")
            return
        table = Table(title="Alert Logs")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Policy Violation", style="magenta")
        table.add_column("Message")
        table.add_column("Sent", style="yellow")
        table.add_column("Timestamp", style="green")

        for log in logs:
            table.add_row(
                str(log.get("id", "")),
                str(log.get("policy_violation", "")),
                str(log.get("message", "")),
                str(log.get("sent", "")),
                str(log.get("timestamp", "")),
            )
        console.print(table)
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to retrieve alert logs", str(e)))
