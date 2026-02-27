import typer
from aiac.client import AIACClient
from  aiac.console import console , print_message , print_warning  , print_info
from rich.table import Table
import json
import csv
import uuid
import time


table = Table()

monitoring_api_app = typer.Typer(help = "monitoring commands")


def _is_html_error_blob(text: str) -> bool:
    t = (text or "").lower()
    return "<!doctype html>" in t or "<html" in t


def _friendly_backend_error(prefix: str, error_text: str) -> str:
    text = str(error_text or "")
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


def _friendly_detect_drift_error(error_text: str, model_version_id: int) -> str:
    if "Insufficient data for drift detection" in error_text:
        return (
            f"Not enough data to run drift detection for model_version_id {model_version_id}. "
            "Add baseline sample_data or upload at least 20 samples using "
            "`monitoring samples`, then run `monitoring detect-drift` again."
        )
    if "404" in error_text and "model_version" in error_text.lower():
        return f"Model version {model_version_id} was not found. Check the ID and try again."
    return _friendly_backend_error(
        f"Failed to detect drift for model_version_id {model_version_id}",
        error_text,
    )


def _friendly_deploy_stats_error(error_text: str, deployment_id: int) -> str:
    if "404" in error_text and "Deployment not found" in error_text:
        return (
            f"Deployment {deployment_id} was not found. "
            "Run `deployment list-deployments` and use a valid deployment ID."
        )
    return _friendly_backend_error(
        f"Failed to fetch stats for deployment_id {deployment_id}",
        error_text,
    )


def _friendly_alert_error(error_text: str, deployment_id: int) -> str:
    if "404" in error_text and "Deployment not found" in error_text:
        return (
            f"Deployment {deployment_id} was not found. "
            "Run `deployment list-deployments` and use a valid deployment ID."
        )
    return _friendly_backend_error(
        f"Failed to fetch alerts for deployment_id {deployment_id}",
        error_text,
    )


def _friendly_health_report_error(error_text: str, deployment_id: int) -> str:
    if "404" in error_text and "Deployment not found" in error_text:
        return (
            f"Deployment {deployment_id} was not found. "
            "Run `deployment list-deployments` and use a valid deployment ID."
        )
    if "403" in error_text and "Access denied" in error_text:
        return "Access denied for this deployment health report."
    return _friendly_backend_error(
        f"Failed to fetch health report for deployment_id {deployment_id}",
        error_text,
    )


def _friendly_cost_intelligence_error(error_text: str, deployment_id: int) -> str:
    if "404" in error_text and "Deployment not found" in error_text:
        return (
            f"Deployment {deployment_id} was not found. "
            "Run `deployment list-deployments` and use a valid deployment ID."
        )
    if "403" in error_text and "Access denied" in error_text:
        return "Access denied for this deployment cost report."
    return _friendly_backend_error(
        f"Failed to fetch cost intelligence for deployment_id {deployment_id}",
        error_text,
    )


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_stats_health(
    cpu_usage: float,
    ram_usage: float,
    latency_ms: float,
    error_rate_pct: float,
    cpu_warn: float,
    ram_warn: float,
    latency_warn: float,
    error_rate_warn: float,
) -> tuple[str, list[str]]:
    warnings = []
    if cpu_usage >= cpu_warn:
        warnings.append(f"High CPU ({cpu_usage:.2f}%)")
    if ram_usage >= ram_warn:
        warnings.append(f"High RAM ({ram_usage:.2f}%)")
    if latency_ms >= latency_warn:
        warnings.append(f"High Latency ({latency_ms:.2f} ms)")
    if error_rate_pct >= error_rate_warn:
        warnings.append(f"High Error Rate ({error_rate_pct:.2f}%)")
    return ("warning" if warnings else "healthy", warnings)


def _resolve_drift_thresholds(
    profile: str,
    kl_threshold,
    wasserstein_threshold,
    ks_threshold,
    chi_square_threshold,
) -> dict:
    profiles = {
        "sensitive": {
            "kl_threshold": 0.15,
            "wasserstein_threshold": 0.12,
            "ks_threshold": 0.2,
            "chi_square_threshold": 7.0,
        },
        "balanced": {
            "kl_threshold": 0.25,
            "wasserstein_threshold": 0.2,
            "ks_threshold": 0.3,
            "chi_square_threshold": 10.0,
        },
        "conservative": {
            "kl_threshold": 0.4,
            "wasserstein_threshold": 0.3,
            "ks_threshold": 0.45,
            "chi_square_threshold": 14.0,
        },
    }
    thresholds = profiles.get(profile, profiles["balanced"]).copy()
    if kl_threshold is not None:
        thresholds["kl_threshold"] = kl_threshold
    if wasserstein_threshold is not None:
        thresholds["wasserstein_threshold"] = wasserstein_threshold
    if ks_threshold is not None:
        thresholds["ks_threshold"] = ks_threshold
    if chi_square_threshold is not None:
        thresholds["chi_square_threshold"] = chi_square_threshold
    return thresholds


def _metric_state(value: float, threshold: float) -> str:
    if threshold <= 0:
        return "n/a"
    ratio = value / threshold
    if ratio >= 1:
        return "breach"
    if ratio >= 0.8:
        return "near"
    return "ok"


def _is_number(value) -> bool:
    return isinstance(value, (int, float))


def _validate_samples_payload(payload_samples, strict_shape: bool = False):
    if not isinstance(payload_samples, list) or len(payload_samples) == 0:
        raise ValueError("data_samples must be a non-empty JSON array.")

    scalar_count = 0
    vector_count = 0
    vector_dims = set()

    for idx, sample in enumerate(payload_samples, start=1):
        if _is_number(sample):
            scalar_count += 1
            continue
        if isinstance(sample, list):
            if len(sample) == 0:
                raise ValueError(f"Sample at index {idx} is an empty vector.")
            if any(not _is_number(v) for v in sample):
                raise ValueError(f"Sample at index {idx} has non-numeric values.")
            vector_count += 1
            vector_dims.add(len(sample))
            continue
        raise ValueError(f"Sample at index {idx} must be a number or numeric list.")

    if strict_shape and vector_count > 0 and len(vector_dims) > 1:
        raise ValueError("In strict mode, all vector samples must have the same dimension.")

    return {
        "count": len(payload_samples),
        "scalar_count": scalar_count,
        "vector_count": vector_count,
        "vector_dims": sorted(vector_dims),
    }


@monitoring_api_app.command("deploy-stats")
def deployment_stats(
    deployment_id: int = typer.Option(..., prompt=True, help="deployment stats"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
    watch: bool = typer.Option(False, "--watch", "-w", help="Poll stats continuously."),
    interval_seconds: int = typer.Option(5, "--interval", "-i", help="Polling interval in seconds for --watch."),
    iterations: int = typer.Option(0, "--iterations", help="Number of polls for --watch (0 means infinite)."),
    cpu_warn: float = typer.Option(85.0, help="CPU warning threshold in percent."),
    ram_warn: float = typer.Option(85.0, help="RAM warning threshold in percent."),
    latency_warn: float = typer.Option(500.0, help="Latency warning threshold in ms."),
    error_rate_warn: float = typer.Option(5.0, help="Error-rate warning threshold in percent."),
):
    """Show live or one-shot deployment stats with health warnings."""
    client = AIACClient(base_path="monitoring")

    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return

        if watch and interval_seconds < 1:
            typer.echo("Interval must be at least 1 second.")
            return

        print_message(f"Fetching stats for deployment_id: {deployment_id}")
        poll_count = 0

        while True:
            response = client.api_request(f"deployments/{deployment_id}/stats/", method="GET")
            payload = response.json()

            cpu_usage = _safe_float(payload.get("cpu_usage"))
            ram_usage = _safe_float(payload.get("ram_usage"))
            latency_ms = _safe_float(payload.get("latency_ms"))
            request_count = int(_safe_float(payload.get("request_count")))
            error_count = int(_safe_float(payload.get("error_count")))
            error_rate_pct = (error_count / request_count * 100.0) if request_count > 0 else 0.0

            health, warnings = _build_stats_health(
                cpu_usage=cpu_usage,
                ram_usage=ram_usage,
                latency_ms=latency_ms,
                error_rate_pct=error_rate_pct,
                cpu_warn=cpu_warn,
                ram_warn=ram_warn,
                latency_warn=latency_warn,
                error_rate_warn=error_rate_warn,
            )

            if fmt == "json":
                output = {
                    "deployment_id": deployment_id,
                    "cpu_usage": cpu_usage,
                    "ram_usage": ram_usage,
                    "latency_ms": latency_ms,
                    "request_count": request_count,
                    "error_count": error_count,
                    "error_rate_pct": round(error_rate_pct, 4),
                    "health": health,
                    "warnings": warnings,
                    "updated_at": payload.get("updated_at"),
                }
                typer.echo(json.dumps(output, indent=2))
            else:
                stats_table = Table(title="Deployment Stats")
                stats_table.add_column("Deployment", style="cyan")
                stats_table.add_column("CPU Usage", style="green")
                stats_table.add_column("RAM Usage", style="yellow")
                stats_table.add_column("Latency (ms)", style="red")
                stats_table.add_column("Request Count", style="blue")
                stats_table.add_column("Error Count", style="magenta")
                stats_table.add_column("Error Rate", style="magenta")
                stats_table.add_column("Health", style="yellow")
                stats_table.add_column("Warnings")
                stats_table.add_column("Updated At", style="white")

                stats_table.add_row(
                    str(deployment_id),
                    f"{cpu_usage:.2f}",
                    f"{ram_usage:.2f}",
                    f"{latency_ms:.2f}",
                    str(request_count),
                    str(error_count),
                    f"{error_rate_pct:.2f}%",
                    health,
                    "; ".join(warnings) if warnings else "-",
                    str(payload.get("updated_at", "N/A")),
                )
                console.print(stats_table)
                typer.echo("Interpretation:")
                if warnings:
                    typer.echo("- Health is 'warning' because one or more thresholds were exceeded.")
                    for warning in warnings:
                        typer.echo(f"- {warning}")
                else:
                    typer.echo("- Health is 'healthy' because all thresholds are below the warning limits.")
                if latency_ms == 0.0:
                    if request_count <= 0:
                        typer.echo(
                            "- Latency is 0 because there have been no requests yet. "
                            "Send traffic to the deployment and re-run stats."
                        )
                    else:
                        typer.echo(
                            "- Latency is 0 because the collector did not report latency for this window "
                            "or only a single request was seen. Re-run with `--watch`."
                        )
                typer.echo(
                    "- CPU/RAM values are percentages of the runtime container. "
                    "Use `monitoring deploy-records` for per-sample detail."
                )

            poll_count += 1
            if not watch:
                break
            if iterations > 0 and poll_count >= iterations:
                break
            time.sleep(interval_seconds)
    except Exception as e:
        typer.echo(_friendly_deploy_stats_error(str(e), deployment_id))

@monitoring_api_app.command("deploy-records")
def deployment_records(
    deployment_id: int = typer.Option(..., prompt=True, help="deployment records"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, or csv."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max records to display."),
    watch: bool = typer.Option(False, "--watch", "-w", help="Poll records continuously."),
    interval_seconds: int = typer.Option(5, "--interval", "-i", help="Polling interval in seconds for --watch."),
    iterations: int = typer.Option(0, "--iterations", help="Number of polls for --watch (0 means infinite)."),
    cpu_warn: float = typer.Option(85.0, help="CPU warning threshold in percent."),
    ram_warn: float = typer.Option(85.0, help="RAM warning threshold in percent."),
    latency_warn: float = typer.Option(500.0, help="Latency warning threshold in ms."),
):
    """Show deployment monitoring records with summary statistics."""
    client = AIACClient(base_path="monitoring")

    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json", "csv"}:
            typer.echo("Invalid format. Use 'table', 'json', or 'csv'.")
            return
        if limit < 1:
            typer.echo("Limit must be at least 1.")
            return
        if watch and interval_seconds < 1:
            typer.echo("Interval must be at least 1 second.")
            return

        print_message(f"Fetching records for deployment_id: {deployment_id}")
        poll_count = 0

        while True:
            response = client.api_request(f"deployments/{deployment_id}/records/", method="GET")
            records_payload = response.json()
            records = records_payload if isinstance(records_payload, list) else [records_payload]
            records = records[:limit]

            if not records:
                typer.echo(
                    f"No monitoring records found for deployment_id {deployment_id}. "
                    "The deployment may not exist or has no collected metrics yet. "
                    "Run `deployment list-deployments` to verify the ID."
                )
                if not watch:
                    return
                poll_count += 1
                if iterations > 0 and poll_count >= iterations:
                    return
                time.sleep(interval_seconds)
                continue

            parsed = []
            for record in records:
                cpu_usage = _safe_float(record.get("cpu_usage"))
                ram_usage = _safe_float(record.get("ram_usage"))
                latency_ms = _safe_float(record.get("latency_ms"))
                request_count = int(_safe_float(record.get("request_count")))
                error_count = int(_safe_float(record.get("error_count")))
                status_bits = []
                if cpu_usage >= cpu_warn:
                    status_bits.append("cpu_warn")
                if ram_usage >= ram_warn:
                    status_bits.append("ram_warn")
                if latency_ms >= latency_warn:
                    status_bits.append("latency_warn")
                status_name = "|".join(status_bits) if status_bits else "ok"
                parsed.append(
                    {
                        "id": record.get("id"),
                        "deployment_id": deployment_id,
                        "cpu_usage": cpu_usage,
                        "ram_usage": ram_usage,
                        "latency_ms": latency_ms,
                        "request_count": request_count,
                        "error_count": error_count,
                        "status": status_name,
                        "created_at": record.get("created_at"),
                    }
                )

            count = len(parsed)
            avg_cpu = sum(r["cpu_usage"] for r in parsed) / count if count else 0.0
            avg_ram = sum(r["ram_usage"] for r in parsed) / count if count else 0.0
            avg_latency = sum(r["latency_ms"] for r in parsed) / count if count else 0.0
            max_latency = max((r["latency_ms"] for r in parsed), default=0.0)
            total_requests = sum(r["request_count"] for r in parsed)
            total_errors = sum(r["error_count"] for r in parsed)

            if fmt == "json":
                output = {
                    "deployment_id": deployment_id,
                    "count": count,
                    "summary": {
                        "avg_cpu_usage": round(avg_cpu, 4),
                        "avg_ram_usage": round(avg_ram, 4),
                        "avg_latency_ms": round(avg_latency, 4),
                        "max_latency_ms": round(max_latency, 4),
                        "total_requests": total_requests,
                        "total_errors": total_errors,
                    },
                    "records": parsed,
                }
                typer.echo(json.dumps(output, indent=2))
            elif fmt == "csv":
                typer.echo("id,deployment_id,cpu_usage,ram_usage,latency_ms,request_count,error_count,status,created_at")
                for row in parsed:
                    typer.echo(
                        f"{row.get('id')},{row.get('deployment_id')},{row.get('cpu_usage'):.4f},"
                        f"{row.get('ram_usage'):.4f},{row.get('latency_ms'):.4f},{row.get('request_count')},"
                        f"{row.get('error_count')},{row.get('status')},{row.get('created_at')}"
                    )
                typer.echo(
                    f"summary,,,,,,,,,"
                )
                typer.echo(
                    f"summary_stats,{deployment_id},{avg_cpu:.4f},{avg_ram:.4f},{avg_latency:.4f},{total_requests},{total_errors},max_latency={max_latency:.4f},-"
                )
            else:
                records_table = Table(title="Deployment Records")
                records_table.add_column("ID", style="cyan", no_wrap=True)
                records_table.add_column("Deployment", style="magenta")
                records_table.add_column("CPU Usage", style="green")
                records_table.add_column("RAM Usage", style="yellow")
                records_table.add_column("Latency (ms)", style="red")
                records_table.add_column("Request Count", style="blue")
                records_table.add_column("Error Count", style="magenta")
                records_table.add_column("Status", style="yellow")
                records_table.add_column("Created At", style="white")

                for row in parsed:
                    records_table.add_row(
                        str(row.get("id", "N/A")),
                        str(row.get("deployment_id")),
                        f"{row.get('cpu_usage', 0.0):.2f}",
                        f"{row.get('ram_usage', 0.0):.2f}",
                        f"{row.get('latency_ms', 0.0):.2f}",
                        str(row.get("request_count", 0)),
                        str(row.get("error_count", 0)),
                        str(row.get("status", "ok")),
                        str(row.get("created_at", "N/A")),
                    )
                console.print(records_table)
                typer.echo(
                    f"Summary: count={count} avg_cpu={avg_cpu:.2f}% avg_ram={avg_ram:.2f}% "
                    f"avg_latency={avg_latency:.2f}ms max_latency={max_latency:.2f}ms "
                    f"total_requests={total_requests} total_errors={total_errors}"
                )

            poll_count += 1
            if not watch:
                break
            if iterations > 0 and poll_count >= iterations:
                break
            time.sleep(interval_seconds)
    except Exception as e:
        typer.echo(
            _friendly_backend_error(
                f"Failed to fetch records for deployment_id {deployment_id}",
                str(e),
            )
        )

@monitoring_api_app.command("alert")
def receive_metrics(
    deployment_id: int = typer.Option(..., prompt=True, help="deployment alerts"),
    include_resolved: bool = typer.Option(False, "--include-resolved", help="Include resolved alerts."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max alerts to display."),
    only_type: str = typer.Option("", "--only-type", help="Filter by alert type."),
    only_severity: str = typer.Option("", "--only-severity", help="Filter by severity (e.g., low, medium, high)."),
    since_hours: int = typer.Option(0, "--since-hours", help="Only include alerts created in the last N hours."),
    since: str = typer.Option("", "--since", help="Only include alerts created after ISO timestamp (e.g., 2026-02-25T10:00:00Z)."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """List alerts for a deployment with filters and summaries."""
    client = AIACClient(base_path="monitoring")

    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return
        if limit < 1:
            typer.echo("Limit must be at least 1.")
            return

        response = client.api_request(f"deployments/{deployment_id}/alerts/", method="GET")
        alerts_payload = response.json()
        alerts = alerts_payload if isinstance(alerts_payload, list) else [alerts_payload]
        print_warning(f"Fetching alerts for deployment_id: {deployment_id}")
        if not alerts:
            deployment_exists = False
            try:
                deploy_client = AIACClient(base_path="deployment")
                deploy_client.api_request(f"deployments/{deployment_id}/", method="GET")
                deployment_exists = True
            except Exception:
                deployment_exists = False

            if deployment_exists:
                typer.echo(
                    f"No alerts found for deployment_id {deployment_id}. "
                    "The deployment exists and currently has no active alerts."
                )
            else:
                typer.echo(
                    f"No alerts found for deployment_id {deployment_id}. "
                    "Deployment was not found."
                )
            return

        if not include_resolved:
            alerts = [a for a in alerts if not bool(a.get("resolved"))]
        if only_type:
            alerts = [a for a in alerts if str(a.get("alert_type", "")).lower() == only_type.lower()]
        if only_severity:
            alerts = [a for a in alerts if str(a.get("severity", "")).lower() == only_severity.lower()]
        from datetime import datetime, timezone, timedelta
        cutoff = None
        if since:
            since_value = since.strip()
            if since_value.endswith("Z"):
                since_value = since_value[:-1] + "+00:00"
            try:
                cutoff = datetime.fromisoformat(since_value)
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=timezone.utc)
            except Exception:
                typer.echo("Invalid --since value. Use ISO format like 2026-02-25T10:00:00Z.")
                return
        elif since_hours and since_hours > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)

        if cutoff is not None:
            filtered = []
            for alert in alerts:
                created_at = str(alert.get("created_at", "")).strip()
                if not created_at:
                    continue
                # Normalize ISO with Z to Python fromisoformat compatible.
                if created_at.endswith("Z"):
                    created_at = created_at[:-1] + "+00:00"
                try:
                    dt = datetime.fromisoformat(created_at)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                if dt >= cutoff:
                    filtered.append(alert)
            alerts = filtered
        alerts = alerts[:limit]

        total = len(alerts)
        resolved_count = sum(1 for a in alerts if bool(a.get("resolved")))
        unresolved_count = total - resolved_count

        if fmt == "json":
            typer.echo(json.dumps(alerts, indent=2, default=str))
            return

        table = Table(title="Deployment Alerts")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Deployment", style="magenta")
        table.add_column("Alert Type", style="red")
        table.add_column("Severity", style="yellow")
        table.add_column("Message", style="yellow")
        table.add_column("Created At", style="green")
        table.add_column("Resolved", style="blue")

        # Assuming alerts is a list of alert objects
        for alert in alerts if isinstance(alerts, list) else [alerts]:
            table.add_row(
                str(alert.get('id', 'N/A')),
                str(deployment_id),
                str(alert.get('alert_type', 'N/A')),
                str(alert.get('severity', 'N/A')),
                str(alert.get('message', 'N/A')),
                str(alert.get('created_at', 'N/A')),
                str(alert.get('resolved', 'N/A'))
            )

        console.print(table)
        typer.echo(f"Summary: total={total} unresolved={unresolved_count} resolved={resolved_count}")
        if total:
            recent = alerts[: min(3, total)]
            typer.echo("Most recent alerts:")
            for idx, alert in enumerate(recent, start=1):
                typer.echo(
                    f"{idx}. {alert.get('created_at', 'N/A')} | "
                    f"type={alert.get('alert_type', 'N/A')} | "
                    f"resolved={alert.get('resolved', 'N/A')} | "
                    f"message={alert.get('message', 'N/A')}"
                )
        if not include_resolved:
            typer.echo("Tip: add `--include-resolved` to include resolved alerts.")
    except Exception as e:
        typer.echo(_friendly_alert_error(str(e), deployment_id))

@monitoring_api_app.command("resolve-alert")
def resolve_alert(
    alert_id: str = typer.Option(None, "--alert-id", "-a", help="Alert UUID to resolve."),
    deployment_id: int = typer.Option(None, "--deployment-id", "-d", help="Deployment ID to select alert from."),
    include_resolved: bool = typer.Option(False, "--include-resolved", help="Include resolved alerts when listing options."),
    force: bool = typer.Option(False, "--yes", "-y", help="Resolve without confirmation."),
):
    """Resolve a deployment alert by id or interactive selection."""
    client = AIACClient(base_path="monitoring")

    try:
        chosen_alert_id = alert_id
        selected_alert = None

        if not chosen_alert_id:
            if deployment_id is None:
                typer.echo("Provide --alert-id, or pass --deployment-id to select from alerts.")
                return

            list_resp = client.api_request(f"deployments/{deployment_id}/alerts/", method="GET")
            alerts_payload = list_resp.json()
            alerts = alerts_payload if isinstance(alerts_payload, list) else [alerts_payload]
            if not include_resolved:
                alerts = [a for a in alerts if not bool(a.get("resolved"))]

            if not alerts:
                if include_resolved:
                    typer.echo(f"No alerts found for deployment_id {deployment_id}.")
                else:
                    typer.echo(
                        f"No unresolved alerts found for deployment_id {deployment_id}. "
                        "Use --include-resolved to list all alerts."
                    )
                return

            alert_table = Table(title="Select Alert to Resolve")
            alert_table.add_column("Index", style="cyan")
            alert_table.add_column("Alert ID", style="magenta")
            alert_table.add_column("Type", style="red")
            alert_table.add_column("Message")
            alert_table.add_column("Resolved", style="yellow")
            alert_table.add_column("Created At", style="green")

            for idx, alert in enumerate(alerts, start=1):
                alert_table.add_row(
                    str(idx),
                    str(alert.get("id", "")),
                    str(alert.get("alert_type", "")),
                    str(alert.get("message", "")),
                    str(alert.get("resolved", "")),
                    str(alert.get("created_at", "")),
                )
            console.print(alert_table)

            selected_index = typer.prompt("Choose alert index to resolve", type=int)
            if selected_index < 1 or selected_index > len(alerts):
                typer.echo("Invalid alert index.")
                return
            selected_alert = alerts[selected_index - 1]
            chosen_alert_id = str(selected_alert.get("id", "")).strip()

        try:
            parsed_uuid = uuid.UUID(str(chosen_alert_id))
        except (TypeError, ValueError):
            typer.echo("Invalid alert UUID format.")
            return

        if not force:
            if not typer.confirm(f"Resolve alert {parsed_uuid}?"):
                typer.echo("Canceled.")
                return

        response = client.api_request(f"alerts/{parsed_uuid}/resolve/", method="POST")
        payload = response.json() if response.text else {}
        print_info(f"Resolving alert with alert_id: {parsed_uuid}")
        typer.echo(f"Alert resolved successfully (status={payload.get('status', 'ok')}).")
        if selected_alert:
            typer.echo(
                f"Resolved: type={selected_alert.get('alert_type')} "
                f"message={selected_alert.get('message')} "
                f"deployment={deployment_id}"
            )
    except Exception as e:
        msg = str(e)
        if "404" in msg and "Alert not found" in msg:
            typer.echo("Alert not found. Use `monitoring alert --deployment-id <id>` to list valid alert IDs.")
        elif "404" in msg and "Deployment not found" in msg:
            typer.echo("Deployment not found. Run `deployment list-deployments` and use a valid deployment ID.")
        else:
            typer.echo(_friendly_backend_error("Failed to resolve alert", msg))


@monitoring_api_app.command("health-report")
def health_report(
    deployment_id: int = typer.Option(..., prompt=True, help="Deployment ID for health report"),
    window: int = typer.Option(50, "--window", "-w", help="Number of recent records considered (10-500)."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """Generate a health report with metrics, alerts, and drift signals."""
    client = AIACClient(base_path="monitoring")
    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return

        endpoint = f"deployments/{deployment_id}/health-report/?window={window}"
        response = client.api_request(endpoint, method="GET")
        payload = response.json()

        if fmt == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return

        summary = Table(title="Deployment Health Report")
        summary.add_column("Deployment", style="cyan")
        summary.add_column("Status", style="yellow")
        summary.add_column("Health Score", style="green")
        summary.add_column("Health", style="magenta")
        summary.add_column("Window", style="blue")
        summary.add_row(
            str(payload.get("deployment_id", deployment_id)),
            str(payload.get("status", "N/A")),
            str(payload.get("health_score", "N/A")),
            str(payload.get("health_status", "N/A")),
            str(payload.get("window_records", "N/A")),
        )
        console.print(summary)
        typer.echo("Interpretation:")
        typer.echo(
            "- Health score summarizes CPU/RAM/latency/error metrics and recent alerts."
        )
        typer.echo(
            "- Health status is derived from the score and recent issues."
        )

        metrics = payload.get("metrics", {})
        metrics_table = Table(title="Metrics")
        metrics_table.add_column("Avg CPU")
        metrics_table.add_column("Avg RAM")
        metrics_table.add_column("Avg Latency (ms)")
        metrics_table.add_column("Total Requests")
        metrics_table.add_column("Total Errors")
        metrics_table.add_column("Error Rate %")
        metrics_table.add_row(
            str(metrics.get("avg_cpu_usage", 0)),
            str(metrics.get("avg_ram_usage", 0)),
            str(metrics.get("avg_latency_ms", 0)),
            str(metrics.get("total_requests", 0)),
            str(metrics.get("total_errors", 0)),
            str(metrics.get("error_rate_pct", 0)),
        )
        console.print(metrics_table)

        alerts = payload.get("alerts", {})
        typer.echo(
            f"Alerts: unresolved={alerts.get('unresolved', 0)} | last_24h={alerts.get('last_24h', 0)}"
        )

        typer.echo("Interpretation:")
        health_score = payload.get("health_score")
        health_status = payload.get("health_status")
        if health_score is not None:
            typer.echo(
                f"- Health score {health_score} maps to status '{health_status}'. "
                "Higher is healthier."
            )
        else:
            typer.echo("- Health status is derived from recent CPU/RAM/latency/error metrics.")
        avg_ram = metrics.get("avg_ram_usage")
        if avg_ram is not None:
            try:
                if float(avg_ram) >= 90:
                    typer.echo("- Average RAM is very high; consider scaling or memory tuning.")
            except (TypeError, ValueError):
                pass
        if payload.get("drift") is None:
            typer.echo(
                "- Drift is unavailable because no recent drift scan exists. "
                "Run `monitoring detect-drift` to populate drift metrics."
            )
        if alerts.get("unresolved", 0):
            typer.echo("- Unresolved alerts can degrade the health score until resolved.")

        drift = payload.get("drift")
        if drift:
            typer.echo(
                "Drift: "
                f"kl={drift.get('kl_divergence')} "
                f"wasserstein={drift.get('wasserstein_distance')} "
                f"ks={drift.get('ks_statistic')} "
                f"chi_square={drift.get('chi_square')} "
                f"scanned_at={drift.get('scanned_at')}"
            )
        else:
            typer.echo("Drift: no recent drift scan available.")

        trends = payload.get("trends", {})
        if trends:
            typer.echo(
                "Trends: "
                f"cpu={trends.get('cpu_trend', 0)} "
                f"ram={trends.get('ram_trend', 0)} "
                f"latency={trends.get('latency_trend', 0)}"
            )

        recommendations = payload.get("recommendations", [])
        if recommendations:
            typer.echo("Recommendations:")
            for rec in recommendations:
                typer.echo(f"- {rec}")
    except Exception as e:
        typer.echo(_friendly_health_report_error(str(e), deployment_id))


@monitoring_api_app.command("cost-intelligence")
def cost_intelligence(
    deployment_id: int = typer.Option(..., prompt=True, help="Deployment ID for cost intelligence"),
    window: int = typer.Option(200, "--window", "-w", help="Number of recent records considered (10-1000)."),
    cpu_hour_rate: float = typer.Option(0.05, help="Cost per CPU-hour."),
    gb_ram_hour_rate: float = typer.Option(0.01, help="Cost per GB RAM-hour."),
    request_million_rate: float = typer.Option(1.0, help="Cost per million requests."),
    ram_reference_gb: float = typer.Option(4.0, help="Reference RAM size when RAM is reported as percent."),
    budget_monthly: float = typer.Option(None, "--budget", help="Optional monthly budget cap for variance analysis."),
    target_cpu_utilization: float = typer.Option(65.0, help="Target CPU utilization percent for efficiency scoring."),
    target_ram_utilization: float = typer.Option(70.0, help="Target RAM utilization percent for efficiency scoring."),
    include_scenarios: bool = typer.Option(True, "--scenarios/--no-scenarios", help="Include projected cost scenarios."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """Estimate deployment cost, efficiency, and optimization opportunities."""
    client = AIACClient(base_path="monitoring")
    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return

        endpoint = (
            f"deployments/{deployment_id}/cost-intelligence/"
            f"?window={window}"
            f"&cpu_hour_rate={cpu_hour_rate}"
            f"&gb_ram_hour_rate={gb_ram_hour_rate}"
            f"&request_million_rate={request_million_rate}"
            f"&ram_reference_gb={ram_reference_gb}"
            f"&target_cpu_utilization={target_cpu_utilization}"
            f"&target_ram_utilization={target_ram_utilization}"
            f"&include_scenarios={str(include_scenarios).lower()}"
        )
        if budget_monthly is not None:
            endpoint += f"&budget_monthly={budget_monthly}"
        response = client.api_request(endpoint, method="GET")
        payload = response.json()

        if fmt == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return

        summary = Table(title="Cost Intelligence")
        summary.add_column("Deployment", style="cyan")
        summary.add_column("Status", style="yellow")
        summary.add_column("Window", style="blue")
        summary.add_column("Observed Hours", style="green")
        summary.add_column("Annual Cost", style="magenta")
        summary.add_column("Efficiency", style="yellow")
        summary.add_row(
            str(payload.get("deployment_id", deployment_id)),
            str(payload.get("status", "N/A")),
            str(payload.get("window_records", "N/A")),
            str(payload.get("observed_hours", "N/A")),
            str(payload.get("annual_estimated_cost", "N/A")),
            str(payload.get("efficiency", {}).get("score", "N/A")),
        )
        console.print(summary)

        util = payload.get("utilization", {})
        util_table = Table(title="Utilization")
        util_table.add_column("Avg CPU %")
        util_table.add_column("Avg RAM GB")
        util_table.add_column("RAM Util %")
        util_table.add_column("Requests/Hour")
        util_table.add_row(
            str(util.get("avg_cpu_pct", 0)),
            str(util.get("avg_ram_gb", 0)),
            str(payload.get("efficiency", {}).get("current_ram_utilization_pct", 0)),
            str(util.get("requests_per_hour", 0)),
        )
        console.print(util_table)
        typer.echo("Interpretation:")
        typer.echo("- Avg CPU % and Avg RAM GB are averages over the selected window.")
        typer.echo("- RAM Util % uses the configured reference RAM size.")
        typer.echo("- Requests/Hour is derived from request counts in the window.")

        cost = payload.get("cost_breakdown_monthly", {})
        cost_table = Table(title="Estimated Monthly Cost")
        cost_table.add_column("CPU Cost", style="cyan")
        cost_table.add_column("RAM Cost", style="magenta")
        cost_table.add_column("Request Cost", style="yellow")
        cost_table.add_column("Total", style="green")
        cost_table.add_column("CPU %", style="cyan")
        cost_table.add_column("RAM %", style="magenta")
        cost_table.add_column("Req %", style="yellow")
        cost_table.add_row(
            str(cost.get("cpu_cost", 0)),
            str(cost.get("ram_cost", 0)),
            str(cost.get("request_cost", 0)),
            str(cost.get("total_estimated_cost", 0)),
            str(cost.get("cpu_share_pct", 0)),
            str(cost.get("ram_share_pct", 0)),
            str(cost.get("request_share_pct", 0)),
        )
        console.print(cost_table)
        typer.echo("Interpretation:")
        typer.echo("- Cost breakdown is estimated from utilization and pricing inputs.")
        typer.echo("- CPU/RAM/Req % show which component dominates monthly cost.")

        efficiency = payload.get("efficiency", {})
        typer.echo(
            "Efficiency: "
            f"score={efficiency.get('score')} "
            f"class={efficiency.get('classification')} "
            f"target_cpu={efficiency.get('target_cpu_utilization')} "
            f"target_ram={efficiency.get('target_ram_utilization')}"
        )
        typer.echo(
            "Reality check: these figures are estimates based on monitoring data and configured rates, "
            "not actual cloud billing. Use them for relative sizing decisions."
        )

        budget = payload.get("budget")
        if budget:
            typer.echo(
                "Budget: "
                f"monthly={budget.get('monthly_budget')} "
                f"variance={budget.get('variance')} "
                f"variance_pct={budget.get('variance_pct')} "
                f"within_budget={budget.get('within_budget')}"
            )

        risks = payload.get("risks", [])
        if risks:
            typer.echo("Risk flags:")
            for risk in risks:
                typer.echo(f"- {risk}")

        scenarios = payload.get("scenarios", [])
        if scenarios:
            scenario_table = Table(title="Scenario Projections")
            scenario_table.add_column("Scenario", style="cyan")
            scenario_table.add_column("Monthly Cost", style="green")
            scenario_table.add_column("Delta vs Current", style="yellow")
            for row in scenarios:
                scenario_table.add_row(
                    str(row.get("name", "")),
                    str(row.get("estimated_monthly_cost", "")),
                    str(row.get("delta_vs_current", "")),
                )
            console.print(scenario_table)
            typer.echo(
                "Interpretation: scenarios simulate cost changes if you resize resources. "
                "Negative delta means cheaper than current; positive means higher cost."
            )

        optimization = payload.get("optimization", {})
        typer.echo(f"Estimated savings potential: {optimization.get('estimated_savings_potential', 0)} / month")
        recommendations = optimization.get("recommendations", [])
        if recommendations:
            typer.echo("Optimization recommendations:")
            for rec in recommendations:
                typer.echo(f"- {rec}")
    except Exception as e:
        typer.echo(_friendly_cost_intelligence_error(str(e), deployment_id))


@monitoring_api_app.command("detect-drift")
def detect_drift(
    model_version_id: int = typer.Option(..., prompt=True, help="detect data drift for model version"),
    profile: str = typer.Option("balanced", "--profile", "-p", help="Threshold profile: sensitive, balanced, conservative."),
    kl_threshold: float = typer.Option(None, help="Override KL divergence threshold"),
    wasserstein_threshold: float = typer.Option(None, help="Override Wasserstein threshold"),
    ks_threshold: float = typer.Option(None, help="Override KS statistic threshold"),
    chi_square_threshold: float = typer.Option(None, help="Override Chi-square threshold"),
    explain: bool = typer.Option(True, help="Show metric-level drift analysis."),
    show_history: bool = typer.Option(False, "--history", help="Show recent drift scans before detection."),
    history_limit: int = typer.Option(5, "--history-limit", help="Max scan rows shown with --history."),
    watch: bool = typer.Option(False, "--watch", "-w", help="Run detection repeatedly."),
    interval_seconds: int = typer.Option(30, "--interval", "-i", help="Seconds between checks for --watch."),
    iterations: int = typer.Option(0, "--iterations", help="Number of checks for --watch (0 means infinite)."),
):
    """Run drift detection with thresholds, history, and watch mode."""
    client = AIACClient(base_path="monitoring")

    try:
        profile = (profile or "balanced").strip().lower()
        if profile not in {"sensitive", "balanced", "conservative"}:
            typer.echo("Invalid profile. Use sensitive, balanced, or conservative.")
            return
        if watch and interval_seconds < 1:
            typer.echo("Interval must be at least 1 second.")
            return

        thresholds = _resolve_drift_thresholds(
            profile=profile,
            kl_threshold=kl_threshold,
            wasserstein_threshold=wasserstein_threshold,
            ks_threshold=ks_threshold,
            chi_square_threshold=chi_square_threshold,
        )

        if show_history:
            try:
                history_response = client.api_request(f"drifts/{model_version_id}/", method="GET")
                history = history_response.json()
                rows = history if isinstance(history, list) else [history]
                rows = rows[: max(1, history_limit)]
                if rows:
                    history_table = Table(title="Recent Drift Scans")
                    history_table.add_column("Scanned At", style="green")
                    history_table.add_column("Detected", style="yellow")
                    history_table.add_column("KL", style="cyan")
                    history_table.add_column("Wasserstein", style="magenta")
                    history_table.add_column("KS", style="blue")
                    history_table.add_column("Chi-square", style="red")
                    for row in rows:
                        history_table.add_row(
                            str(row.get("scanned_at", "N/A")),
                            str(row.get("drift_detected", "N/A")),
                            str(row.get("kl_divergence", "N/A")),
                            str(row.get("wasserstein_distance", "N/A")),
                            str(row.get("ks_statistic", "N/A")),
                            str(row.get("chi_square", "N/A")),
                        )
                    console.print(history_table)
                else:
                    typer.echo("No previous drift scans found.")
            except Exception:
                # History retrieval should not block drift checks.
                pass

        print_info(
            f"Detecting drift for model_version_id: {model_version_id} "
            f"(profile={profile}, thresholds={thresholds})"
        )

        run_count = 0
        while True:
            response = client.api_request(
                f"drifts/{model_version_id}/",
                method="POST",
                data=thresholds,
            )
            result = response.json()

            kl_val = _safe_float(result.get("kl_divergence"))
            wd_val = _safe_float(result.get("wasserstein_distance"))
            ks_val = _safe_float(result.get("ks_statistic"))
            chi_val = _safe_float(result.get("chi_square"))
            detected = bool(result.get("drift_detected", False))

            typer.echo(
                f"Drift detection result: detected={detected} "
                f"| kl={kl_val:.6f} "
                f"| wasserstein={wd_val:.6f} "
                f"| ks={ks_val:.6f} "
                f"| chi_square={chi_val:.6f}"
            )

            if explain:
                typer.echo("Interpretation:")
                if detected:
                    typer.echo("- Drift detected because at least one metric breached its threshold.")
                else:
                    typer.echo("- No drift detected; all metrics are within thresholds.")
                typer.echo(
                    "- Status meanings: ok=below threshold, near=approaching threshold, breach=exceeded threshold."
                )
                typer.echo(
                    "- Wasserstein captures distribution shift magnitude; KL/KS/Chi-square capture divergence tests."
                )

                analysis_table = Table(title="Drift Analysis")
                analysis_table.add_column("Metric", style="cyan")
                analysis_table.add_column("Value")
                analysis_table.add_column("Threshold", style="yellow")
                analysis_table.add_column("Status", style="magenta")
                rows = [
                    ("kl_divergence", kl_val, thresholds["kl_threshold"]),
                    ("wasserstein_distance", wd_val, thresholds["wasserstein_threshold"]),
                    ("ks_statistic", ks_val, thresholds["ks_threshold"]),
                    ("chi_square", chi_val, thresholds["chi_square_threshold"]),
                ]
                for metric, value, threshold in rows:
                    analysis_table.add_row(
                        metric,
                        f"{value:.6f}",
                        f"{threshold:.6f}",
                        _metric_state(value, threshold),
                    )
                console.print(analysis_table)

            run_count += 1
            if not watch:
                break
            if iterations > 0 and run_count >= iterations:
                break
            time.sleep(interval_seconds)
    except Exception as e:
        typer.echo(_friendly_detect_drift_error(str(e), model_version_id))

@monitoring_api_app.command("samples")
def get_samples(
    model_version_id: int = typer.Option(..., prompt=True, help="Post samples for model version"),
    data_samples: str = typer.Option("", help="JSON array of numeric samples, e.g. \"[0.1, 0.2, 0.3]\""),
    samples_file: str = typer.Option("", help="Path to a JSON file containing an array of samples"),
    csv_file: str = typer.Option("", help="Path to CSV file. Uses first row as one feature vector sample."),
    drop_last_column: bool = typer.Option(
        False,
        "--drop-last-column",
        help="Drop the last CSV column for each row (useful when last column is label/target).",
    ),
    input_format: str = typer.Option("auto", "--format", "-f", help="Input format for --samples-file: auto, json, csv."),
    chunk_size: int = typer.Option(0, "--chunk-size", help="Upload in batches (0 means single request)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and preview samples without uploading."),
    preview: int = typer.Option(3, "--preview", help="Preview first N parsed samples."),
    strict_shape: bool = typer.Option(False, "--strict-shape", help="Require consistent vector dimensions."),
):
    """Upload or validate samples for drift/monitoring."""
    client = AIACClient(base_path="monitoring")

    try:
        typer.echo("Input format guidance:")
        typer.echo("- Single feature row: [[6,63,98,26,726,38.3,2.466,25]]")
        typer.echo("- Multiple rows: [[6,63,98,26,726,38.3,2.466,25],[5,50,90,22,700,35.2,1.9,30]]")
        typer.echo("- Scalar samples (one number per sample): [0.1,0.2,0.3]")

        payload_samples = []
        used_drop_last_column = False
        fmt = (input_format or "auto").strip().lower()
        if fmt not in {"auto", "json", "csv"}:
            typer.echo("Invalid format. Use auto, json, or csv.")
            return

        if chunk_size < 0:
            typer.echo("chunk-size must be >= 0.")
            return
        if preview < 0:
            typer.echo("preview must be >= 0.")
            return

        if csv_file:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = [row for row in reader if row]
                if not rows:
                    raise ValueError("CSV file is empty.")

                def _is_number_text(text: str) -> bool:
                    try:
                        float(text)
                        return True
                    except (TypeError, ValueError):
                        return False

                # Skip header row if it contains non-numeric values.
                start_idx = 0
                if rows and any(not _is_number_text(cell.strip()) for cell in rows[0] if cell.strip()):
                    start_idx = 1

                parsed_rows = []
                for idx, row in enumerate(rows[start_idx:], start=start_idx + 1):
                    cleaned = [cell.strip() for cell in row if cell.strip() != ""]
                    if not cleaned:
                        continue
                    if drop_last_column:
                        if len(cleaned) <= 1:
                            raise ValueError(
                                f"CSV row {idx} has only one column; cannot apply --drop-last-column."
                            )
                        cleaned = cleaned[:-1]
                        used_drop_last_column = True
                    if any(not _is_number_text(cell) for cell in cleaned):
                        raise ValueError(f"Non-numeric value found in CSV row {idx}.")
                    numeric_row = [float(cell) for cell in cleaned]
                    parsed_rows.append(numeric_row)

                if not parsed_rows:
                    raise ValueError("No numeric sample rows found in CSV.")

                payload_samples = parsed_rows
        elif samples_file:
            resolved_format = fmt
            if resolved_format == "auto":
                resolved_format = "csv" if samples_file.lower().endswith(".csv") else "json"

            if resolved_format == "csv":
                with open(samples_file, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = [row for row in reader if row]
                    if not rows:
                        raise ValueError("CSV file is empty.")
                    parsed_rows = []
                    start_idx = 0
                    if rows and any(not cell.strip().replace(".", "", 1).replace("-", "", 1).isdigit() for cell in rows[0] if cell.strip()):
                        start_idx = 1
                    for idx, row in enumerate(rows[start_idx:], start=start_idx + 1):
                        cleaned = [cell.strip() for cell in row if cell.strip() != ""]
                        if not cleaned:
                            continue
                        if drop_last_column:
                            if len(cleaned) <= 1:
                                raise ValueError(
                                    f"CSV row {idx} has only one column; cannot apply --drop-last-column."
                                )
                            cleaned = cleaned[:-1]
                            used_drop_last_column = True
                        try:
                            parsed_rows.append([float(cell) for cell in cleaned])
                        except ValueError:
                            raise ValueError(f"Non-numeric value found in CSV row {idx}.")
                    payload_samples = parsed_rows
            else:
                with open(samples_file, "r", encoding="utf-8") as f:
                    payload_samples = json.load(f)
        elif data_samples:
            payload_samples = json.loads(data_samples)
        else:
            # Prompt if options were not provided.
            raw = typer.prompt("Data samples JSON (example: [0.1, 0.2, 0.3])")
            payload_samples = json.loads(raw)

        stats = _validate_samples_payload(payload_samples, strict_shape=strict_shape)
        preview_rows = payload_samples[:preview] if preview > 0 else []

        typer.echo(
            f"Parsed samples: total={stats['count']} scalar={stats['scalar_count']} "
            f"vector={stats['vector_count']} dims={stats['vector_dims'] if stats['vector_dims'] else 'N/A'}"
        )
        if used_drop_last_column:
            typer.echo("CSV parsing option enabled: dropped last column from each row.")
        if stats["count"] < 20:
            typer.echo(
                "Note: drift detection needs at least 20 samples. "
                "Add more rows/samples before running `monitoring detect-drift`."
            )
        if stats["scalar_count"] == stats["count"] and stats["count"] > 1:
            typer.echo(
                "Interpretation: you provided a list of scalar samples (one number per sample). "
                "If you intended a single multi-feature row, wrap it as a nested list, e.g. [[6, 63, 98, ...]]."
            )
        if stats["vector_count"] > 0:
            dims = stats["vector_dims"]
            if dims:
                typer.echo(
                    f"Interpretation: you provided {stats['vector_count']} vector samples with dimensions {dims}."
                )
        if preview_rows:
            preview_label = "rows" if stats["vector_count"] > 0 else "values"
            typer.echo(f"Preview ({len(preview_rows)} {preview_label}):")
            for idx, row in enumerate(preview_rows, start=1):
                if isinstance(row, list):
                    typer.echo(f"  {idx:02d}. {json.dumps(row)}")
                else:
                    typer.echo(f"  {idx:02d}. {row}")

        if dry_run:
            typer.echo("Dry run complete. No samples were uploaded.")
            return

        print_info(f"Posting samples for model_version_id: {model_version_id}")
        inserted_total = 0

        if chunk_size and chunk_size > 0:
            for i in range(0, len(payload_samples), chunk_size):
                chunk = payload_samples[i : i + chunk_size]
                response = client.api_request(
                    "deployments/samples/",
                    method="POST",
                    data={"model_version_id": model_version_id, "data_samples": chunk},
                )
                payload = response.json()
                inserted_total += int(payload.get("inserted", 0))
                typer.echo(
                    f"Uploaded chunk {i // chunk_size + 1}: size={len(chunk)} inserted={payload.get('inserted', 'N/A')}"
                )
        else:
            response = client.api_request(
                "deployments/samples/",
                method="POST",
                data={"model_version_id": model_version_id, "data_samples": payload_samples},
            )
            payload = response.json()
            inserted_total = int(payload.get("inserted", 0))

        typer.echo(f"Samples posted successfully: inserted_total={inserted_total}")
    except Exception as e:
        typer.echo(
            _friendly_backend_error(
                f"Failed to post samples for model_version_id {model_version_id}",
                str(e),
            )
        )
       
