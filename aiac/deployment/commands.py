from aiac.client import AIACClient
import subprocess
import sys
import platform
import time
import socket
import json
import requests
import typer
import re
import os
from pathlib import Path
from aiac.console import console, print_info, print_message, print_warning
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

api_app_deployment = typer.Typer(help="Deployment commands")


def _load_k8s_clients(kubeconfig: str = "", context: str = ""):
    try:
        from kubernetes import client as k8s_client
        from kubernetes import config as k8s_config
        from kubernetes.client.exceptions import ApiException
    except Exception:
        return None, None, None, (
            "Kubernetes SDK is not installed.\n"
            "Install it with `pip install kubernetes` and retry."
        )

    # Normalize kubeconfig path to support values like %USERPROFILE%\.kube\config.
    kubeconfig_path = ""
    if kubeconfig:
        kubeconfig_path = os.path.expanduser(os.path.expandvars(kubeconfig.strip()))

    def _try_load():
        if kubeconfig_path:
            if not Path(kubeconfig_path).exists():
                raise FileNotFoundError(
                    f"Kubeconfig file was not found at '{kubeconfig_path}'."
                )
            k8s_config.load_kube_config(
                config_file=kubeconfig_path,
                context=context or None,
            )
        else:
            k8s_config.load_kube_config(context=context or None)

    first_error = None
    try:
        _try_load()
    except Exception as e:
        first_error = e
        # Best-effort local auto-fix for Minikube users.
        try:
            subprocess.run(
                ["minikube", "update-context"],
                capture_output=True,
                text=True,
                check=False,
            )
            _try_load()
        except Exception:
            # Fallback to in-cluster config if running inside Kubernetes.
            try:
                k8s_config.load_incluster_config()
            except Exception as in_cluster_error:
                details = str(first_error or in_cluster_error)
                return None, None, None, (
                    "Unable to load Kubernetes configuration.\n"
                    "AIAC tried: kubeconfig, minikube context refresh, then in-cluster config.\n"
                    "Fix options:\n"
                    "1) Start local cluster: `minikube start --driver=docker`\n"
                    "2) Refresh context: `minikube update-context`\n"
                    "3) Pass explicit config: `--kubeconfig $env:USERPROFILE\\.kube\\config` (PowerShell)\n"
                    f"Details: {details}"
                )

    return k8s_client, k8s_client.AppsV1Api(), k8s_client.CoreV1Api(), ApiException

def _is_html_error_blob(text: str) -> bool:
    t = (text or "").lower()
    return "<!doctype html>" in t or "<html" in t


def _friendly_backend_error(prefix: str, error_text: str) -> str:
    text = str(error_text or "")
    lowered = text.lower()
    if "403" in lowered and "admin access required" in lowered:
        match = re.search(r"Contact admin:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text)
        contact = match.group(1) if match else None
        contact_line = (
            f"Contact admin: {contact}"
            if contact
            else "Login with an admin account, or ask an admin to approve/reject/retire this model version."
        )
        return (
            f"{prefix}: admin access is required.\n"
            f"{contact_line}"
        )
    if "submitted file is empty" in text.lower():
        return (
            f"{prefix}: uploaded model file is empty.\n"
            "Use a valid non-empty model file, then retry.\n"
            "Tip: if a token refresh happened, rerun the command once."
        )
    if "API server is not reachable" in text:
        return text
    if "OperationalError" in text:
        return (
            f"{prefix}: backend database is not ready.\n"
            "Make sure the server is started with migrations:\n"
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


def _friendly_deploy_error(error_text: str) -> str:
    lowered = (error_text or "").lower()
    if "401" in lowered or "token_not_valid" in lowered or "user_not_found" in lowered:
        return (
            "Authentication is invalid or expired. "
            "Please run `aiac auth login` and retry deployment."
        )
    if "model version must be approved" in lowered:
        return (
            "Model version is not approved yet. "
            "Approve it first with `aiac deployment approve-model-version --model-version-id <id>`."
        )
    if '"port"' in error_text and "already used by another active deployment" in error_text:
        return "Port is already in use by another active deployment. Choose a different port and try again."
    if "Invalid pk" in error_text and "model_version" in error_text:
        return "Model version not found. Please check the ID and try again."
    if "Invalid pk" in error_text and '"user"' in error_text:
        return "User not found. Please check the user ID and try again."
    return _friendly_backend_error("Failed to deploy model version", error_text)


def _is_auth_error(error_text: str) -> bool:
    txt = (error_text or "").lower()
    return (
        "401" in txt
        or "token_not_valid" in txt
        or "token is expired" in txt
        or "user_not_found" in txt
        or "given token not valid" in txt
    )


def _friendly_deployment_lookup_error(error_text: str, deployment_id: int, action: str) -> str:
    if _is_auth_error(error_text):
        return "Session expired or authentication is invalid. Please run `aiac auth login` and try again."
    txt = (error_text or "")
    if "No Deployment matches the given query" in txt or ("404" in txt and "Deployment not found" in txt):
        return f"Deployment '{deployment_id}' was not found. Run `aiac deployment list-deployments` and use a valid ID."
    return f"Failed to {action}: {txt}"


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
    except Exception as e:
        if _is_auth_error(str(e)):
            errors.append("Authentication is invalid or expired. Run `aiac auth login`.")
        else:
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


def _friendly_create_project_error(error_text: str) -> str:
    if _is_auth_error(error_text):
        return "Session expired or authentication is invalid. Please run `aiac auth login` and try again."
    txt = str(error_text or "")
    if '"owner"' in txt and "Invalid pk" in txt and "does not exist" in txt:
        return (
            "Owner ID not found. Please use a valid user ID.\n"
            "Tip: run `aiac auth me` to see your current user ID."
        )
    return _friendly_backend_error("Failed to create project", txt)


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
    if "features, but" in error_text and "expecting" in error_text:
        return (
            "Feature mismatch between uploaded samples and model input schema.\n"
            "Your samples have a different number of columns than the model expects "
            "(often because CSV includes the target/label column).\n"
            "Upload feature-only samples with the exact same feature count used in training, then rerun traffic-shadow."
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


def _redis_reachable(host: str, port: int, timeout: float = 1.5) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        sock.close()


def _docker_cli_available() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if result.returncode == 0:
            return True, (result.stdout or "").strip()
        detail = (result.stderr or result.stdout or "").strip()
        return False, detail or "Docker CLI not available."
    except Exception as e:
        return False, str(e)


def _docker_daemon_ready() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        if result.returncode == 0:
            return True, "Docker daemon is reachable."
        detail = (result.stderr or result.stdout or "").strip()
        return False, detail or "Docker daemon is not reachable."
    except Exception as e:
        return False, str(e)


def _collect_preflight_checks(
    client: AIACClient,
    model_version_id: int | None,
    port: int | None,
    redis_host: str,
    redis_port: int,
    check_local_port: bool,
    include_docker: bool = True,
) -> tuple[list[dict], bool]:
    checks: list[dict] = []

    def add_check(name: str, status: str, details: str, fix: str = ""):
        checks.append({"name": name, "status": status, "details": details, "fix": fix})

    base_url = client.base_url.rstrip("/")
    try:
        # Authenticated probe so logged-in users don't get false 401 warnings.
        resp = client.api_request(endpoint="projects/", method="GET")
        status_code = getattr(resp, "status_code", 200)
        if status_code == 200:
            add_check("API server", "PASS", f"Reachable and authenticated at {base_url}.")
        else:
            add_check("API server", "WARN", f"Reachable at {base_url} (status {status_code}).", "Run `aiac auth login` if needed.")
    except Exception as e:
        msg = str(e)
        if _is_auth_error(msg):
            add_check("API server", "FAIL", f"Reachable at {base_url}, but authentication is invalid/expired.", "Run `aiac auth login`.")
        elif "API server is not reachable" in msg or "ConnectionError" in msg:
            add_check("API server", "FAIL", f"Not reachable at {base_url}.", "Start server: `aiac server run --host 127.0.0.1 --port 8000 --migrate`.")
        else:
            add_check("API server", "WARN", f"Could not fully validate API auth: {msg}", "Run `aiac auth login` and retry preflight.")

    if include_docker:
        docker_ok, docker_detail = _docker_cli_available()
        if docker_ok:
            add_check("Docker CLI", "PASS", docker_detail or "Docker CLI available.")
        else:
            add_check("Docker CLI", "FAIL", docker_detail, "Install Docker Desktop/Engine and ensure `docker` is on PATH.")

        daemon_ok, daemon_detail = _docker_daemon_ready()
        if daemon_ok:
            add_check("Docker daemon", "PASS", daemon_detail)
        else:
            add_check("Docker daemon", "FAIL", daemon_detail, "Start Docker Desktop/Engine before deployment.")

    if _redis_reachable(redis_host, redis_port):
        add_check("Redis", "PASS", f"Reachable on {redis_host}:{redis_port}.")
    else:
        add_check("Redis", "WARN", f"Not reachable on {redis_host}:{redis_port}.", "Start Redis (example): `docker run -d --name aiac-redis -p 6379:6379 redis:7`.")

    if _has_celery_worker():
        add_check("Celery worker", "PASS", "At least one worker responded to ping.")
    else:
        add_check("Celery worker", "WARN", "No worker detected.", "Run worker or rely on server fallback mode.")

    if model_version_id is not None:
        try:
            mv_resp = client.api_request(endpoint="model-versions/", method="GET")
            rows = mv_resp.json() if mv_resp is not None else []
            exists = isinstance(rows, list) and any(str(x.get("id")) == str(model_version_id) for x in rows)
            if exists:
                add_check("Model version", "PASS", f"Model version {model_version_id} exists.")
            else:
                add_check("Model version", "FAIL", f"Model version {model_version_id} was not found.", "Run `aiac deployment list-model-versions`.")
        except Exception as e:
            if _is_auth_error(str(e)):
                add_check("Model version", "FAIL", "Cannot validate model version because authentication is invalid/expired.", "Run `aiac auth login`.")
            else:
                add_check("Model version", "WARN", "Could not validate model version now.", "Ensure API server and auth are working.")

    if port is not None:
        if port < 1 or port > 65535:
            add_check("Port", "FAIL", f"Invalid port {port}.", "Use a port between 1 and 65535.")
        elif check_local_port and not _is_local_port_available(port):
            add_check("Port", "WARN", f"Local port {port} appears in use.", "Choose another port for deployment.")
        else:
            add_check("Port", "PASS", f"Port {port} looks available locally.")

    ready = not any(c["status"] == "FAIL" for c in checks)
    return checks, ready

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
            # Start without opening a new console window.
            creationflags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags |= subprocess.CREATE_NO_WINDOW
            subprocess.Popen(
                cmd,
                creationflags=creationflags,
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


@api_app_deployment.command("preflight")
def deployment_preflight(
    model_version_id: int | None = typer.Option(None, help="Optional model version ID to validate."),
    port: int | None = typer.Option(None, help="Optional port to validate locally."),
    redis_host: str = typer.Option("localhost", help="Redis host."),
    redis_port: int = typer.Option(6379, help="Redis port."),
    check_local_port: bool = typer.Option(True, help="Check local port conflict when --port is provided."),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """
    Run pre-deployment checks (API, Docker, Redis, Celery, model version, port).
    """
    cfg_client = AIACClient(base_path="deployment")
    checks, ready = _collect_preflight_checks(
        client=cfg_client,
        model_version_id=model_version_id,
        port=port,
        redis_host=redis_host,
        redis_port=redis_port,
        check_local_port=check_local_port,
        include_docker=True,
    )
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")
    warn_count = sum(1 for c in checks if c["status"] == "WARN")
    pass_count = sum(1 for c in checks if c["status"] == "PASS")

    fmt = (output_format or "table").strip().lower()
    if fmt not in {"table", "json"}:
        typer.echo("Invalid format. Use 'table' or 'json'.")
        return

    if fmt == "json":
        typer.echo(
            json.dumps(
                {
                    "ready": ready,
                    "summary": {"pass": pass_count, "warn": warn_count, "fail": fail_count},
                    "checks": checks,
                },
                indent=2,
            )
        )
        return

    table = Table(title="Deployment Preflight")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details")
    table.add_column("Suggested Fix")
    for row in checks:
        status = row["status"]
        style_status = (
            f"[green]{status}[/green]" if status == "PASS"
            else f"[yellow]{status}[/yellow]" if status == "WARN"
            else f"[red]{status}[/red]"
        )
        table.add_row(row["name"], style_status, row["details"], row["fix"])
    console.print(table)
    typer.echo(f"Summary: PASS={pass_count} WARN={warn_count} FAIL={fail_count}")
    if ready:
        typer.echo("Preflight result: ready for deployment.")
    else:
        typer.echo("Preflight result: not ready. Fix FAIL checks before deploying.")

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
        payload = response.json()
        table = Table(title="Project Created")
        table.add_column("ID", style="cyan")
        table.add_column("Owner", style="magenta")
        table.add_column("Name", style="green")
        table.add_column("Description", style="white")
        table.add_row(
            str(payload.get("id", "N/A")),
            str(payload.get("owner", owner_id)),
            str(payload.get("name", name)),
            str(payload.get("description", description)),
        )
        console.print(table)
        typer.echo(f"Created at: {payload.get('created_at', 'N/A')}")
    except Exception as e:
        typer.echo(_friendly_create_project_error(str(e)))

@api_app_deployment.command("create-model-version")
def create_model_version(project_id: int = typer.Option(..., prompt=True, help="ID of the project"),
                         description: str = typer.Option(..., prompt=True, help="Description of the model version"),
                         field_file_path: str = typer.Option(..., prompt=True, help="Path to the model file")):
    
    """
    Create a new model version for a specified project.
    """
   
    client = AIACClient(base_path="deployment")
    field_file_path = field_file_path.strip().strip('"').strip("'")
    if not field_file_path:
        typer.echo("Model file path is required.")
        return
    if not Path(field_file_path).exists():
        typer.echo(
            "Model file not found. Remove extra quotes and verify the path.\n"
            "Example: C:\\Users\\ASUS\\diabete_ml.pkl"
        )
        return
    data = {
        "projet": project_id,
        "description": description,
    }
    try:
        with open(field_file_path, "rb") as f:
            files = {"field_file": f}
            response = client.api_request(endpoint="model-versions/", method="POST", data=data, files=files)
        payload = response.json()
        table = Table(title="Model Version Created")
        table.add_column("ID", style="cyan")
        table.add_column("Project", style="magenta")
        table.add_column("Description", style="white")
        table.add_column("Deployed", style="green")
        table.add_row(
            str(payload.get("id", "N/A")),
            str(payload.get("projet", project_id)),
            str(payload.get("description", description)),
            "yes" if payload.get("deployed") else "no",
        )
        console.print(table)
        field_file = payload.get("field_file")
        if field_file:
            typer.echo(f"Model file URL: {field_file}")
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to create model version", str(e)))

@api_app_deployment.command("deploy-model-version")
def deploy_model_version(user_id: int = typer.Option(..., prompt=True, help="ID of the user deploying the model"),
                         model_version_id: int = typer.Option(..., prompt=True, help="ID of the model version to deploy"),
                         port: int = typer.Option(..., prompt=True, help="Port to deploy the model version on"),
                         auto_preflight: bool = typer.Option(True, "--auto-preflight/--no-auto-preflight", help="Run deployment preflight checks before starting."),
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
    client = AIACClient(base_path="deployment")
    if auto_preflight:
        checks, ready = _collect_preflight_checks(
            client=client,
            model_version_id=model_version_id,
            port=port,
            redis_host=redis_host,
            redis_port=redis_port,
            check_local_port=check_local_port,
            include_docker=True,
        )
        warns = [c for c in checks if c["status"] == "WARN"]
        fails = [c for c in checks if c["status"] == "FAIL"]
        for row in warns:
            msg = f"Preflight warning [{row['name']}]: {row['details']}"
            if row.get("fix"):
                msg += f" | Fix: {row['fix']}"
            print_warning(msg)
        if fails:
            for row in fails:
                msg = f"Preflight failed [{row['name']}]: {row['details']}"
                if row.get("fix"):
                    msg += f" | Fix: {row['fix']}"
                typer.echo(msg)
            typer.echo("Deployment canceled due to preflight FAIL checks.")
            return

    if start_worker:
        if not _check_redis_and_hint(redis_host, redis_port):
            typer.echo("Redis is unavailable. Deployment will run in fallback mode if the server supports it.")
        else:
            ok, err = _start_worker_and_wait()
            if not ok:
                typer.echo("Worker did not respond to ping in time.")
                typer.echo("Continuing with server fallback mode.")

    if not _has_celery_worker():
        typer.echo("No Celery worker detected. Continuing with server fallback mode.")

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
                    if "Network error:" in msg or "API server is not reachable" in msg:
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
        payload = response.json()
        message = payload.get("message") if isinstance(payload, dict) else None
        if message:
            typer.echo(f"Redeploy started. {message}")
        else:
            typer.echo("Redeploy started successfully.")
        typer.echo("")

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
                    if "Network error:" in msg or "API server is not reachable" in msg:
                        transient_network_failures += 1
                        if transient_network_failures <= 15:
                            progress.update(task_id, status="WAITING_API")
                            time.sleep(2)
                            continue
                    progress.update(task_id, status="ERROR")
                    typer.echo(f"\n\n{_friendly_deployment_lookup_error(msg, deployment_id, 'fetch deployment status')}\n")
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
        typer.echo(f"\n\n{_friendly_deployment_lookup_error(str(e), deployment_id, 'redeploy deployment')}")

@api_app_deployment.command("stop-deployment")
def stop_deployment(deployment_id: int = typer.Option(..., prompt=True, help="ID of the deployment to stop")):
    """
    Stop a specified deployment.
    """
    client = AIACClient(base_path="deployment")
    endpoint = f"deployments/{deployment_id}/stop/"
    try:
        response = client.api_request(endpoint=endpoint, method="POST")
        payload = response.json() if response.text else {}
        message = payload.get("message") if isinstance(payload, dict) else None
        if message:
            typer.echo(message)
        else:
            typer.echo(f"Deployment '{deployment_id}' stopped successfully.")
    except Exception as e:
        msg = str(e)
        if _is_auth_error(msg):
            typer.echo("Session expired or authentication is invalid. Please run `aiac auth login` and try again.")
            return
        if "No Deployment matches the given query" in msg or ("404" in msg and "Deployment not found" in msg):
            typer.echo(f"Deployment '{deployment_id}' was not found. Run `aiac deployment list-deployments` and use a valid ID.")
            return
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
            payload = response.json() if response.text else {}
            message = payload.get("message") if isinstance(payload, dict) else None
            typer.echo(message or f"Deployment '{deployment_id}' deleted successfully.")
    except Exception as e:
        msg = str(e)
        if _is_auth_error(msg):
            typer.echo("Session expired or authentication is invalid. Please run `aiac auth login` and try again.")
            return
        if (
            "Deployment matching query does not exist" in msg
            or "No Deployment matches the given query" in msg
            or ("404" in msg and "Deployment not found" in msg)
        ):
            typer.echo(f"Deployment '{deployment_id}' was not found. Run `aiac deployment list-deployments` and use a valid ID.")
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
        table.add_column("K8s Image Hint")
        table.add_column("Logs")
        table.add_column("Deployed At")
        table.add_row("----", "----", "-------", "-------------", "----", "------", "------------", "------------", "--------------", "----", "-----------")
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
                f"model_deploy_{deployment['id']}",
                str(deployment.get("logs")),
                str(deployment.get("deployed_at")),
            )
        table.add_row("----", "----", "-------", "-------------", "----", "------", "------------", "------------", "--------------", "----", "-----------")
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
        table.add_row("k8s_image_hint", f"model_deploy_{deployment_id}")
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
        typer.echo(_friendly_deployment_lookup_error(str(e), deployment_id, "retrieve deployment details"))


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
        typer.echo("Interpretation:")
        score = payload.get("advisor_score")
        risk = payload.get("risk_level")
        strategy = payload.get("recommended_strategy")
        if score is not None:
            typer.echo(
                f"- Score {score} maps to risk '{risk}' and strategy '{strategy}'. "
                "Higher score means healthier deployment."
            )
        else:
            typer.echo(
                "- Risk and strategy are derived from CPU/RAM/latency/error metrics and alert/drift signals."
            )
        ram = metrics.get("ram_usage")
        if ram is not None:
            try:
                if float(ram) >= 90:
                    typer.echo("- RAM is very high; watch for memory pressure or scaling needs.")
            except (TypeError, ValueError):
                pass
        if payload.get("drift_high"):
            typer.echo("- Drift is high: consider retraining or recalibration.")
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
        typer.echo("Interpretation:")
        typer.echo(
            f"- Evaluated deployment {payload.get('deployment_id')} "
            f"(current={payload.get('current_model_version_id')} vs candidate={payload.get('candidate_model_version_id')}) "
            f"on {payload.get('sample_count')} samples."
        )
        rec = str(payload.get("recommendation", ""))
        if rec == "promote_candidate":
            typer.echo("- Recommendation means candidate performance is acceptable for promotion.")
        elif rec == "keep_current":
            typer.echo("- Recommendation means current model remains the safer/better choice.")
        elif rec == "review_required":
            typer.echo("- Recommendation means manual review is required before any promotion decision.")

        match_rate = m.get("prediction_match_rate")
        matches = m.get("prediction_matches")
        if match_rate is not None and matches is not None:
            typer.echo(
                f"- Match rate={match_rate} ({matches} matching predictions): "
                "higher is closer behavior to current model."
            )

        latency_ratio = m.get("latency_ratio_candidate_vs_current")
        if isinstance(latency_ratio, (int, float)):
            if latency_ratio < 1:
                typer.echo(f"- Latency ratio={latency_ratio:.4f}: candidate is faster than current.")
            elif latency_ratio > 1:
                typer.echo(f"- Latency ratio={latency_ratio:.4f}: candidate is slower than current.")
            else:
                typer.echo("- Latency ratio=1.0000: candidate and current have similar latency.")

        avg_abs_diff = m.get("avg_abs_prediction_diff")
        if avg_abs_diff is not None:
            typer.echo(
                f"- Avg abs diff={avg_abs_diff}: lower values indicate closer numeric outputs "
                "(especially for regression-like predictions)."
            )
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

        typer.echo("How to read this:")
        typer.echo(
            "- Prediction is the model output (class index or label). "
            "Decision is the policy verdict (approved/refused)."
        )
        if confidence is None or margin is None:
            typer.echo(
                "- Confidence and margin are None because this runtime did not return probabilities. "
                "Threshold checks could not be evaluated."
            )
        else:
            typer.echo("- Confidence and margin are available, so refusal thresholds were evaluated.")
        typer.echo(
            "- Feature numbers correspond to the input order you provided. "
            "Contribution = value × weight. Positive increases the prediction, negative decreases it."
        )

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
                total_contrib = 0.0
                for row in linear:
                    try:
                        total_contrib += float(row.get("contribution", 0.0))
                    except (TypeError, ValueError):
                        continue
                if total_contrib > 0:
                    typer.echo(
                        f"- Net effect is positive (sum of contributions={total_contrib:.6f}), "
                        "which pushed the prediction upward."
                    )
                elif total_contrib < 0:
                    typer.echo(
                        f"- Net effect is negative (sum of contributions={total_contrib:.6f}), "
                        "which pushed the prediction downward."
                    )
                else:
                    typer.echo("- Net effect is neutral (sum of contributions≈0).")
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
def list_model_versions(
    status: str = typer.Option("", "--status", help="Filter by status (draft/pending/approved/rejected/retired)."),
    project_id: int = typer.Option(0, "--project-id", help="Filter by project ID."),
    deployed_only: bool = typer.Option(False, "--deployed-only", help="Only show deployed model versions."),
):
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
        table.add_column("Status")
        table.add_column("Approved By")
        table.add_column("Approved At")
        table.add_column("Created At")
        table.add_column("Updated At")
        table.add_column("Deployed")
        table.add_row("----", "-------", "-----------", "----------", "------", "----------", "----------", "----------", "----------", "--------")
        rows = response.json()
        if status:
            rows = [mv for mv in rows if str(mv.get("status", "")).lower() == status.lower()]
        if project_id:
            rows = [mv for mv in rows if int(mv.get("projet") or 0) == project_id]
        if deployed_only:
            rows = [mv for mv in rows if mv.get("deployed")]

        for model_version in rows:
            table.add_row(
                str(model_version["id"]),
                str(model_version["projet"]),
                str(model_version["description"]),
                str(model_version["field_file"]),
                str(model_version.get("status", "")),
                str(model_version.get("approved_by", "")),
                str(model_version.get("approved_at", "")),
                str(model_version["created_at"]),
                str(model_version["updated_at"]),
                str(model_version["deployed"]),
            )
        table.add_row("----", "-------", "-----------", "----------", "------", "----------", "----------", "----------", "----------", "--------")
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
        msg = str(e)
        if _is_auth_error(msg):
            typer.echo("Session expired or authentication is invalid. Please run `aiac auth login` and try again.")
        elif "No ModelVersion matches the given query" in msg:
            typer.echo(
                f"Model version '{model_version_id}' was not found. "
                "Run `aiac deployment list-model-versions` to see valid IDs."
            )
        else:
            typer.echo(f"Failed to delete model version: {msg}")


@api_app_deployment.command("approve-model-version")
def approve_model_version(
    model_version_id: int = typer.Option(..., prompt=True, help="Model version ID to approve"),
    note: str = typer.Option("", "--note", help="Optional approval note"),
):
    """Approve a model version for deployment."""
    client = AIACClient(base_path="deployment")
    try:
        resp = client.api_request(
            endpoint=f"model-versions/{model_version_id}/approve/",
            method="POST",
            data={"note": note} if note else {},
        )
        payload = resp.json() if resp.text else {}
        typer.echo(payload.get("message", f"Model version {model_version_id} approved."))
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to approve model version", str(e)))


@api_app_deployment.command("reject-model-version")
def reject_model_version(
    model_version_id: int = typer.Option(..., prompt=True, help="Model version ID to reject"),
    note: str = typer.Option("", "--note", help="Optional rejection note"),
):
    """Reject a model version."""
    client = AIACClient(base_path="deployment")
    try:
        resp = client.api_request(
            endpoint=f"model-versions/{model_version_id}/reject/",
            method="POST",
            data={"note": note} if note else {},
        )
        payload = resp.json() if resp.text else {}
        typer.echo(payload.get("message", f"Model version {model_version_id} rejected."))
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to reject model version", str(e)))


@api_app_deployment.command("retire-model-version")
def retire_model_version(
    model_version_id: int = typer.Option(..., prompt=True, help="Model version ID to retire"),
    note: str = typer.Option("", "--note", help="Optional retirement note"),
):
    """Retire a model version."""
    client = AIACClient(base_path="deployment")
    try:
        resp = client.api_request(
            endpoint=f"model-versions/{model_version_id}/retire/",
            method="POST",
            data={"note": note} if note else {},
        )
        payload = resp.json() if resp.text else {}
        typer.echo(payload.get("message", f"Model version {model_version_id} retired."))
    except Exception as e:
        typer.echo(_friendly_backend_error("Failed to retire model version", str(e)))


@api_app_deployment.command("list-model-approvals")
def list_model_approvals(
    model_version_id: int = typer.Option(..., prompt=True, help="Model version ID"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table or json."),
):
    """List approval history for a model version."""
    client = AIACClient(base_path="deployment")
    try:
        fmt = (output_format or "table").strip().lower()
        if fmt not in {"table", "json"}:
            typer.echo("Invalid format. Use 'table' or 'json'.")
            return
        resp = client.api_request(
            endpoint=f"model-versions/{model_version_id}/approvals/",
            method="GET",
        )
        payload = resp.json()
        rows = payload if isinstance(payload, list) else [payload]
        if fmt == "json":
            typer.echo(json.dumps(rows, indent=2, default=str))
            return
        table = Table(title="Model Version Approvals")
        table.add_column("ID", style="cyan")
        table.add_column("Model Version", style="magenta")
        table.add_column("Decision", style="yellow")
        table.add_column("Note")
        table.add_column("Decided By", style="green")
        table.add_column("Decided At", style="white")
        for row in rows:
            table.add_row(
                str(row.get("id", "")),
                str(row.get("model_version", "")),
                str(row.get("decision", "")),
                str(row.get("note", "")),
                str(row.get("decided_by", "")),
                str(row.get("decided_at", "")),
            )
        console.print(table)
    except Exception as e:
        typer.echo(f"Failed to list approvals: {e}")


@api_app_deployment.command("k8s-deploy")
def k8s_deploy(
    deployment_id: int = typer.Option(..., prompt=True, help="AIAC deployment ID"),
    image: str = typer.Option(..., "--image", "-i", prompt=True, help="Container image to run"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
    replicas: int = typer.Option(1, "--replicas", "-r", help="Number of replicas"),
    container_port: int = typer.Option(8000, "--container-port", help="Container port"),
    service_port: int = typer.Option(80, "--service-port", help="Service port"),
    service_type: str = typer.Option("ClusterIP", "--service-type", help="ClusterIP|NodePort|LoadBalancer"),
    rollout_strategy: str = typer.Option(
        "RollingUpdate",
        "--rollout-strategy",
        help="Deployment strategy: RollingUpdate or Recreate",
    ),
    max_unavailable: str = typer.Option(
        "25%",
        "--max-unavailable",
        help="RollingUpdate max unavailable (int or percent), used only for RollingUpdate.",
    ),
    max_surge: str = typer.Option(
        "25%",
        "--max-surge",
        help="RollingUpdate max surge (int or percent), used only for RollingUpdate.",
    ),
    kubeconfig: str = typer.Option("", "--kubeconfig", help="Optional kubeconfig file path"),
    context: str = typer.Option("", "--context", help="Optional kubeconfig context"),
):
    """Deploy an AIAC runtime image to Kubernetes and expose a Service."""
    service_type_normalized = (service_type or "ClusterIP").strip()
    if service_type_normalized not in {"ClusterIP", "NodePort", "LoadBalancer"}:
        typer.echo("Invalid service type. Use ClusterIP, NodePort, or LoadBalancer.")
        return
    strategy_normalized = (rollout_strategy or "RollingUpdate").strip()
    if strategy_normalized not in {"RollingUpdate", "Recreate"}:
        typer.echo("Invalid rollout strategy. Use RollingUpdate or Recreate.")
        return
    if replicas < 1:
        typer.echo("replicas must be >= 1.")
        return

    k8s_client, apps_api, core_api, ApiException_or_error = _load_k8s_clients(kubeconfig, context)
    if not k8s_client:
        typer.echo(ApiException_or_error)
        return
    ApiException = ApiException_or_error

    resource_name = f"aiac-deploy-{deployment_id}"
    labels = {
        "app": "aiac-runtime",
        "aiac-deployment-id": str(deployment_id),
    }

    container = k8s_client.V1Container(
        name="runtime",
        image=image,
        ports=[k8s_client.V1ContainerPort(container_port=container_port)],
    )
    pod_spec = k8s_client.V1PodSpec(containers=[container])
    pod_template = k8s_client.V1PodTemplateSpec(
        metadata=k8s_client.V1ObjectMeta(labels=labels),
        spec=pod_spec,
    )
    def _int_or_percent(value: str):
        v = str(value).strip()
        if v.endswith("%"):
            # Keep percentages as strings in K8s API.
            return v
        try:
            return int(v)
        except ValueError:
            raise typer.BadParameter("Expected integer or percentage (e.g. 1 or 25%).")

    rolling_update_cfg = None
    if strategy_normalized == "RollingUpdate":
        rolling_update_cfg = k8s_client.V1RollingUpdateDeployment(
            max_unavailable=_int_or_percent(max_unavailable),
            max_surge=_int_or_percent(max_surge),
        )

    strategy_cfg = k8s_client.V1DeploymentStrategy(
        type=strategy_normalized,
        rolling_update=rolling_update_cfg,
    )

    dep_spec = k8s_client.V1DeploymentSpec(
        replicas=replicas,
        strategy=strategy_cfg,
        selector=k8s_client.V1LabelSelector(match_labels=labels),
        template=pod_template,
    )
    dep_body = k8s_client.V1Deployment(
        metadata=k8s_client.V1ObjectMeta(name=resource_name, labels=labels),
        spec=dep_spec,
    )

    svc_spec = k8s_client.V1ServiceSpec(
        selector=labels,
        ports=[k8s_client.V1ServicePort(port=service_port, target_port=container_port)],
        type=service_type_normalized,
    )
    svc_body = k8s_client.V1Service(
        metadata=k8s_client.V1ObjectMeta(name=resource_name, labels=labels),
        spec=svc_spec,
    )

    try:
        try:
            apps_api.read_namespaced_deployment(name=resource_name, namespace=namespace)
            apps_api.patch_namespaced_deployment(name=resource_name, namespace=namespace, body=dep_body)
            dep_action = "updated"
        except ApiException as e:
            if e.status != 404:
                raise
            apps_api.create_namespaced_deployment(namespace=namespace, body=dep_body)
            dep_action = "created"

        try:
            core_api.read_namespaced_service(name=resource_name, namespace=namespace)
            core_api.patch_namespaced_service(name=resource_name, namespace=namespace, body=svc_body)
            svc_action = "updated"
        except ApiException as e:
            if e.status != 404:
                raise
            core_api.create_namespaced_service(namespace=namespace, body=svc_body)
            svc_action = "created"

        table = Table(title="Kubernetes Deployment")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Name", resource_name)
        table.add_row("Namespace", namespace)
        table.add_row("Image", image)
        table.add_row("Replicas", str(replicas))
        table.add_row("Container Port", str(container_port))
        table.add_row("Service Port", str(service_port))
        table.add_row("Service Type", service_type_normalized)
        table.add_row("Rollout Strategy", strategy_normalized)
        if strategy_normalized == "RollingUpdate":
            table.add_row("Max Unavailable", str(max_unavailable))
            table.add_row("Max Surge", str(max_surge))
        table.add_row("Deployment", dep_action)
        table.add_row("Service", svc_action)
        console.print(table)
    except Exception as e:
        typer.echo(f"Failed to deploy to Kubernetes: {e}")


@api_app_deployment.command("k8s-preflight")
def k8s_preflight(
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace to check"),
    deployment_id: int = typer.Option(
        None,
        "--deployment-id",
        help="Optional AIAC deployment ID to check if Kubernetes resources already exist.",
    ),
    kubeconfig: str = typer.Option("", "--kubeconfig", help="Optional kubeconfig file path"),
    context: str = typer.Option("", "--context", help="Optional kubeconfig context"),
):
    """Run Kubernetes readiness checks before using k8s commands."""
    checks = []

    # SDK presence check.
    try:
        from kubernetes import client as _k8s_client  # noqa: F401
        checks.append(("Kubernetes SDK", "PASS", "Python kubernetes package is installed.", ""))
    except Exception:
        checks.append(
            (
                "Kubernetes SDK",
                "FAIL",
                "Python kubernetes package is missing.",
                "Install with: pip install kubernetes",
            )
        )
        table = Table(title="Kubernetes Preflight")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Details", style="white")
        table.add_column("Suggested Fix", style="green")
        for row in checks:
            table.add_row(*row)
        console.print(table)
        typer.echo("Preflight result: not ready.")
        return

    k8s_client, apps_api, core_api, ApiException_or_error = _load_k8s_clients(kubeconfig, context)
    if not k8s_client:
        checks.append(("Kube config", "FAIL", str(ApiException_or_error), "Set KUBECONFIG or pass --kubeconfig."))
        table = Table(title="Kubernetes Preflight")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Details", style="white")
        table.add_column("Suggested Fix", style="green")
        for row in checks:
            table.add_row(*row)
        console.print(table)
        typer.echo("Preflight result: not ready.")
        return

    ApiException = ApiException_or_error

    # API reachability check.
    try:
        version_api = k8s_client.VersionApi()
        v = version_api.get_code()
        checks.append(("K8s API", "PASS", f"Reachable (v{v.major}.{v.minor}).", ""))
    except Exception as e:
        checks.append(("K8s API", "FAIL", f"Cannot reach Kubernetes API: {e}", "Start cluster or fix kube context."))

    # Namespace check.
    try:
        core_api.read_namespace(name=namespace)
        checks.append(("Namespace", "PASS", f"Namespace '{namespace}' exists.", ""))
    except ApiException as e:
        if e.status == 404:
            checks.append(
                (
                    "Namespace",
                    "WARN",
                    f"Namespace '{namespace}' not found.",
                    f"Create it with: kubectl create namespace {namespace}",
                )
            )
        else:
            checks.append(("Namespace", "FAIL", f"Namespace check failed: {e}", "Verify cluster permissions."))
    except Exception as e:
        checks.append(("Namespace", "FAIL", f"Namespace check failed: {e}", "Verify cluster permissions."))

    # Optional existing resources check.
    if deployment_id is not None:
        resource_name = f"aiac-deploy-{deployment_id}"
        try:
            apps_api.read_namespaced_deployment(name=resource_name, namespace=namespace)
            checks.append(("Deployment resource", "PASS", f"'{resource_name}' exists.", ""))
        except ApiException as e:
            if e.status == 404:
                checks.append(
                    (
                        "Deployment resource",
                        "WARN",
                        f"'{resource_name}' does not exist yet.",
                        "Run `aiac deployment k8s-deploy` first.",
                    )
                )
            else:
                checks.append(("Deployment resource", "FAIL", f"Check failed: {e}", "Verify RBAC and namespace."))
        except Exception as e:
            checks.append(("Deployment resource", "FAIL", f"Check failed: {e}", "Verify RBAC and namespace."))

    table = Table(title="Kubernetes Preflight")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Details", style="white")
    table.add_column("Suggested Fix", style="green")
    for row in checks:
        table.add_row(*row)
    console.print(table)

    fail_count = len([1 for c in checks if c[1] == "FAIL"])
    warn_count = len([1 for c in checks if c[1] == "WARN"])
    if fail_count > 0:
        typer.echo("Preflight result: not ready.")
    elif warn_count > 0:
        typer.echo("Preflight result: partially ready (warnings present).")
    else:
        typer.echo("Preflight result: ready for Kubernetes commands.")


@api_app_deployment.command("k8s-bootstrap")
def k8s_bootstrap(
    install_minikube: bool = typer.Option(
        True,
        "--install/--no-install",
        help="Install Minikube using winget before start (Windows).",
    ),
    driver: str = typer.Option("docker", "--driver", help="Minikube driver (default: docker)."),
    profile: str = typer.Option("", "--profile", help="Optional Minikube profile name."),
):
    """Install Minikube (optional) and start a local Kubernetes cluster."""
    if install_minikube and platform.system().lower() != "windows":
        typer.echo("Auto-install via winget is only supported on Windows. Skipping install step.")
        install_minikube = False

    if install_minikube:
        try:
            typer.echo("Installing Minikube with winget...")
            install_proc = subprocess.run(
                ["winget", "install", "Kubernetes.minikube", "--accept-package-agreements", "--accept-source-agreements"],
                capture_output=True,
                text=True,
                check=False,
            )
            if install_proc.returncode != 0:
                details = (install_proc.stderr or install_proc.stdout or "").strip()
                typer.echo(
                    "Failed to install Minikube automatically.\n"
                    "Install manually:\n"
                    "  winget install Kubernetes.minikube\n"
                    f"Details: {details[:300]}"
                )
                return
            typer.echo("Minikube installation completed.")
        except FileNotFoundError:
            typer.echo(
                "winget is not available on this system.\n"
                "Install Minikube manually, then retry:\n"
                "  winget install Kubernetes.minikube"
            )
            return
        except Exception as e:
            typer.echo(f"Failed to install Minikube: {e}")
            return

    start_cmd = ["minikube", "start", f"--driver={driver}"]
    if profile:
        start_cmd.extend(["-p", profile])

    try:
        typer.echo(f"Starting Minikube cluster with driver '{driver}'...")
        start_proc = subprocess.run(
            start_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if start_proc.returncode != 0:
            details = (start_proc.stderr or start_proc.stdout or "").strip()
            typer.echo(
                "Failed to start Minikube cluster.\n"
                "Make sure Docker Desktop/Engine is running, then retry:\n"
                "  minikube start --driver=docker\n"
                f"Details: {details[:400]}"
            )
            return

        typer.echo("Minikube cluster started successfully.")
    except FileNotFoundError:
        typer.echo(
            "minikube command is not available.\n"
            "Install Minikube, then run:\n"
            "  minikube start --driver=docker"
        )
        return
    except Exception as e:
        typer.echo(f"Failed to start Minikube cluster: {e}")
        return

    # Verification checks
    try:
        cluster_info = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            check=False,
        )
        nodes = subprocess.run(
            ["kubectl", "get", "nodes"],
            capture_output=True,
            text=True,
            check=False,
        )
        if cluster_info.returncode == 0 and nodes.returncode == 0:
            typer.echo("Kubernetes cluster is reachable.")
            typer.echo("Next step: run `aiac deployment k8s-preflight`.")
        else:
            typer.echo(
                "Minikube started, but kubectl verification failed.\n"
                "Try manually:\n"
                "  kubectl cluster-info\n"
                "  kubectl get nodes"
            )
    except Exception:
        typer.echo(
            "Minikube started. Could not run kubectl verification automatically.\n"
            "Please run:\n"
            "  kubectl cluster-info\n"
            "  kubectl get nodes"
        )


@api_app_deployment.command("k8s-doctor")
def k8s_doctor(
    kubeconfig: str = typer.Option("", "--kubeconfig", help="Optional kubeconfig file path"),
    context: str = typer.Option("", "--context", help="Optional kubeconfig context"),
):
    """Diagnose Kubernetes setup and print recovery commands."""
    checks = []

    def _check_cmd(name: str, args: list[str], fix: str):
        try:
            proc = subprocess.run(args, capture_output=True, text=True, check=False)
            if proc.returncode == 0:
                details = (proc.stdout or proc.stderr or "").strip().splitlines()
                checks.append((name, "PASS", (details[0] if details else "available"), ""))
                return True
            details = (proc.stderr or proc.stdout or "").strip()
            checks.append((name, "FAIL", details[:180] or "command failed", fix))
            return False
        except FileNotFoundError:
            checks.append((name, "FAIL", "command not found", fix))
            return False
        except Exception as e:
            checks.append((name, "FAIL", str(e)[:180], fix))
            return False

    docker_ok = _check_cmd(
        "Docker CLI",
        ["docker", "--version"],
        "Install/start Docker Desktop, then retry.",
    )
    _check_cmd(
        "kubectl",
        ["kubectl", "version", "--client"],
        "Install kubectl: `winget install Kubernetes.kubectl`.",
    )
    minikube_ok = _check_cmd(
        "Minikube",
        ["minikube", "version"],
        (
            "Install Minikube with `winget install Kubernetes.minikube`.\n"
            "If winget source fails, use manual installer from minikube docs."
        ),
    )

    try:
        import kubernetes  # noqa: F401
        checks.append(("Python kubernetes SDK", "PASS", "installed", ""))
    except Exception:
        checks.append(
            (
                "Python kubernetes SDK",
                "FAIL",
                "package not installed",
                "Install with: `pip install kubernetes` or `pip install \"ai-accelerator[k8s]\"`.",
            )
        )

    if minikube_ok:
        try:
            ms = subprocess.run(
                ["minikube", "status", "--output=json"],
                capture_output=True,
                text=True,
                check=False,
            )
            if ms.returncode == 0:
                checks.append(("Minikube cluster", "PASS", "running", ""))
            else:
                details = (ms.stderr or ms.stdout or "").strip()
                checks.append(
                    (
                        "Minikube cluster",
                        "WARN",
                        details[:180] or "not running",
                        "Start with: `minikube start --driver=docker`.",
                    )
                )
        except Exception as e:
            checks.append(("Minikube cluster", "WARN", str(e)[:180], "Run `minikube start --driver=docker`."))

    _k8s_client, _apps_api, _core_api, err_or_exc = _load_k8s_clients(kubeconfig, context)
    if _k8s_client is None:
        checks.append(
            (
                "Kube config / API",
                "FAIL",
                str(err_or_exc).splitlines()[0],
                "Run `minikube update-context` and retry preflight.",
            )
        )
    else:
        try:
            version_api = _k8s_client.VersionApi()
            v = version_api.get_code()
            checks.append(("Kubernetes API", "PASS", f"reachable (v{v.major}.{v.minor})", ""))
        except Exception as e:
            checks.append(
                (
                    "Kubernetes API",
                    "FAIL",
                    str(e)[:180],
                    "Ensure cluster is running and current context is valid.",
                )
            )

    table = Table(title="Kubernetes Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Details", style="white")
    table.add_column("Suggested Fix", style="green")
    for row in checks:
        table.add_row(*row)
    console.print(table)

    fail_count = len([1 for c in checks if c[1] == "FAIL"])
    warn_count = len([1 for c in checks if c[1] == "WARN"])
    pass_count = len([1 for c in checks if c[1] == "PASS"])
    typer.echo(f"Summary: PASS={pass_count} WARN={warn_count} FAIL={fail_count}")
    if fail_count > 0:
        typer.echo("Kubernetes is not ready yet.")
        typer.echo("Quick recovery:")
        if docker_ok:
            typer.echo("1) Start cluster: `minikube start --driver=docker`")
        else:
            typer.echo("1) Install/start Docker Desktop first.")
        typer.echo("2) Refresh context: `minikube update-context`")
        typer.echo("3) Validate: `aiac deployment k8s-preflight`")
    elif warn_count > 0:
        typer.echo("Kubernetes is partially ready (warnings present).")
    else:
        typer.echo("Kubernetes looks ready for AIAC k8s commands.")


@api_app_deployment.command("k8s-status")
def k8s_status(
    deployment_id: int = typer.Option(..., prompt=True, help="AIAC deployment ID"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
    kubeconfig: str = typer.Option("", "--kubeconfig", help="Optional kubeconfig file path"),
    context: str = typer.Option("", "--context", help="Optional kubeconfig context"),
):
    """Show Kubernetes status for an AIAC deployment resource."""
    k8s_client, apps_api, core_api, ApiException_or_error = _load_k8s_clients(kubeconfig, context)
    if not k8s_client:
        typer.echo(ApiException_or_error)
        return
    ApiException = ApiException_or_error
    resource_name = f"aiac-deploy-{deployment_id}"
    try:
        dep = apps_api.read_namespaced_deployment(name=resource_name, namespace=namespace)
        svc = core_api.read_namespaced_service(name=resource_name, namespace=namespace)
        status = dep.status
        service_ip = svc.spec.cluster_ip or "N/A"
        table = Table(title="Kubernetes Runtime Status")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Name", resource_name)
        table.add_row("Namespace", namespace)
        table.add_row("Desired Replicas", str(dep.spec.replicas or 0))
        table.add_row("Ready Replicas", str(status.ready_replicas or 0))
        table.add_row("Available Replicas", str(status.available_replicas or 0))
        table.add_row("Service Type", str(svc.spec.type))
        table.add_row("Cluster IP", str(service_ip))
        console.print(table)
    except ApiException as e:
        if e.status == 404:
            typer.echo(
                f"Kubernetes resources for deployment {deployment_id} were not found in namespace '{namespace}'."
            )
            return
        typer.echo(f"Failed to fetch Kubernetes status: {e}")
    except Exception as e:
        typer.echo(f"Failed to fetch Kubernetes status: {e}")


@api_app_deployment.command("k8s-scale")
def k8s_scale(
    deployment_id: int = typer.Option(..., prompt=True, help="AIAC deployment ID"),
    replicas: int = typer.Option(..., "--replicas", "-r", prompt=True, help="Target replicas"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
    kubeconfig: str = typer.Option("", "--kubeconfig", help="Optional kubeconfig file path"),
    context: str = typer.Option("", "--context", help="Optional kubeconfig context"),
):
    """Scale Kubernetes deployment replicas."""
    if replicas < 1:
        typer.echo("replicas must be >= 1.")
        return
    k8s_client, apps_api, _core_api, ApiException_or_error = _load_k8s_clients(kubeconfig, context)
    if not k8s_client:
        typer.echo(ApiException_or_error)
        return
    ApiException = ApiException_or_error
    resource_name = f"aiac-deploy-{deployment_id}"
    body = {"spec": {"replicas": replicas}}
    try:
        apps_api.patch_namespaced_deployment_scale(
            name=resource_name,
            namespace=namespace,
            body=body,
        )
        typer.echo(
            f"Kubernetes deployment '{resource_name}' scaled to {replicas} replicas in namespace '{namespace}'."
        )
    except ApiException as e:
        if e.status == 404:
            typer.echo(
                f"Kubernetes deployment '{resource_name}' was not found in namespace '{namespace}'."
            )
            return
        typer.echo(f"Failed to scale Kubernetes deployment: {e}")
    except Exception as e:
        typer.echo(f"Failed to scale Kubernetes deployment: {e}")


@api_app_deployment.command("k8s-hpa")
def k8s_hpa(
    deployment_id: int = typer.Option(..., prompt=True, help="AIAC deployment ID"),
    min_replicas: int = typer.Option(1, "--min", help="Minimum replicas"),
    max_replicas: int = typer.Option(..., "--max", prompt=True, help="Maximum replicas"),
    cpu_percent: int = typer.Option(
        70,
        "--cpu-percent",
        help="Target average CPU utilization percentage",
    ),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
    kubeconfig: str = typer.Option("", "--kubeconfig", help="Optional kubeconfig file path"),
    context: str = typer.Option("", "--context", help="Optional kubeconfig context"),
):
    """Create or update HorizontalPodAutoscaler for an AIAC Kubernetes deployment."""
    if min_replicas < 1:
        typer.echo("--min must be >= 1.")
        return
    if max_replicas < min_replicas:
        typer.echo("--max must be >= --min.")
        return
    if cpu_percent < 1 or cpu_percent > 100:
        typer.echo("--cpu-percent must be between 1 and 100.")
        return

    k8s_client, _apps_api, _core_api, ApiException_or_error = _load_k8s_clients(kubeconfig, context)
    if not k8s_client:
        typer.echo(ApiException_or_error)
        return
    ApiException = ApiException_or_error
    autoscaling_api = k8s_client.AutoscalingV2Api()
    resource_name = f"aiac-deploy-{deployment_id}"
    hpa_name = f"{resource_name}-hpa"

    metric = k8s_client.V2MetricSpec(
        type="Resource",
        resource=k8s_client.V2ResourceMetricSource(
            name="cpu",
            target=k8s_client.V2MetricTarget(
                type="Utilization",
                average_utilization=cpu_percent,
            ),
        ),
    )

    hpa_body = k8s_client.V2HorizontalPodAutoscaler(
        metadata=k8s_client.V1ObjectMeta(name=hpa_name),
        spec=k8s_client.V2HorizontalPodAutoscalerSpec(
            scale_target_ref=k8s_client.V2CrossVersionObjectReference(
                api_version="apps/v1",
                kind="Deployment",
                name=resource_name,
            ),
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            metrics=[metric],
        ),
    )

    try:
        try:
            autoscaling_api.read_namespaced_horizontal_pod_autoscaler(
                name=hpa_name,
                namespace=namespace,
            )
            autoscaling_api.patch_namespaced_horizontal_pod_autoscaler(
                name=hpa_name,
                namespace=namespace,
                body=hpa_body,
            )
            action = "updated"
        except ApiException as e:
            if e.status != 404:
                raise
            autoscaling_api.create_namespaced_horizontal_pod_autoscaler(
                namespace=namespace,
                body=hpa_body,
            )
            action = "created"
        typer.echo(
            f"Kubernetes HPA {action}: {hpa_name} "
            f"(min={min_replicas}, max={max_replicas}, cpu={cpu_percent}%) in namespace '{namespace}'."
        )
    except Exception as e:
        typer.echo(f"Failed to configure Kubernetes HPA: {e}")


@api_app_deployment.command("k8s-rollback")
def k8s_rollback(
    deployment_id: int = typer.Option(..., prompt=True, help="AIAC deployment ID"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
    to_revision: int = typer.Option(
        0,
        "--to-revision",
        help="Target ReplicaSet revision. 0 means previous available revision.",
    ),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
    kubeconfig: str = typer.Option("", "--kubeconfig", help="Optional kubeconfig file path"),
    context: str = typer.Option("", "--context", help="Optional kubeconfig context"),
):
    """Rollback Kubernetes deployment image to a previous ReplicaSet revision."""
    k8s_client, apps_api, _core_api, ApiException_or_error = _load_k8s_clients(kubeconfig, context)
    if not k8s_client:
        typer.echo(ApiException_or_error)
        return
    ApiException = ApiException_or_error

    resource_name = f"aiac-deploy-{deployment_id}"
    label_selector = f"aiac-deployment-id={deployment_id}"

    try:
        deployment = apps_api.read_namespaced_deployment(name=resource_name, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            typer.echo(
                f"Kubernetes deployment '{resource_name}' was not found in namespace '{namespace}'."
            )
            return
        typer.echo(f"Failed to read Kubernetes deployment: {e}")
        return
    except Exception as e:
        typer.echo(f"Failed to read Kubernetes deployment: {e}")
        return

    current_image = ""
    if deployment.spec and deployment.spec.template and deployment.spec.template.spec and deployment.spec.template.spec.containers:
        current_image = deployment.spec.template.spec.containers[0].image or ""

    try:
        rs_list = apps_api.list_namespaced_replica_set(
            namespace=namespace,
            label_selector=label_selector,
        )
    except Exception as e:
        typer.echo(f"Failed to list ReplicaSets for rollback: {e}")
        return

    candidates = []
    for rs in rs_list.items:
        ann = (rs.metadata.annotations or {}) if rs.metadata else {}
        rev_raw = ann.get("deployment.kubernetes.io/revision")
        if not rev_raw:
            continue
        try:
            rev = int(rev_raw)
        except ValueError:
            continue
        image = ""
        try:
            image = rs.spec.template.spec.containers[0].image or ""
        except Exception:
            image = ""
        if not image:
            continue
        candidates.append({"revision": rev, "image": image})

    if not candidates:
        typer.echo("No ReplicaSet revisions found for rollback.")
        return

    candidates = sorted(candidates, key=lambda x: x["revision"], reverse=True)
    unique_by_revision = {}
    for row in candidates:
        unique_by_revision[row["revision"]] = row
    revisions = sorted(unique_by_revision.keys(), reverse=True)

    if to_revision > 0:
        target = unique_by_revision.get(to_revision)
        if not target:
            typer.echo(
                f"Requested revision {to_revision} was not found. "
                f"Available revisions: {revisions}"
            )
            return
    else:
        target = None
        for rev in revisions:
            item = unique_by_revision[rev]
            if item["image"] != current_image:
                target = item
                break
        if not target:
            typer.echo(
                "No previous image revision found to rollback to "
                "(current deployment already matches latest available image)."
            )
            return

    if not yes:
        confirm = typer.confirm(
            f"Rollback '{resource_name}' to revision {target['revision']} "
            f"(image: {target['image']}) in namespace '{namespace}'?"
        )
        if not confirm:
            typer.echo("Canceled.")
            return

    patch_body = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": deployment.spec.template.spec.containers[0].name,
                            "image": target["image"],
                        }
                    ]
                }
            }
        }
    }
    try:
        apps_api.patch_namespaced_deployment(
            name=resource_name,
            namespace=namespace,
            body=patch_body,
        )
        typer.echo(
            f"Rollback triggered for '{resource_name}' in namespace '{namespace}'.\n"
            f"Current image: {current_image}\n"
            f"Target revision: {target['revision']} | Target image: {target['image']}"
        )
    except Exception as e:
        typer.echo(f"Failed to rollback Kubernetes deployment: {e}")


@api_app_deployment.command("k8s-delete")
def k8s_delete(
    deployment_id: int = typer.Option(..., prompt=True, help="AIAC deployment ID"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
    kubeconfig: str = typer.Option("", "--kubeconfig", help="Optional kubeconfig file path"),
    context: str = typer.Option("", "--context", help="Optional kubeconfig context"),
):
    """Delete Kubernetes Deployment and Service created for AIAC deployment."""
    if not yes:
        confirm = typer.confirm(
            f"Delete Kubernetes resources for deployment {deployment_id} in namespace '{namespace}'?"
        )
        if not confirm:
            typer.echo("Canceled.")
            return

    k8s_client, apps_api, core_api, ApiException_or_error = _load_k8s_clients(kubeconfig, context)
    if not k8s_client:
        typer.echo(ApiException_or_error)
        return
    ApiException = ApiException_or_error
    resource_name = f"aiac-deploy-{deployment_id}"
    hpa_name = f"{resource_name}-hpa"

    deleted = []
    missing = []
    try:
        autoscaling_api = k8s_client.AutoscalingV2Api()
        try:
            autoscaling_api.delete_namespaced_horizontal_pod_autoscaler(
                name=hpa_name,
                namespace=namespace,
            )
            deleted.append("hpa")
        except ApiException as e:
            if e.status == 404:
                missing.append("hpa")
            else:
                raise
        try:
            core_api.delete_namespaced_service(name=resource_name, namespace=namespace)
            deleted.append("service")
        except ApiException as e:
            if e.status == 404:
                missing.append("service")
            else:
                raise
        try:
            apps_api.delete_namespaced_deployment(name=resource_name, namespace=namespace)
            deleted.append("deployment")
        except ApiException as e:
            if e.status == 404:
                missing.append("deployment")
            else:
                raise

        typer.echo(
            f"Kubernetes cleanup finished for '{resource_name}' in namespace '{namespace}'. "
            f"Deleted: {deleted or ['none']} | Missing: {missing or ['none']}"
        )
    except Exception as e:
        typer.echo(f"Failed to delete Kubernetes resources: {e}")
