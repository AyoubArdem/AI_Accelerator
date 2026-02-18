from aiac.client import AIACClient
import subprocess
import sys
import platform
import time
import socket
import json
import requests
import typer
from aiac.console import console, print_info, print_message, print_warning
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

api_app_deployment = typer.Typer(help="Deployment commands")

def _friendly_deploy_error(error_text: str) -> str:
    if '"port"' in error_text and "already used by another active deployment" in error_text:
        return "Port is already in use by another active deployment. Choose a different port and try again."
    if "Invalid pk" in error_text and "model_version" in error_text:
        return "Model version not found. Please check the ID and try again."
    if "Invalid pk" in error_text and '"user"' in error_text:
        return "User not found. Please check the user ID and try again."
    return f"Failed to deploy model version: {error_text}"


def _is_local_port_available(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _run_deploy_precheck(
    client: AIACClient,
    model_version_id: int,
    port: int,
    check_local_port: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if port < 1 or port > 65535:
        errors.append("Port must be between 1 and 65535.")

    try:
        mv_resp = client.api_request(endpoint="model-versions/", method="GET")
        model_versions = mv_resp.json() if mv_resp is not None else []
        exists = any(str(mv.get("id")) == str(model_version_id) for mv in model_versions)
        if not exists:
            errors.append(f"Model version {model_version_id} was not found.")
    except Exception:
        warnings.append("Could not verify model version existence during precheck.")

    if check_local_port and port >= 1 and port <= 65535 and not _is_local_port_available(port):
        warnings.append(
            f"Local port {port} appears in use on this machine. "
            "If your backend deploys locally, deployment may fail with a port conflict."
        )

    return errors, warnings


def _friendly_advisor_error(error_text: str, deployment_id: int) -> str:
    if "404" in error_text and "Deployment not found" in error_text:
        return (
            f"Deployment {deployment_id} was not found. "
            "Run `deployment list-deployments` and use a valid deployment ID."
        )
    if "403" in error_text and "Access denied" in error_text:
        return "Access denied for this deployment advisor report."
    return f"Failed to get deployment advisor report: {error_text}"


def _friendly_services_error(error_text: str, deployment_id: int) -> str:
    if "404" in error_text and "Deployment not found" in error_text:
        return (
            f"Deployment {deployment_id} was not found. "
            "Run `deployment list-deployments` and use a valid deployment ID."
        )
    if "403" in error_text and "Access denied" in error_text:
        return "Access denied for deployment services."
    return f"Failed to retrieve deployment services: {error_text}"


def _friendly_shadow_error(error_text: str, deployment_id: int) -> str:
    if "404" in error_text and "Deployment not found" in error_text:
        return (
            f"Deployment {deployment_id} was not found. "
            "Run `deployment list-deployments` and use a valid deployment ID."
        )
    if "404" in error_text and "Candidate model version not found" in error_text:
        return "Candidate model version was not found. Use `deployment list-model-versions`."
    if "403" in error_text and "Access denied" in error_text:
        return "Access denied for traffic shadow analysis."
    if "No samples available for shadow test" in error_text:
        return (
            "No samples are available for shadow testing. "
            "Upload samples first using `monitoring samples --model-version-id <id> --data-samples \"[...]\"`, "
            "then rerun traffic-shadow."
        )
    if "Missing dependency `scikit-learn`" in error_text:
        return (
            "Traffic shadow requires `scikit-learn` in the backend environment to load this model. "
            "Install it (e.g. `pip install scikit-learn`) and retry."
        )
    if "Missing dependency `" in error_text:
        return (
            "Traffic shadow could not load model dependencies in backend environment. "
            f"Details: {error_text}"
        )
    return f"Failed to run traffic shadow analysis: {error_text}"


def _friendly_explain_decision_error(error_text: str, deployment_id: int) -> str:
    if "404" in error_text and "Deployment not found" in error_text:
        return (
            f"Deployment {deployment_id} was not found. "
            "Run `deployment list-deployments` and use a valid deployment ID."
        )
    if "invalid features json" in error_text.lower():
        return "Invalid features JSON. Provide a numeric JSON array, for example: \"[0.1, 0.2, 0.3]\"."
    if "runtime endpoint not available" in error_text.lower():
        return (
            "Runtime endpoint is not available for this deployment. "
            "Ensure deployment is ACTIVE and has a valid runtime URL."
        )
    if "runtime request failed: 404" in error_text.lower() or '"detail":"Not Found"' in error_text:
        return (
            "Explainable decision endpoint is not available on this deployment runtime. "
            "Redeploy the model with the latest runtime, then retry `deployment explain-decision`."
        )
    return f"Failed to run explainable decision: {error_text}"


def _suggest_model_version_ids(client: AIACClient, limit: int = 8) -> str:
    try:
        resp = client.api_request(endpoint="model-versions/", method="GET")
        rows = resp.json() if resp is not None else []
        if not isinstance(rows, list) or not rows:
            return "No model versions found. Create one with `deployment create-model-version`."
        ids = []
        for row in rows[: max(1, limit)]:
            mv_id = row.get("id")
            if mv_id is not None:
                ids.append(str(mv_id))
        if not ids:
            return "No model versions found. Create one with `deployment create-model-version`."
        return f"Available model version IDs: {', '.join(ids)}"
    except Exception:
        return "Run `deployment list-model-versions` to find a valid candidate ID."


def _runtime_urls_from_payload(payload: dict) -> dict:
    runtime_urls = payload.get("runtime_urls")
    if isinstance(runtime_urls, dict) and runtime_urls:
        return runtime_urls

    endpoint = str(payload.get("endpoint_url") or "").strip()
    if endpoint:
        base = endpoint[:-8] if endpoint.endswith("/predict") else endpoint.rstrip("/")
    else:
        port = payload.get("port")
        base = f"http://127.0.0.1:{port}" if port else ""
    if not base:
        return {}
    return {
        "base_url": base,
        "ui_page": f"{base}/ui",
        "ui_docs": f"{base}/docs",
        "ui_redoc": f"{base}/redoc",
        "health": f"{base}/health",
        "predict": f"{base}/predict",
        "predict_decision": f"{base}/predict-decision",
    }


def _print_runtime_urls(payload: dict):
    urls = _runtime_urls_from_payload(payload)
    if not urls:
        return
    typer.echo("Runtime URLs:")
    typer.echo(f"- App UI: {urls.get('ui_page')}")
    typer.echo(f"- UI Docs: {urls.get('ui_docs')}")
    typer.echo(f"- UI ReDoc: {urls.get('ui_redoc')}")
    typer.echo(f"- Health: {urls.get('health')}")
    typer.echo(f"- Predict API: {urls.get('predict')}")
    typer.echo(f"- Explainable Decision API: {urls.get('predict_decision')}")


def _check_redis_and_hint(host: str, port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.5)
    try:
        sock.connect((host, port))
        return True
    except Exception:
        print_warning(f"\nRedis is not reachable on {host}:{port}.")
        print_info("If you don't have Redis running, start it with Docker:")
        print_info("  docker run -d --name aiac-redis -p 6379:6379 redis:7")
        print_warning("Make sure Docker Engine/Desktop is running before deploying.\n")
        return False
    finally:
        sock.close()

def _has_celery_worker() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "celery", "-A", "AI_Accelerator", "inspect", "ping", "--timeout=2"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        output = f"{result.stdout}\n{result.stderr}".lower()
        return "pong" in output
    except Exception:
        return False

def _start_worker_and_wait() -> tuple[bool, str]:
    try:
        cmd = [sys.executable, "-m", "celery", "-A", "AI_Accelerator", "worker", "--loglevel=info", "--pool=solo"]
        if platform.system().lower() == "windows":
            # CREATE_NEW_CONSOLE is more reliable than detached mode on Windows.
            subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Give the worker a few seconds to boot and register.
        for _ in range(6):
            time.sleep(2)
            if _has_celery_worker():
                return True, ""
        return False, "Worker process started but did not respond to ping."
    except Exception as e:
        return False, str(e)

@api_app_deployment.command("create-project-deployment")
def create_deployment(owner_id: int = typer.Option(..., prompt=True, help="Owner user ID of the project"),
                        name: str = typer.Option(..., prompt=True, help="Name of the project"),
                        description: str = typer.Option(..., prompt=True, help="Description of the project")):
    """
    Create a new deployment for a specified model version.
    """
    client = AIACClient(base_path="deployment")
    data = {
        "owner": owner_id,
        "name": name,
        "description": description,
    }
    try:
        response = client.api_request(endpoint="projects/", method="POST", data=data)
        typer.echo(f"Project created successfully: {response.json()}")
    except Exception as e:
        typer.echo(f"Failed to create project: {str(e)}")

@api_app_deployment.command("create-model-version")
def create_model_version(project_id: int = typer.Option(..., prompt=True, help="ID of the project"),
                         description: str = typer.Option(..., prompt=True, help="Description of the model version"),
                         field_file_path: str = typer.Option(..., prompt=True, help="Path to the model file")):
    
    """
    Create a new model version for a specified project.
    """
   
    client = AIACClient(base_path="deployment")
    data = {
        "projet": project_id,
        "description": description,
    }
    try:
        with open(field_file_path, "rb") as f:
            files = {"field_file": f}
            response = client.api_request(endpoint="model-versions/", method="POST", data=data, files=files)
        typer.echo(f"Model version created successfully: {response.json()}")
    except Exception as e:
        typer.echo(f"Failed to create model version: {str(e)}")

@api_app_deployment.command("deploy-model-version")
def deploy_model_version(user_id: int = typer.Option(..., prompt=True, help="ID of the user deploying the model"),
                         model_version_id: int = typer.Option(..., prompt=True, help="ID of the model version to deploy"),
                         port: int = typer.Option(..., prompt=True, help="Port to deploy the model version on"),
                         start_worker: bool = typer.Option(True, help="Start Celery worker automatically if not running"),
                         wait: bool = typer.Option(True, help="Wait and show progress until deployment finishes"),
                         poll_interval_seconds: int = typer.Option(2, help="Polling interval (seconds) while waiting"),
                         timeout_seconds: int = typer.Option(900, help="Max time to wait for deployment completion"),
                         precheck: bool = typer.Option(True, help="Run pre-deployment checks before API call"),
                         check_local_port: bool = typer.Option(True, help="Check whether the local port is already in use"),
                         output_format: str = typer.Option("text", "--format", "-f", help="Output format: text or json"),
                         redis_host: str = typer.Option("localhost", help="Redis host for Celery"),
                         redis_port: int = typer.Option(6379, help="Redis port for Celery")):
    """
    Deploy a specified model version.
    """
    if start_worker:
        if not _check_redis_and_hint(redis_host, redis_port):
            typer.echo("Redis is unavailable. Deployment will run in fallback mode if the server supports it.")
        else:
            ok, err = _start_worker_and_wait()
            if not ok:
                typer.echo(f"Worker auto-start failed: {err}")
                typer.echo("Continuing. Server may execute deployment in fallback mode.")

    if not _has_celery_worker():
        typer.echo("No Celery worker detected. Continuing with server fallback if available.")

    client = AIACClient(base_path="deployment")
    if precheck:
        errors, warnings = _run_deploy_precheck(
            client=client,
            model_version_id=model_version_id,
            port=port,
            check_local_port=check_local_port,
        )
        for warning in warnings:
            print_warning(warning)
        if errors:
            for err in errors:
                typer.echo(f"Precheck failed: {err}")
            return

    if poll_interval_seconds < 1:
        typer.echo("poll-interval-seconds must be at least 1.")
        return

    out_fmt = (output_format or "text").strip().lower()
    if out_fmt not in {"text", "json"}:
        typer.echo("Invalid format. Use 'text' or 'json'.")
        return

    data = {
        "user": user_id,
        "model_version": model_version_id,
        "port": port,
    }
    try:
        response = client.api_request(endpoint="deployments/", method="POST", data=data)
        payload = response.json()
        if out_fmt == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
        else:
            summary = Table(title="Deployment Started")
            summary.add_column("Deployment ID", style="cyan")
            summary.add_column("Model Version", style="magenta")
            summary.add_column("Port", style="green")
            summary.add_column("Initial Status", style="yellow")
            summary.add_row(
                str(payload.get("id", "N/A")),
                str(payload.get("model_version", model_version_id)),
                str(payload.get("port", port)),
                str(payload.get("status", "PENDING")),
            )
            console.print(summary)
            typer.echo("Tracking deployment progress...")

        if not wait:
            return

        deployment_id = payload.get("id")
        if not deployment_id:
            typer.echo("No deployment id returned. Cannot track progress.")
            return

        status_progress = {
            "PENDING": 10,
            "DEPLOYING": 60,
            "ACTIVE": 100,
            "STOPPED": 100,
            "FAILED": 100,
            "DELETED": 100,
        }

        start_time = time.time()
        transient_network_failures = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.fields[status]}[/bold]"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            task_id = progress.add_task("Deploying", total=100, status="PENDING")
            while True:
                if time.time() - start_time > timeout_seconds:
                    progress.update(task_id, status="TIMEOUT")
                    typer.echo("\n\nDeployment is still in progress. Check later with get-deployment-details.\n")
                    break

                try:
                    status_resp = client.api_request(endpoint=f"deployments/{deployment_id}/", method="GET")
                    status_payload = status_resp.json()
                    transient_network_failures = 0
                except Exception as e:
                    msg = str(e)
                    if "Network error:" in msg:
                        transient_network_failures += 1
                        if transient_network_failures <= 15:
                            progress.update(task_id, status="WAITING_API")
                            time.sleep(poll_interval_seconds)
                            continue
                    progress.update(task_id, status="ERROR")
                    if "No Deployment matches the given query" in msg:
                        typer.echo("Deployment not found.")
                    else:
                        typer.echo(f"Failed to fetch deployment status: {msg}")
                    break

                status = str(status_payload.get("status", "PENDING")).upper()
                progress.update(task_id, completed=status_progress.get(status, 10), status=status)

                if status in {"ACTIVE", "FAILED", "STOPPED", "DELETED"}:
                    typer.echo(f"\nDeployment finished with status: {status}")
                    if status == "ACTIVE":
                        _print_runtime_urls(status_payload)
                    else:
                        typer.echo(f"Logs: {status_payload.get('logs')}")
                    break

                time.sleep(poll_interval_seconds)

    except Exception as e:
        msg = str(e)
        typer.echo(_friendly_deploy_error(msg))

@api_app_deployment.command("redeploy-model")
def  redeploy_model(deployment_id: int = typer.Option(..., prompt=True, help="ID of the deployment to redeploy"),
                    start_worker: bool = typer.Option(True, help="Start Celery worker automatically if not running"),
                    wait: bool = typer.Option(True, help="Wait and show progress until redeploy finishes"),
                    timeout_seconds: int = typer.Option(900, help="Max time to wait for redeploy completion"),
                    redis_host: str = typer.Option("localhost", help="Redis host for Celery"),
                    redis_port: int = typer.Option(6379, help="Redis port for Celery")):
    """
    Redeploy a specified deployment.
    """
    if start_worker:
        if not _check_redis_and_hint(redis_host, redis_port):
            typer.echo("Redis is unavailable. Redeploy will run in fallback mode if the server supports it.")
        else:
            ok, err = _start_worker_and_wait()
            if not ok:
                typer.echo(f"Worker auto-start failed: {err}")
                typer.echo("Continuing. Server may execute redeploy in fallback mode.")

    if not _has_celery_worker():
        typer.echo("No Celery worker detected. Continuing with server fallback if available.")

    client = AIACClient(base_path="deployment")
    endpoint = f"deployments/{deployment_id}/redeploy/"
    try:
        response = client.api_request(endpoint=endpoint, method="POST")
        typer.echo(f"Deployment redeployed successfully: {response.json()}\n\n")

        if not wait:
            return

        status_progress = {
            "PENDING": 10,
            "DEPLOYING": 60,
            "ACTIVE": 100,
            "STOPPED": 100,
            "FAILED": 100,
            "DELETED": 100,
        }

        start_time = time.time()
        transient_network_failures = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.fields[status]}[/bold]"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            task_id = progress.add_task("Redeploying", total=100, status="PENDING")
            while True:
                if time.time() - start_time > timeout_seconds:
                    progress.update(task_id, status="TIMEOUT")
                    typer.echo("Redeploy is still in progress. Check later with get-deployment-details.")
                    break

                try:
                    status_resp = client.api_request(endpoint=f"deployments/{deployment_id}/", method="GET")
                    status_payload = status_resp.json()
                    transient_network_failures = 0
                except Exception as e:
                    msg = str(e)
                    if "Network error:" in msg:
                        transient_network_failures += 1
                        if transient_network_failures <= 15:
                            progress.update(task_id, status="WAITING_API")
                            time.sleep(2)
                            continue
                    progress.update(task_id, status="ERROR")
                    if "No Deployment matches the given query" in msg:
                        typer.echo("\n\nDeployment not found.\n")
                    else:
                        typer.echo(f"\n\nFailed to fetch deployment status: {msg}")
                    break

                status = str(status_payload.get("status", "PENDING")).upper()
                progress.update(task_id, completed=status_progress.get(status, 10), status=status)

                if status in {"ACTIVE", "FAILED", "STOPPED", "DELETED"}:
                    typer.echo(f"\n\nRedeploy finished with status: {status}")
                    if status == "ACTIVE":
                        _print_runtime_urls(status_payload)
                    else:
                        typer.echo(f"Logs: {status_payload.get('logs')}")
                    break

                time.sleep(2)

    except Exception as e:
        typer.echo(f"\n\nFailed to redeploy deployment: {str(e)}")

@api_app_deployment.command("stop-deployment")
def stop_deployment(deployment_id: int = typer.Option(..., prompt=True, help="ID of the deployment to stop")):
    """
    Stop a specified deployment.
    """
    client = AIACClient(base_path="deployment")
    endpoint = f"deployments/{deployment_id}/stop/"
    try:
        response = client.api_request(endpoint=endpoint, method="POST")
        typer.echo(f"Deployment stopped successfully: {response.json()}")
    except Exception as e:
        msg = str(e)
        if "No running container" in msg:
            typer.echo("No running container to stop.")
        else:
            typer.echo(f"Failed to stop deployment: {msg}")

@api_app_deployment.command("delete-deployment")
def delete_deployment(deployment_id: int = typer.Option(..., prompt=True, help="ID of the deployment to delete"),
                      confirm: bool = typer.Option(True, help="Ask for confirmation before deleting")):
    """
    Delete a specified deployment.
    """
    if confirm:
        if not typer.confirm(f"Are you sure you want to delete deployment {deployment_id}?"):
            typer.echo("Canceled.")
            return
    client = AIACClient(base_path="deployment")
    endpoint = f"deployments/{deployment_id}/delete/"
    try:
        response = client.api_request(endpoint=endpoint, method="DELETE")
        if response.status_code == 204 or not response.text:
            typer.echo("Deployment deleted successfully.")
        else:
            typer.echo(f"Deployment deleted successfully: {response.json()}")
    except Exception as e:
        msg = str(e)
        if "Deployment matching query does not exist" in msg:
            typer.echo("Deployment not found.")
        else:
            typer.echo(f"Failed to delete deployment: {msg}")

@api_app_deployment.command("list-deployments")
def list_deployments():
    """
    List all deployments.
    """
    client = AIACClient(base_path="deployment")
    try:
        response = client.api_request(endpoint="deployments/list/", method="GET")
        typer.echo(f"Deployments: {response.status_code}")
        table = Table(title="Deployments")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("User")
        table.add_column("Project")
        table.add_column("Model Version")
        table.add_column("Port")
        table.add_column("Status")
        table.add_column("Endpoint URL")
        table.add_column("Container Id")
        table.add_column("Logs")
        table.add_column("Deployed At")
        table.add_row("----", "----", "-------", "-------------", "----", "------", "------------", "------------", "----", "-----------")
        for deployment in response.json():
            project_name = "N/A"
            model_version_id = deployment.get("model_version")
            if model_version_id:
                try:
                    mv_resp = client.api_request(endpoint="model-versions/", method="GET")
                    for mv in mv_resp.json():
                        if mv.get("id") == model_version_id:
                            projet = mv.get("projet")
                            # projet can be an ID or object; handle both
                            if isinstance(projet, dict):
                                project_name = projet.get("name", "N/A")
                            else:
                                project_name = str(projet)
                            break
                except Exception:
                    project_name = "N/A"
            table.add_row(
                str(deployment["id"]),
                str(deployment.get("user")),
                project_name,
                str(deployment["model_version"]),
                str(deployment["port"]),
                str(deployment["status"]),
                str(deployment.get("endpoint_url")),
                str(deployment.get("docker_container_id")),
                str(deployment.get("logs")),
                str(deployment.get("deployed_at")),
            )
        table.add_row("----", "----", "-------", "-------------", "----", "------", "------------", "------------", "----", "-----------")
        console.print(table)
    except Exception as e:
        typer.echo(f"Failed to retrieve deployments: {str(e)}")

@api_app_deployment.command("get-deployment-details")
def get_deployment_details(deployment_id: int = typer.Option(..., prompt=True, help="ID of the deployment to get details for")):
    """
    Get details of a specified deployment.
    """
    client = AIACClient(base_path="deployment")
    endpoint = f"deployments/{deployment_id}/"
    try:
        response = client.api_request(endpoint=endpoint, method="GET")
        typer.echo(f"Deployment details: {response.status_code}")
        payload = response.json()
        project_name = "N/A"
        model_version_id = payload.get("model_version")
        if model_version_id:
            try:
                mv_resp = client.api_request(endpoint="model-versions/", method="GET")
                for mv in mv_resp.json():
                    if mv.get("id") == model_version_id:
                        projet = mv.get("projet")
                        if isinstance(projet, dict):
                            project_name = projet.get("name", "N/A")
                        else:
                            project_name = str(projet)
                        break
            except Exception:
                project_name = "N/A"
        table = Table(title="Deployment Details")
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_row("project", project_name)
        for key, value in payload.items():
            table.add_row(key, str(value))
        runtime_urls = _runtime_urls_from_payload(payload)
        if runtime_urls:
            table.add_row("ui_page", str(runtime_urls.get("ui_page", "")))
            table.add_row("ui_docs", str(runtime_urls.get("ui_docs", "")))
            table.add_row("ui_redoc", str(runtime_urls.get("ui_redoc", "")))
            table.add_row("health", str(runtime_urls.get("health", "")))
            table.add_row("predict", str(runtime_urls.get("predict", "")))
            table.add_row("predict_decision", str(runtime_urls.get("predict_decision", "")))
        console.print(table)
    except Exception as e:
        typer.echo(f"Failed to retrieve deployment details: {str(e)}")


@api_app_deployment.command("advisor")
def deployment_advisor(
    deployment_id: int = typer.Option(..., prompt=True, help="Deployment ID for advisor report"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """Advanced deployment advisor with risk and strategy recommendations."""
    client = AIACClient(base_path="deployment")
    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return

        response = client.api_request(endpoint=f"deployments/{deployment_id}/advisor/", method="GET")
        payload = response.json()

        if fmt == "json":
            typer.echo(str(payload))
            return

        table = Table(title="Deployment Advisor")
        table.add_column("Deployment", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Score", style="green")
        table.add_column("Risk", style="magenta")
        table.add_column("Strategy", style="red")
        table.add_row(
            str(payload.get("deployment_id", deployment_id)),
            str(payload.get("status", "N/A")),
            str(payload.get("advisor_score", "N/A")),
            str(payload.get("risk_level", "N/A")),
            str(payload.get("recommended_strategy", "N/A")),
        )
        console.print(table)

        metrics = payload.get("metrics", {})
        metrics_table = Table(title="Runtime Metrics")
        metrics_table.add_column("CPU")
        metrics_table.add_column("RAM")
        metrics_table.add_column("Latency")
        metrics_table.add_column("Requests")
        metrics_table.add_column("Errors")
        metrics_table.add_column("Error Rate %")
        metrics_table.add_row(
            str(metrics.get("cpu_usage", 0)),
            str(metrics.get("ram_usage", 0)),
            str(metrics.get("latency_ms", 0)),
            str(metrics.get("request_count", 0)),
            str(metrics.get("error_count", 0)),
            str(metrics.get("error_rate_pct", 0)),
        )
        console.print(metrics_table)

        typer.echo(
            f"Unresolved alerts: {payload.get('unresolved_alerts', 0)} | Drift high: {payload.get('drift_high', False)}"
        )
        for reason in payload.get("reasons", []):
            typer.echo(f"- Reason: {reason}")
        for rec in payload.get("recommendations", []):
            typer.echo(f"- Recommendation: {rec}")
    except Exception as e:
        typer.echo(_friendly_advisor_error(str(e), deployment_id))


@api_app_deployment.command("services")
def deployment_services(
    deployment_id: int = typer.Option(..., prompt=True, help="Deployment ID for service URLs"),
    probe: bool = typer.Option(False, "--probe", help="Probe /health endpoint while fetching URLs."),
    timeout: int = typer.Option(2, "--timeout", help="Health probe timeout in seconds (1-10)."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """Show all runtime service URLs for a deployment, with optional health probe."""
    client = AIACClient(base_path="deployment")
    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return
        timeout = max(1, min(timeout, 10))

        endpoint = f"deployments/{deployment_id}/services/?probe={str(probe).lower()}&timeout={timeout}"
        response = client.api_request(endpoint=endpoint, method="GET")
        payload = response.json()

        if fmt == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return

        info = Table(title="Deployment Services")
        info.add_column("Deployment", style="cyan")
        info.add_column("Status", style="yellow")
        info.add_column("Probe", style="magenta")
        info.add_row(
            str(payload.get("deployment_id", deployment_id)),
            str(payload.get("status", "N/A")),
            "enabled" if payload.get("probe", {}).get("enabled") else "disabled",
        )
        console.print(info)

        services = payload.get("services", {})
        urls_table = Table(title="Service URLs")
        urls_table.add_column("Service", style="cyan")
        urls_table.add_column("URL", style="green")
        for key in ["base_url", "ui_page", "ui_docs", "ui_redoc", "health", "predict", "predict_decision"]:
            urls_table.add_row(key, str(services.get(key, "")))
        console.print(urls_table)

        probe_payload = payload.get("probe", {})
        if probe_payload.get("enabled"):
            typer.echo(
                f"Health probe: ok={probe_payload.get('health_ok')} "
                f"error={probe_payload.get('health_error')}"
            )
            if probe_payload.get("health_response") is not None:
                typer.echo(f"Health response: {probe_payload.get('health_response')}")
    except Exception as e:
        typer.echo(_friendly_services_error(str(e), deployment_id))


@api_app_deployment.command("traffic-shadow")
def deployment_traffic_shadow(
    deployment_id: int = typer.Option(..., prompt=True, help="Active deployment ID to compare from"),
    candidate_model_version_id: int = typer.Option(..., "--candidate", "-c", help="Candidate model version ID"),
    sample_limit: int = typer.Option(200, "--samples", "-s", help="Number of recent samples to evaluate (10-1000)."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """Compare active deployment model against a candidate model using recent samples."""
    client = AIACClient(base_path="deployment")
    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return
        sample_limit = max(10, min(sample_limit, 1000))

        endpoint = (
            f"deployments/{deployment_id}/traffic-shadow/"
            f"?candidate_model_version_id={candidate_model_version_id}"
            f"&sample_limit={sample_limit}"
        )
        response = client.api_request(endpoint=endpoint, method="GET")
        payload = response.json()

        if fmt == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return

        top = Table(title="Traffic Shadow Result")
        top.add_column("Deployment", style="cyan")
        top.add_column("Current Model", style="yellow")
        top.add_column("Candidate", style="magenta")
        top.add_column("Samples", style="green")
        top.add_column("Recommendation", style="red")
        top.add_row(
            str(payload.get("deployment_id")),
            str(payload.get("current_model_version_id")),
            str(payload.get("candidate_model_version_id")),
            str(payload.get("sample_count")),
            str(payload.get("recommendation")),
        )
        console.print(top)

        m = payload.get("shadow_metrics", {})
        mt = Table(title="Shadow Metrics")
        mt.add_column("Match Rate")
        mt.add_column("Matches")
        mt.add_column("Current Latency (ms)")
        mt.add_column("Candidate Latency (ms)")
        mt.add_column("Latency Ratio")
        mt.add_column("Avg Abs Diff")
        mt.add_row(
            str(m.get("prediction_match_rate")),
            str(m.get("prediction_matches")),
            str(m.get("current_latency_ms")),
            str(m.get("candidate_latency_ms")),
            str(m.get("latency_ratio_candidate_vs_current")),
            str(m.get("avg_abs_prediction_diff")),
        )
        console.print(mt)

        typer.echo(f"Reason: {payload.get('reason')}")
    except Exception as e:
        msg = str(e)
        if "Candidate model version not found" in msg:
            base_msg = _friendly_shadow_error(msg, deployment_id)
            suggestions = _suggest_model_version_ids(client)
            typer.echo(f"{base_msg} {suggestions}")
            return
        typer.echo(_friendly_shadow_error(msg, deployment_id))


@api_app_deployment.command("explain-decision")
def deployment_explain_decision(
    deployment_id: int = typer.Option(..., prompt=True, help="Active deployment ID to query."),
    features: str = typer.Option(
        "",
        "--features",
        "-x",
        help='JSON numeric feature array, for example "[0.1, 0.2, 0.3]".',
    ),
    min_confidence: float = typer.Option(None, "--min-confidence", help="Refuse if confidence is below this value."),
    min_margin: float = typer.Option(None, "--min-margin", help="Refuse if top-2 class margin is below this value."),
    blocked_labels: str = typer.Option(
        "",
        "--blocked-labels",
        help='Comma-separated labels to refuse, for example "denied,blocked".',
    ),
    fallback: bool = typer.Option(
        True,
        "--fallback/--no-fallback",
        help="If /predict-decision is unavailable, fallback to /predict.",
    ),
    timeout: int = typer.Option(10, "--timeout", help="Runtime request timeout in seconds."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """Run explainable decision endpoint with configurable refusal checks."""
    client = AIACClient(base_path="deployment")
    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return

        raw_features = features.strip()
        if not raw_features:
            raw_features = typer.prompt('Features JSON (example: [0.1, 0.2, 0.3])')
        try:
            parsed_features = json.loads(raw_features)
        except json.JSONDecodeError as e:
            raise Exception(f"invalid features JSON ({e.msg})")

        if not isinstance(parsed_features, list) or not parsed_features:
            raise Exception("invalid features JSON: expected a non-empty JSON array.")
        if any(not isinstance(v, (int, float)) for v in parsed_features):
            raise Exception("invalid features JSON: all features must be numeric.")

        deployment_resp = client.api_request(endpoint=f"deployments/{deployment_id}/", method="GET")
        deployment_payload = deployment_resp.json()
        urls = _runtime_urls_from_payload(deployment_payload)
        decision_url = urls.get("predict_decision")
        if not decision_url:
            raise Exception("runtime endpoint not available")

        body = {"features": parsed_features}
        if min_confidence is not None:
            body["min_confidence"] = min_confidence
        if min_margin is not None:
            body["min_margin"] = min_margin
        blocked = [x.strip() for x in blocked_labels.split(",") if x.strip()]
        if blocked:
            body["blocked_labels"] = blocked

        response = requests.post(decision_url, json=body, timeout=max(1, timeout))
        if response.status_code == 404 and fallback:
            predict_url = urls.get("predict")
            if not predict_url:
                raise Exception("runtime request failed: 404 - decision endpoint missing and predict endpoint unavailable")
            fallback_resp = requests.post(
                predict_url,
                json={"features": parsed_features},
                timeout=max(1, timeout),
            )
            if fallback_resp.status_code >= 400:
                raise Exception(
                    f"runtime fallback request failed: {fallback_resp.status_code} - {fallback_resp.text}"
                )
            raw = fallback_resp.json()
            fallback_prediction = raw.get("prediction")
            if isinstance(fallback_prediction, list) and fallback_prediction:
                fallback_prediction = fallback_prediction[0]

            top_probs = []
            probs = raw.get("probabilities")
            if isinstance(probs, list) and probs and isinstance(probs[0], list):
                row = [float(x) for x in probs[0]]
                indexed = [(idx, val) for idx, val in enumerate(row)]
                indexed.sort(key=lambda x: x[1], reverse=True)
                for idx, val in indexed[:3]:
                    top_probs.append({"class_index": idx, "probability": round(val, 6)})

            result = {
                "decision": "approved_with_fallback",
                "prediction": fallback_prediction,
                "reasons": [
                    "Explainable decision endpoint not found on runtime.",
                    "Fallback prediction endpoint was used.",
                    "Refusal checks (confidence/margin/blocked labels) were not enforced.",
                ],
                "refusal_policy": {
                    "mode": "fallback_predict_only",
                    "enforced": False,
                },
                "explanation": {
                    "confidence": None,
                    "margin": None,
                    "top_probabilities": top_probs,
                    "linear_feature_contributions": [],
                    "feature_importance_summary": [],
                },
                "raw_output": raw,
                "fallback_used": True,
            }
        else:
            if response.status_code >= 400:
                raise Exception(f"runtime request failed: {response.status_code} - {response.text}")
            result = response.json()

        if fmt == "json":
            typer.echo(json.dumps(result, indent=2, default=str))
            return

        top = Table(title="Explainable Decision")
        top.add_column("Deployment", style="cyan")
        top.add_column("Decision", style="yellow")
        top.add_column("Prediction", style="green")
        top.add_column("Confidence", style="magenta")
        top.add_column("Margin", style="blue")
        top.add_row(
            str(deployment_id),
            str(result.get("decision", "N/A")),
            str(result.get("prediction", "N/A")),
            str(result.get("explanation", {}).get("confidence", "N/A")),
            str(result.get("explanation", {}).get("margin", "N/A")),
        )
        console.print(top)

        # High-level interpretation to make the decision output easier to understand.
        explanation = result.get("explanation", {}) if isinstance(result, dict) else {}
        confidence = explanation.get("confidence")
        margin = explanation.get("margin")
        fallback_used = bool(result.get("fallback_used", False))
        policy = result.get("refusal_policy", {}) if isinstance(result, dict) else {}
        decision = str(result.get("decision", "N/A"))

        typer.echo("Interpretation:")
        if fallback_used:
            typer.echo("- Runtime used fallback mode (/predict). Refusal checks were not enforced.")
        else:
            if confidence is None or margin is None:
                typer.echo(
                    "- This model/runtime does not expose probability scores, "
                    "so confidence/margin checks could not be evaluated."
                )
            else:
                typer.echo(
                    f"- Confidence check: observed={confidence} "
                    f"threshold={policy.get('min_confidence', 'N/A')}"
                )
                typer.echo(
                    f"- Margin check: observed={margin} "
                    f"threshold={policy.get('min_margin', 'N/A')}"
                )
            if decision == "refused":
                typer.echo("- Final outcome: request was refused by safety/uncertainty policy.")
            elif decision == "approved":
                typer.echo("- Final outcome: request was approved by runtime policy checks.")
            else:
                typer.echo(f"- Final outcome: {decision}.")

        reasons = result.get("reasons", [])
        if reasons:
            typer.echo("Reasons:")
            for reason in reasons:
                typer.echo(f"- {reason}")

        probs = result.get("explanation", {}).get("top_probabilities", [])
        if probs:
            probs_table = Table(title="Top Probabilities")
            probs_table.add_column("Class Index", style="cyan")
            probs_table.add_column("Probability", style="green")
            for row in probs:
                probs_table.add_row(
                    str(row.get("class_index")),
                    str(row.get("probability")),
                )
            console.print(probs_table)

        linear = result.get("explanation", {}).get("linear_feature_contributions", [])
        if linear:
            linear_table = Table(title="Linear Feature Contributions")
            linear_table.add_column("Feature", style="cyan")
            linear_table.add_column("Value")
            linear_table.add_column("Weight", style="yellow")
            linear_table.add_column("Contribution", style="magenta")
            for row in linear:
                linear_table.add_row(
                    str(row.get("feature_index")),
                    str(row.get("feature_value")),
                    str(row.get("weight")),
                    str(row.get("contribution")),
                )
            console.print(linear_table)

            # Brief impact summary: strongest positive and negative contributors.
            try:
                ranked = sorted(
                    linear,
                    key=lambda r: abs(float(r.get("contribution", 0.0))),
                    reverse=True,
                )
                positives = [r for r in ranked if float(r.get("contribution", 0.0)) > 0]
                negatives = [r for r in ranked if float(r.get("contribution", 0.0)) < 0]
                typer.echo("Contribution summary:")
                if positives:
                    p = positives[0]
                    typer.echo(
                        f"- Strongest positive driver: feature {p.get('feature_index')} "
                        f"(contribution={p.get('contribution')})"
                    )
                if negatives:
                    n = negatives[0]
                    typer.echo(
                        f"- Strongest negative driver: feature {n.get('feature_index')} "
                        f"(contribution={n.get('contribution')})"
                    )
                if not positives and not negatives:
                    typer.echo("- No directional feature contributions were found.")
            except Exception:
                pass
    except Exception as e:
        typer.echo(_friendly_explain_decision_error(str(e), deployment_id))


@api_app_deployment.command("list-projects")
def list_projects():
    """
    List all projects.
    """
    client = AIACClient(base_path="deployment")
    try:
        response = client.api_request(endpoint="projects/", method="GET")
        typer.echo(f"Projects: {response.status_code}")
        table = Table(title="Projects")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Owner")
        table.add_column("Project Name")
        table.add_column("Description")
        table.add_column("Created At")
        table.add_row("----", "-------", "-------------", "-----------", "----------")
        for project in response.json():
            table.add_row(
                str(project["id"]),
                str(project["owner"]),
                str(project["name"]),
                str(project["description"]),
                str(project["created_at"]),
            )
        table.add_row("----", "-------", "-------------", "-----------", "----------")
        console.print(table)
    except Exception as e:
        typer.echo(f"Failed to retrieve projects: {str(e)}")

@api_app_deployment.command("list-model-versions")
def list_model_versions():
    """
    List all model versions.
    """
    client = AIACClient(base_path="deployment")
    try:
        response = client.api_request(endpoint="model-versions/", method="GET")
        typer.echo(f"Model Versions: {response.status_code}")
        table = Table(title="Model Versions")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Project")
        table.add_column("Description")
        table.add_column("Field File")
        table.add_column("Created At")
        table.add_column("Updated At")
        table.add_column("Deployed")
        table.add_row("----", "-------", "-----------", "----------", "----------", "----------", "--------")
        for model_version in response.json():
            table.add_row(
                str(model_version["id"]),
                str(model_version["projet"]),
                str(model_version["description"]),
                str(model_version["field_file"]),
                str(model_version["created_at"]),
                str(model_version["updated_at"]),
                str(model_version["deployed"]),
            )
        table.add_row("----", "-------", "-----------", "----------", "----------", "----------", "--------")
        console.print(table)
    except Exception as e:
        typer.echo(f"Failed to retrieve model versions: {str(e)}")



@api_app_deployment.command("delete-project")
def delete_project(project_id: int = typer.Option(..., prompt=True, help="ID of the project to delete"),
                   confirm: bool = typer.Option(True, help="Ask for confirmation before deleting")):
    """
    Delete a specified project.
    """
    if confirm:
        if not typer.confirm(f"Are you sure you want to delete project {project_id}?"):
            typer.echo("Canceled.")
            return
    client = AIACClient(base_path="deployment")
    endpoint = f"projects/{project_id}/delete/"
    try:
        response = client.api_request(endpoint=endpoint, method="DELETE")
        if response.status_code == 204 or not response.text:
            typer.echo("Project deleted successfully.")
        else:
            typer.echo(f"Project deleted successfully: {response.json()}")
    except Exception as e:
        msg = str(e)
        if "No Projet matches the given query" in msg:
            typer.echo("Project not found.")
        else:
            typer.echo(f"Failed to delete project: {msg}")


@api_app_deployment.command("delete-model-version")
def delete_model_version(model_version_id: int = typer.Option(..., prompt=True, help="ID of the model version to delete"),
                         confirm: bool = typer.Option(True, help="Ask for confirmation before deleting")):
    """
    Delete a specified model version.
    """
    if confirm:
        if not typer.confirm(f"Are you sure you want to delete model version {model_version_id}?"):
            typer.echo("Canceled.")
            return
    client = AIACClient(base_path="deployment")
    endpoint = f"model-versions/{model_version_id}/delete/"
    try:
        response = client.api_request(endpoint=endpoint, method="DELETE")
        if response.status_code == 204 or not response.text:
            typer.echo("Model version deleted successfully.")
        else:
            typer.echo(f"Model version deleted successfully: {response.json()}")
    except Exception as e:
        typer.echo(f"Failed to delete model version: {str(e)}")
