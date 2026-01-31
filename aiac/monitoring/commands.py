import typer
from aiac.client import AIACClient
from  aiac.console import console , print_message , print_warning  , print_info
from rich.table import Table


table = Table()

monitoring_api_app = typer.Typer(help = "monitoring commands")

@monitoring_api_app.command("deploy-stats")
def deployment_stats(deployment_id : int = typer.Option(..., prompt=True, help="deployment stats")):
    client = AIACClient()

    response = client.api_request(endpoint="deployments/{deployment_id}/stats/",method="GET")
    if response == 200:
       print_message("Fetching stats for deployment_id : {deployment_id}".format(deployment_id=deployment_id))
       
       table.add_column("deployment","cpu_usage","ram_usage","latency_ms","request_count","error_count","updated_at",justify="right",style="cyan",no_wrap=True)
       Table.add_row("-----------", "-----------", "-----------", "-----------", "-----------","-----------","------------")
       Table.add_row("{deployment_id}","{cpu_usage}","{ram_usage}","{latency_ms}","{request_count}","{error_count}","{updated_at}")
       Table.add_row("-----------", "-----------", "-----------", "-----------", "-----------","-----------","------------")
       console.print(table)
    else:
         typer.echo("Failed to fetch stats for deployment_id : {deployment_id}".format(deployment_id=deployment_id))

@monitoring_api_app.command("deploy-records")
def deployment_records(deployment_id : int = typer.Option(..., prompt=True, help="deployment records")):
    client = AIACClient()

    response = client.api_request(endpoint="deployments/{deployment_id}/records/",method="GET")
    if response == 200:
       print_message("Fetching records for deployment_id : {deployment_id}".format(deployment_id=deployment_id))
       
       table.add_column("id","deployment","cpu_usage","ram_usage","latency_ms","request_count","error_count","created_at",justify="right",style="cyan",no_wrap=True)
       Table.add_row("-----------", "-----------", "-----------", "-----------", "-----------","-----------","-----------","------------")
       Table.add_row("{id}","{deployment_id}","{cpu_usage}","{ram_usage}","{latency_ms}","{request_count}","{error_count}","{created_at}")
       Table.add_row("-----------", "-----------", "-----------", "-----------", "-----------","-----------","-----------","------------")
       console.print(table)
    else:
         typer.echo("Failed to fetch records for deployment_id : {deployment_id}".format(deployment_id=deployment_id))

@monitoring_api_app.command("alert")
def receive_metrics(deployment_id : int = typer.Option(..., prompt=True, help="deployment alerts")):
    client = AIACClient()

    response = client.api_request(endpoint="deployments/{deployment_id}/alerts/",method="GET")
    if response == 200:
       print_warning("Fetching alerts for deployment_id : {deployment_id}".format(deployment_id=deployment_id))
       table.add_column("id","deployment","alert_type","message","created_at","resolved",justify="right",style="cyan",no_wrap=True)
       Table.add_row("-----------", "-----------", "-----------", "-----------", "-----------","------------")
       Table.add_row("{id}","{deployment_id}","{alert_type}","{message}","{created_at}","{resolved}")
       Table.add_row("-----------", "-----------", "-----------", "-----------", "-----------","------------")
       console.print(table)
    else:
         typer.echo("Failed to fetch alerts for deployment_id : {deployment_id}".format(deployment_id=deployment_id))

@monitoring_api_app.command("resolve-alert")
def resolve_alert(alert_id : str = typer.Option(..., prompt=True, help="resolve alert by id")):
    client = AIACClient()
    
    response = client.api_request(endpoint="alerts/{alert_id}/resolve/",method="POST")
    if response != 200:
         typer.echo("Failed to resolve alert with alert_id : {alert_id}".format(alert_id=alert_id))
    else:
        print_info("Resolving alert with alert_id : {alert_id}".format(alert_id=alert_id))
        typer.echo(response.content)

@monitoring_api_app.command("detect-drift")
def detect_drift(model_version_id : int = typer.Option(..., prompt=True, help="detect data drift for model version")):
    client = AIACClient()
    
    response = client.api_request(endpoint="drifts/{model_version_id}/".format(model_version_id=model_version_id),method="GET")
    if response != 200:
         typer.echo("Failed to detect drift for model_version_id : {model_version_id}".format(model_version_id=model_version_id))
    else:
        print_info("Detecting drift for model_version_id : {model_version_id}".format(model_version_id=model_version_id))
        typer.echo(response.content)

@monitoring_api_app.command("samples")
def get_samples(model_version_id : int = typer.Option(..., prompt=True, help="post samples for model version")):
    client = AIACClient()
    
    response = client.api_request(endpoint="deployments/samples/",method="POST", data={"model_version_id": model_version_id})
    if response != 200:
         typer.echo("Failed to post samples for model_version_id : {model_version_id}".format(model_version_id=model_version_id))
    else:
        print_info("posting samples for model_version_id : {model_version_id}".format(model_version_id=model_version_id))
       