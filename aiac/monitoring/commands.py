import typer
from aiac.client import AIACClient
from  aiac.console import console , print_message , print_warning  , print_info
from rich.table import Table


table = Table()

monitoring_api_app = typer.Typer(help = "monitoring commands")

@monitoring_api_app.command("deploy-stats")
def deployment_stats(deployment_id: int = typer.Option(..., prompt=True, help="deployment stats")):
    client = AIACClient()

    try:
        response = client.api_request(f"deployments/{deployment_id}/stats/", method="GET")
        print_message(f"Fetching stats for deployment_id: {deployment_id}")

        table = Table(title="Deployment Stats")
        table.add_column("Deployment", style="cyan")
        table.add_column("CPU Usage", style="green")
        table.add_column("RAM Usage", style="yellow")
        table.add_column("Latency (ms)", style="red")
        table.add_column("Request Count", style="blue")
        table.add_column("Error Count", style="magenta")
        table.add_column("Updated At", style="white")

        # Assuming response is a single stats object
        table.add_row(
            str(deployment_id),
            str(response.get('cpu_usage', 'N/A')),
            str(response.get('ram_usage', 'N/A')),
            str(response.get('latency_ms', 'N/A')),
            str(response.get('request_count', 'N/A')),
            str(response.get('error_count', 'N/A')),
            str(response.get('updated_at', 'N/A'))
        )

        console.print(table)
    except Exception as e:
        typer.echo(f"Failed to fetch stats for deployment_id {deployment_id}: {str(e)}")

@monitoring_api_app.command("deploy-records")
def deployment_records(deployment_id: int = typer.Option(..., prompt=True, help="deployment records")):
    client = AIACClient()

    try:
        records = client.api_request(f"deployments/{deployment_id}/records/", method="GET")
        print_message(f"Fetching records for deployment_id: {deployment_id}")

        table = Table(title="Deployment Records")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Deployment", style="magenta")
        table.add_column("CPU Usage", style="green")
        table.add_column("RAM Usage", style="yellow")
        table.add_column("Latency (ms)", style="red")
        table.add_column("Request Count", style="blue")
        table.add_column("Error Count", style="magenta")
        table.add_column("Created At", style="white")

        # Assuming records is a list of record objects
        for record in records if isinstance(records, list) else [records]:
            table.add_row(
                str(record.get('id', 'N/A')),
                str(deployment_id),
                str(record.get('cpu_usage', 'N/A')),
                str(record.get('ram_usage', 'N/A')),
                str(record.get('latency_ms', 'N/A')),
                str(record.get('request_count', 'N/A')),
                str(record.get('error_count', 'N/A')),
                str(record.get('created_at', 'N/A'))
            )

        console.print(table)
    except Exception as e:
        typer.echo(f"Failed to fetch records for deployment_id {deployment_id}: {str(e)}")

@monitoring_api_app.command("alert")
def receive_metrics(deployment_id: int = typer.Option(..., prompt=True, help="deployment alerts")):
    client = AIACClient()

    try:
        alerts = client.api_request(f"deployments/{deployment_id}/alerts/", method="GET")
        print_warning(f"Fetching alerts for deployment_id: {deployment_id}")

        table = Table(title="Deployment Alerts")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Deployment", style="magenta")
        table.add_column("Alert Type", style="red")
        table.add_column("Message", style="yellow")
        table.add_column("Created At", style="green")
        table.add_column("Resolved", style="blue")

        # Assuming alerts is a list of alert objects
        for alert in alerts if isinstance(alerts, list) else [alerts]:
            table.add_row(
                str(alert.get('id', 'N/A')),
                str(deployment_id),
                str(alert.get('alert_type', 'N/A')),
                str(alert.get('message', 'N/A')),
                str(alert.get('created_at', 'N/A')),
                str(alert.get('resolved', 'N/A'))
            )

        console.print(table)
    except Exception as e:
        typer.echo(f"Failed to fetch alerts for deployment_id {deployment_id}: {str(e)}")

@monitoring_api_app.command("resolve-alert")
def resolve_alert(alert_id: str = typer.Option(..., prompt=True, help="resolve alert by id")):
    client = AIACClient()

    try:
        response = client.api_request(f"alerts/{alert_id}/resolve/", method="POST")
        print_info(f"Resolving alert with alert_id: {alert_id}")
        typer.echo(f"Alert resolved successfully: {response}")
    except Exception as e:
        typer.echo(f"Failed to resolve alert with alert_id {alert_id}: {str(e)}")

@monitoring_api_app.command("detect-drift")
def detect_drift(model_version_id: int = typer.Option(..., prompt=True, help="detect data drift for model version")):
    client = AIACClient()

    try:
        response = client.api_request(f"drifts/{model_version_id}/", method="GET")
        print_info(f"Detecting drift for model_version_id: {model_version_id}")
        typer.echo(f"Drift detection result: {response}")
    except Exception as e:
        typer.echo(f"Failed to detect drift for model_version_id {model_version_id}: {str(e)}")

@monitoring_api_app.command("samples")
def get_samples(model_version_id: int = typer.Option(..., prompt=True, help="post samples for model version")):
    client = AIACClient()

    try:
        response = client.api_request("deployments/samples/", method="POST", data={"model_version_id": model_version_id})
        print_info(f"Posting samples for model_version_id: {model_version_id}")
        typer.echo(f"Samples posted successfully: {response}")
    except Exception as e:
        typer.echo(f"Failed to post samples for model_version_id {model_version_id}: {str(e)}")
       