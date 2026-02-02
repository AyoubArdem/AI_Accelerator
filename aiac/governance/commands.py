import typer
from aiac.client import AIACClient
from aiac.console import console
from rich.table import Table



table = Table(title="Governance Policies")

governance_api_app = typer.Typer(help="Governance related commands for AIAC.")

@governance_api_app.command("create-policy")
def create_policy(name: str, policy_type: str, description: str = "", rules: str = "{}"):
    """Create a new governance policy."""

    client = AIACClient()

    try:
        # Parse rules if it's a string
        if isinstance(rules, str):
            import json
            rules = json.loads(rules)

        data = {
            "name": name,
            "policy_type": policy_type,
            "description": description,
            "rules": rules
        }

        response = client.api_request("/policies/", method="POST", data=data)
        typer.echo(f"Policy '{name}' created successfully.")
    except Exception as e:
        typer.echo(f"Failed to create policy: {str(e)}")

@governance_api_app.command("list-policies")
def list_policies():
    """List all governance policies."""

    client = AIACClient()
    try:
        policies = client.api_request("/policies/")

        table = Table(title="Governance Policies")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Type", style="green")
        table.add_column("Description")

        for policy in policies:
            table.add_row(
                str(policy['id']),
                policy['name'],
                policy['policy_type'],
                policy.get('description', '')
            )

        console.print(table)
    except Exception as e:
        typer.echo(f"Failed to retrieve policies: {str(e)}")

@governance_api_app.command("delete-policy")
def delete_policy(policy_id: int):
    
    """Delete a governance policy by its ID."""

    client = AIACClient()
    response = client.delete(f"/policies/{policy_id}/")

    if response.status_code == 204:
        typer.echo(f"Policy with ID '{policy_id}' deleted successfully.")
    else:
        typer.echo(f"Failed to delete policy. Status code: {response.status_code}, Response: {response.text}")

@governance_api_app.command("view-violations")
def view_violations():
    """View all policy violations."""

    client = AIACClient()
    response = client.get("/policy-violations/")

    if response.status_code == 200:
        violations = response.json()
        for violation in violations:
            table.add_column("Deployment_ID", "Policy_Name", "Violation_Type", "Severity","Resolved", justify="right", style="cyan", no_wrap=True)
            table.add_row(str(violation['deployment_id']), str(violation['policy_name']), str(violation['violation_type']), str(violation['severity']), str(violation['resolved']))
        console.print(table)
    else:
        typer.echo(f"Failed to retrieve violations. Status code: {response.status_code}, Response: {response.text}")

@governance_api_app.command("metrics")
def violation_metrics():
    """View metrics related to policy violations."""

    client = AIACClient()
    response = client.get("/policy-violations/")

    if response.status_code == 200:
        violations = response.json()
        if violations:
            for metrics in violations:
                typer.echo("Violation Metrics:{metrics[policy_name]} --- {metrics[violation_type]}")
                for key, value in metrics.items():
                    typer.echo(f"{key}: {value}")
                typer.echo("-------------------------------------------------------------------------")
        else:
            typer.echo("No violations found.")
    else:
        typer.echo(f"Failed to retrieve violation metrics. Status code: {response.status_code}, Response: {response.text}")


@governance_api_app.command("apply-policy")
def apply_policy(policy_id: int, deployment_id: int):
    """Apply a policy to a deployment."""
    

    client = AIACClient()
    data = {
        "policy": policy_id,
        "deployment": deployment_id
    }

    response = client.post("/policy-assignments/", json=data)

    if response.status_code == 201:
        typer.echo(f"Policy '{policy_id}' applied to deployment '{deployment_id}' successfully.")
        typer.echo(f"applied_at: {response.json().get('applied_at')}")
        typer.echo(f"applied_by: {response.json().get('applied_by')}")
    else:
        typer.echo(f"Failed to apply policy. Status code: {response.status_code}, Response: {response.text}")




@governance_api_app.command("alert-logs")
def alert_logs():
    """View alert logs for policy violations."""

    client = AIACClient()
    response = client.get("/alerts/")

    if response.status_code == 200:
        typer.echo("Alert Logs:")
        logs = response.json()
        for log in logs:
            table.add_column("Policy_Violation", "Message","Sent", justify="right", style="cyan", no_wrap=True)
            table.add_row(str(log['policy_violation']), str(log['message']), str(log['sent']))
        console.print(table)
    else:
        typer.echo(f"Failed to retrieve alert logs. Status code: {response.status_code}, Response: {response.text}")