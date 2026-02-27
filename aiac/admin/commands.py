import csv
import json
import re
import typer
from pathlib import Path
from aiac.client import AIACClient
from aiac.console import console
from rich.table import Table

admin_app = typer.Typer(help="Admin services (user management and audits)")

def _friendly_admin_error(prefix: str, error_text: str) -> str:
    txt = str(error_text or "")
    if "API server is not reachable" in txt:
        return txt
    if "403" in txt and "Admin access required" in txt:
        match = re.search(r"Contact admin:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", txt)
        contact = match.group(1) if match else None
        contact_line = (
            f"Contact admin: {contact}"
            if contact
            else "Login with an admin account, or ask an admin to promote your account."
        )
        return (
            f"{prefix}: admin access is required for this command.\n"
            f"{contact_line}"
        )
    if "404" in txt and "<!DOCTYPE html>" in txt:
        return (
            f"{prefix}: admin endpoints not found on the server.\n"
            "Make sure the backend is updated and restarted, then try again."
        )
    if "404" in txt and "Not Found" in txt:
        return (
            f"{prefix}: admin endpoints not found on the server.\n"
            "Make sure the backend is updated and restarted, then try again."
        )
    return f"{prefix}: {txt}"

@admin_app.command("list-users")
def list_users(
    role: str = typer.Option("", "--role", help="Filter by role (admin/developer/client)."),
    active: bool = typer.Option(False, "--active", help="Only active users."),
    inactive: bool = typer.Option(False, "--inactive", help="Only inactive users."),
    staff: bool = typer.Option(False, "--staff", help="Only staff users."),
    email: str = typer.Option("", "--email", help="Filter by email substring."),
    username: str = typer.Option("", "--username", help="Filter by username substring."),
    limit: int = typer.Option(0, "--limit", "-l", help="Limit results (0 = no limit)."),
    offset: int = typer.Option(0, "--offset", help="Skip first N results."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """List users with filters."""
    client = AIACClient(base_path="users")
    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return
        resp = client.api_request("admin/users/", method="GET")
        payload = resp.json()
        rows = payload if isinstance(payload, list) else [payload]
        if role:
            rows = [r for r in rows if str(r.get("role", "")).lower() == role.lower()]
        if active and not inactive:
            rows = [r for r in rows if r.get("is_active")]
        if inactive and not active:
            rows = [r for r in rows if not r.get("is_active")]
        if staff:
            rows = [r for r in rows if r.get("is_staff")]
        if email:
            needle = email.lower()
            rows = [r for r in rows if needle in str(r.get("email", "")).lower()]
        if username:
            needle = username.lower()
            rows = [r for r in rows if needle in str(r.get("username", "")).lower()]
        if offset and offset > 0:
            rows = rows[offset:]
        if limit and limit > 0:
            rows = rows[:limit]

        if fmt == "json":
            typer.echo(json.dumps(rows, indent=2, default=str))
            return

        table = Table(title="Users")
        table.add_column("ID", style="cyan")
        table.add_column("Email", style="green")
        table.add_column("Username", style="yellow")
        table.add_column("Role", style="magenta")
        table.add_column("Active", style="white")
        table.add_column("Staff", style="white")
        table.add_column("Joined", style="white")
        for row in rows:
            table.add_row(
                str(row.get("id", "")),
                str(row.get("email", "")),
                str(row.get("username", "")),
                str(row.get("role", "")),
                "yes" if row.get("is_active") else "no",
                "yes" if row.get("is_staff") else "no",
                str(row.get("date_joined", "")),
            )
        console.print(table)
        typer.echo(f"Total: {len(rows)}")
    except Exception as e:
        typer.echo(_friendly_admin_error("Failed to list users", e))


@admin_app.command("user")
def user_detail(user_id: int = typer.Option(..., prompt=True, help="User ID")):
    """Show details for a single user."""
    client = AIACClient(base_path="users")
    try:
        resp = client.api_request(f"admin/users/{user_id}/", method="GET")
        payload = resp.json()
        table = Table(title="User Detail")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")
        for k, v in payload.items():
            table.add_row(str(k), str(v))
        console.print(table)
    except Exception as e:
        typer.echo(_friendly_admin_error("Failed to fetch user", e))


def _simple_user_action(user_id: int, endpoint: str, success_msg: str):
    client = AIACClient(base_path="users")
    try:
        resp = client.api_request(endpoint, method="POST")
        payload = resp.json() if resp.text else {}
        msg = payload.get("message") if isinstance(payload, dict) else None
        typer.echo(msg or success_msg)
    except Exception as e:
        typer.echo(_friendly_admin_error("Failed to update user", e))


@admin_app.command("activate-user")
def activate_user(user_id: int = typer.Option(..., prompt=True, help="User ID")):
    """Activate a user account."""
    _simple_user_action(user_id, f"admin/users/{user_id}/activate/", "User activated.")


@admin_app.command("deactivate-user")
def deactivate_user(user_id: int = typer.Option(..., prompt=True, help="User ID")):
    """Deactivate a user account."""
    _simple_user_action(user_id, f"admin/users/{user_id}/deactivate/", "User deactivated.")


@admin_app.command("soft-delete-user")
def soft_delete_user(user_id: int = typer.Option(..., prompt=True, help="User ID")):
    """Soft delete (deactivate) a user account."""
    _simple_user_action(user_id, f"admin/users/{user_id}/soft-delete/", "User soft-deleted (deactivated).")


@admin_app.command("promote-admin")
def promote_admin(user_id: int = typer.Option(..., prompt=True, help="User ID")):
    """Promote a user to admin."""
    _simple_user_action(user_id, f"admin/users/{user_id}/promote/", "User promoted to admin.")


@admin_app.command("demote-admin")
def demote_admin(user_id: int = typer.Option(..., prompt=True, help="User ID")):
    """Demote a user to client."""
    _simple_user_action(user_id, f"admin/users/{user_id}/demote/", "User demoted to client.")


@admin_app.command("reset-password")
def reset_password(
    user_id: int = typer.Option(..., prompt=True, help="User ID"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="New password"),
):
    """Reset a user's password."""
    client = AIACClient(base_path="users")
    try:
        resp = client.api_request(
            f"admin/users/{user_id}/reset-password/",
            method="POST",
            data={"password": password},
        )
        payload = resp.json() if resp.text else {}
        msg = payload.get("message") if isinstance(payload, dict) else None
        typer.echo(msg or "Password reset successfully.")
    except Exception as e:
        typer.echo(_friendly_admin_error("Failed to reset password", e))


@admin_app.command("list-audits")
def list_audits(
    limit: int = typer.Option(50, "--limit", "-l", help="Max rows to display."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """List audit logs."""
    client = AIACClient(base_path="governance")
    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return
        resp = client.api_request("audit-logs/", method="GET")
        payload = resp.json()
        rows = payload if isinstance(payload, list) else [payload]
        rows = rows[: max(1, limit)]
        if fmt == "json":
            typer.echo(json.dumps(rows, indent=2, default=str))
            return
        table = Table(title="Audit Logs")
        table.add_column("ID", style="cyan")
        table.add_column("Deployment", style="magenta")
        table.add_column("User", style="green")
        table.add_column("Severity", style="yellow")
        table.add_column("Action", style="white")
        table.add_column("Service", style="white")
        table.add_column("Timestamp", style="white")
        for row in rows:
            table.add_row(
                str(row.get("id", "")),
                str(row.get("deployment", "")),
                str(row.get("user", "")),
                str(row.get("severity", "")),
                str(row.get("action", "")),
                str(row.get("service", "")),
                str(row.get("timestamp", "")),
            )
        console.print(table)
        typer.echo("Interpretation:")
        typer.echo("- Each row is an audit event recorded by the governance service.")
        typer.echo("- Severity reflects impact level; Action shows what happened (e.g., DEPLOY).")
        typer.echo("- Deployment and User are IDs; use `deployment list-deployments` or `admin list-users` for details.")
    except Exception as e:
        typer.echo(_friendly_admin_error("Failed to list audits", e))


@admin_app.command("export-audits")
def export_audits(
    output_path: str = typer.Option("audit_logs.csv", "--out", help="CSV output path."),
):
    """Export audit logs to CSV."""
    client = AIACClient(base_path="governance")
    try:
        resp = client.api_request("audit-logs/", method="GET")
        payload = resp.json()
        rows = payload if isinstance(payload, list) else [payload]
        headers = ["id", "deployment", "user", "severity", "action", "service", "description", "timestamp"]
        output_path = str(Path(output_path).expanduser())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                writer.writerow([row.get(h, "") for h in headers])
        typer.echo(f"Exported {len(rows)} audit log(s) to {output_path}.")
    except Exception as e:
        typer.echo(_friendly_admin_error("Failed to export audits", e))


@admin_app.command("export-audits-json")
def export_audits_json(
    output_path: str = typer.Option("audit_logs.json", "--out", help="JSON output path."),
):
    """Export audit logs to JSON."""
    client = AIACClient(base_path="governance")
    try:
        resp = client.api_request("audit-logs/", method="GET")
        payload = resp.json()
        rows = payload if isinstance(payload, list) else [payload]
        output_path = str(Path(output_path).expanduser())
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, default=str)
        typer.echo(f"Exported {len(rows)} audit log(s) to {output_path}.")
    except Exception as e:
        typer.echo(_friendly_admin_error("Failed to export audits", e))
