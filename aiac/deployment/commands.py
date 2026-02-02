from aiac.client import AIACClient
import typer
from aiac.console import console, print_info, print_message, print_warning
from rich.table import Table

api_app_deployment = typer.Typer(help="Deployment commands")

@api_app_deployment.command("create-project-deployment")
def create_deployment(owner: str = typer.Option(..., prompt=True, help="Owner of the project"),
                        project_name: str = typer.Option(..., prompt=True, help="Name of the project"),
                        description: str = typer.Option(..., prompt=True, help="Description of the project")):
    """
    Create a new deployment for a specified model version.
    """
    client = AIACClient()
    data = {
        "owner": owner,
        "project_name": project_name,
        "description": description,
      
    }
    try:
        response = client.api_request(endpoint="projects/", method="POST", data=data)
        typer.echo(f"Project created successfully: {response}")
    except Exception as e:
        typer.echo(f"Failed to create project: {str(e)}")

@api_app_deployment.command("create-model-version")
def create_model_version(project_id: int = typer.Option(..., prompt=True, help="ID of the project"),
                         description: str = typer.Option(..., prompt=True, help="Description of the model version"),
                         field_file_path: str = typer.Option(..., prompt=True, help="Path to the model file"),
                         sample_data: str = typer.Option(...,prompt=True, help="Path to the sample data CSV file")):
    
    """
    Create a new model version for a specified project.
    """
   
    client = AIACClient()
    data = {
            "project_id": project_id,
            "description": description,
            "field_file": field_file_path,
            "sample_data": sample_data,
        }
    try:
        response = client.api_request(endpoint="model-versions/", method="POST", data=data)
        typer.echo(f"Model version created successfully: {response}")
    except Exception as e:
        typer.echo(f"Failed to create model version: {str(e)}")

@api_app_deployment.command("deploy-model-version")
def deploy_model_version(user_id: int = typer.Option(..., prompt=True, help="ID of the user deploying the model"),
                         model_version_id: int = typer.Option(..., prompt=True, help="ID of the model version to deploy"),
                         port: int = typer.Option(..., prompt=True, help="Port to deploy the model version on")):
    """
    Deploy a specified model version.
    """
    client = AIACClient()
    data = {
        "user_id": user_id,
        "model_version_id": model_version_id,
        "port": port,
    }
    response = client.api_request(endpoint="deployments/", method="POST", data=data)
    if response.status_code == 201:
            typer.echo(f"Model version deployed successfully: {response}")
    else:
            typer.echo(f"Failed to deploy model version: {response}")

@api_app_deployment.command("redeploy-model")
def  redeploy_model(deployment_id: int = typer.Option(..., prompt=True, help="ID of the deployment to redeploy")):
    """
    Redeploy a specified deployment.
    """
    client = AIACClient()
    endpoint = f"deployments/{deployment_id}/redeploy/"
    response = client.api_request(endpoint=endpoint, method="POST")
    if response.status_code == 200:
        typer.echo(f"Deployment redeployed successfully: {response}")
    else:
        typer.echo(f"Failed to redeploy deployment: {response}")

@api_app_deployment.command("stop-deployment")
def stop_deployment(deployment_id: int = typer.Option(..., prompt=True, help="ID of the deployment to stop")):
    """
    Stop a specified deployment.
    """
    client = AIACClient()
    endpoint = f"deployments/{deployment_id}/stop/"
    response = client.api_request(endpoint=endpoint, method="POST")
    if response.status_code == 200:
        typer.echo(f"Deployment stopped successfully: {response}")
    else:
        typer.echo(f"Failed to stop deployment: {response}")

@api_app_deployment.command("delete-deployment")
def delete_deployment(deployment_id: int = typer.Option(..., prompt=True, help="ID of the deployment to delete")):
    """
    Delete a specified deployment.
    """
    client = AIACClient()
    endpoint = f"deployments/{deployment_id}/delete/"
    response = client.api_request(endpoint=endpoint, method="DELETE")
    if response.status_code == 200:
        typer.echo(f"Deployment deleted successfully: {response}")
    else:
        typer.echo(f"Failed to delete deployment: {response}")

@api_app_deployment.command("list-deployments")
def list_deployments():
    """
    List all deployments.
    """
    client = AIACClient()
    response = client.api_request(endpoint="deployments/list/", method="GET")
    if response.status_code == 200:
        typer.echo(f"Deployments: {response}")
        Table = Table(title="Deployments")
        Table.add_column("ID", "Project", "Model Version", "Port", "Status","Server_IP","endpoint_url","Container_Id","Logs","Created", justify="right" , style="cyan", no_wrap=True)
        Table.add_row("----", "-------", "-------------", "----", "------","---------","------------","------------","----","-------")
        for deployment in response.json():
            Table.add_row(
                str(deployment["id"]),
                str(deployment["project"]),
                str(deployment["model_version"]),
                str(deployment["port"]),
                str(deployment["status"]),
                str(deployment["server_ip"]),
                str(deployment["endpoint_url"]),
                str(deployment["docker_container_id"]),
                str(deployment["logs"]),
                str(deployment["created_at"]),
            )
        Table.add_row("----", "-------", "-------------", "----", "------","---------","------------","------------","----","-------")
        console.print(Table)
    else:
        typer.echo(f"Failed to retrieve deployments: {response}")

@api_app_deployment.command("get-deployment-details")
def get_deployment_details(deployment_id: int = typer.Option(..., prompt=True, help="ID of the deployment to get details for")):
    """
    Get details of a specified deployment.
    """
    client = AIACClient()
    endpoint = f"deployments/{deployment_id}/"
    response = client.api_request(endpoint=endpoint, method="GET")
    if response.status_code == 200:
        typer.echo(f"Deployment details: {response}")
        Table = Table(title="Deployment Details")
        Table.add_column("Field", style="cyan", no_wrap=True)
        for key, value in response.json().items():
            Table.add_row(key, str(value))
        console.print(Table)
    else:
        typer.echo(f"Failed to retrieve deployment details: {response}")

@api_app_deployment.command("list-projects")
def list_projects():
    """
    List all projects.
    """
    client = AIACClient()
    response = client.api_request(endpoint="projects/", method="GET")
    if response.status_code == 200:
        typer.echo(f"Projects: {response}")
        Table = Table(title="Projects")
        Table.add_column("ID", "Owner", "Project Name", "Description", "Created At", justify="right" , style="cyan", no_wrap=True)
        Table.add_row("----", "-------", "-------------", "-----------", "----------")
        for project in response.json():
            Table.add_row(
                str(project["id"]),
                str(project["owner"]),
                str(project["project_name"]),
                str(project["description"]),
                str(project["created_at"]),
            )
        Table.add_row("----", "-------", "-------------", "-----------", "----------")
        console.print(Table)
    else:
        typer.echo(f"Failed to retrieve projects: {response}")

@api_app_deployment.command("list-model-versions")
def list_model_versions():
    """
    List all model versions.
    """
    client = AIACClient()
    response = client.api_request(endpoint="model-versions/", method="GET")
    if response.status_code == 200:
        typer.echo(f"Model Versions: {response}")
        Table = Table(title="Model Versions")
        Table.add_column("ID", "Project", "Description", "Field File", "Created At", "Updated At", "Deployed", justify="right" , style="cyan", no_wrap=True)
        Table.add_row("----", "-------", "-----------", "----------", "----------", "----------", "--------")
        for model_version in response.json():
            Table.add_row(
                str(model_version["id"]),
                str(model_version["projet"]),
                str(model_version["description"]),
                str(model_version["field_file"]),
                str(model_version["created_at"]),
                str(model_version["updated_at"]),
                str(model_version["deployed"]),
            )
        Table.add_row("----", "-------", "-----------", "----------", "----------", "----------", "--------")
        console.print(Table)
    else:
        typer.echo(f"Failed to retrieve model versions: {response}")



@api_app_deployment.command("delete-project")
def delete_project(project_id: int = typer.Option(..., prompt=True, help="ID of the project to delete")):
    """
    Delete a specified project.
    """
    client = AIACClient()
    endpoint = f"projects/{project_id}/delete/"
    response = client.api_request(endpoint=endpoint, method="DELETE")
    if response.status_code == 200:
        typer.echo(f"Project deleted successfully: {response}")
    else:
        typer.echo(f"Failed to delete project: {response}")


@api_app_deployment.command("delete-model-version")
def delete_model_version(model_version_id: int = typer.Option(..., prompt=True, help="ID of the model version to delete")):
    """
    Delete a specified model version.
    """
    client = AIACClient()
    endpoint = f"model-versions/{model_version_id}/delete/"
    response = client.api_request(endpoint=endpoint, method="DELETE")
    if response.status_code == 200:
        typer.echo(f"Model version deleted successfully: {response}")
    else:
        typer.echo(f"Failed to delete model version: {response}")