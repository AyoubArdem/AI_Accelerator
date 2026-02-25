import os
import json
import signal
import subprocess
import sys
import re
from pathlib import Path

import typer


server_app = typer.Typer(help="Local API server commands")


def _state_dir() -> Path:
    path = Path.home() / ".aiac"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return _state_dir() / "server_state.json"


def _log_path() -> Path:
    return _state_dir() / "server.log"

def _delete_log_file(log_path: str | None) -> None:
    if not log_path:
        return
    try:
        Path(log_path).unlink(missing_ok=True)
    except Exception:
        pass


def _read_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    _state_path().write_text(json.dumps(state, indent=2), encoding="utf-8")


def _clear_state() -> None:
    try:
        _state_path().unlink(missing_ok=True)
    except Exception:
        pass


def _is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                check=False,
            )
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _stop_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        os.kill(pid, signal.SIGTERM)
        return True
    except Exception:
        return False


def _run_migrations() -> tuple[bool, str]:
    migrate_command = [
        sys.executable,
        "-m",
        "django",
        "migrate",
        "--noinput",
        "--settings=AI_Accelerator.settings",
    ]
    try:
        result = subprocess.run(
            migrate_command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, ""
        error_text = (result.stderr or result.stdout or "").strip()
        return False, error_text or "Unknown migration error."
    except Exception as exc:
        return False, str(exc)


def _friendly_server_boot_error(prefix: str, error_text: str) -> str:
    text = str(error_text or "").strip()
    missing_env = re.search(r"([A-Z][A-Z0-9_]+) not found\. Declare it as envvar", text)
    if missing_env:
        env_name = missing_env.group(1)
        return (
            f"{prefix}: missing required environment variable `{env_name}`.\n"
            "Set it in your shell or `.env`, then rerun `aiac server run`."
        )
    if "OperationalError" in text and "connection to server" in text and "5432" in text:
        return (
            f"{prefix}: PostgreSQL is not reachable.\n"
            "Start PostgreSQL or configure fallback SQLite settings, then rerun `aiac server run`."
        )
    if "No module named" in text:
        return (
            f"{prefix}: missing Python dependency.\n"
            f"Details: {text}"
        )
    if text:
        return f"{prefix}: {text}"
    return f"{prefix}."


@server_app.command("run")
def run_server(
    host: str = typer.Option("127.0.0.1", help="Host for the Django server"),
    port: int = typer.Option(8000, help="Port for the Django server"),
    no_reload: bool = typer.Option(True, help="Disable Django auto-reloader"),
    background: bool = typer.Option(
        True,
        "--background/--foreground",
        help="Run server in background (recommended for CLI usage).",
    ),
    migrate: bool = typer.Option(
        True,
        "--migrate/--no-migrate",
        help="Run database migrations before starting the server.",
    ),
):
    """Run the AI Accelerator Django API server."""
    try:
        from django.core.management import execute_from_command_line
    except Exception:
        typer.echo(
            "Django is not installed in this environment. "
            "Install dependencies and try again."
        )
        raise typer.Exit(code=1)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AI_Accelerator.settings")
    django_run_command = [
        sys.executable,
        "-m",
        "django",
        "runserver",
        f"{host}:{port}",
        "--settings=AI_Accelerator.settings",
    ]
    if no_reload:
        django_run_command.append("--noreload")

    if migrate:
        ok, migrate_error = _run_migrations()
        if not ok:
            typer.echo(_friendly_server_boot_error("Failed to apply database migrations automatically", migrate_error))
            raise typer.Exit(code=1)

    if background:
        existing = _read_state()
        existing_pid = int(existing.get("pid", 0) or 0)
        if existing_pid and _is_pid_running(existing_pid):
            host_info = existing.get("host", host)
            port_info = existing.get("port", port)
            typer.echo(f"AIAC server is already running on http://{host_info}:{port_info}/ (PID {existing_pid}).")
            typer.echo("Use `aiac server stop` to stop it first.")
            return

        log_path = _log_path()
        with open(log_path, "a", encoding="utf-8") as log_file:
            proc = subprocess.Popen(
                django_run_command,
                stdout=log_file,
                stderr=log_file,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        _write_state({"pid": proc.pid, "host": host, "port": port, "log_path": str(log_path)})
        typer.echo(f"AIAC server started in background on http://{host}:{port}/")
        typer.echo(f"Logs: {log_path}")
        typer.echo(f"PID: {proc.pid}")
        typer.echo("You can continue running AIAC commands in this terminal.")
        return

    try:
        execute_from_command_line(
            ["aiac", "runserver", f"{host}:{port}"] + (["--noreload"] if no_reload else [])
        )
    except Exception as exc:
        typer.echo(_friendly_server_boot_error("Server startup failed", str(exc)))
        raise typer.Exit(code=1)


@server_app.command("status")
def server_status():
    """Show local AIAC server status."""
    state = _read_state()
    pid = int(state.get("pid", 0) or 0)
    if not pid:
        typer.echo("AIAC server is not running (no state found).")
        return

    if _is_pid_running(pid):
        host = state.get("host", "127.0.0.1")
        port = state.get("port", 8000)
        typer.echo(f"AIAC server is running on http://{host}:{port}/")
        typer.echo(f"PID: {pid}")
        log_path = state.get("log_path")
        if log_path:
            display_log = log_path
            try:
                home = str(Path.home())
                if display_log.startswith(home):
                    display_log = display_log.replace(home, "~", 1)
            except Exception:
                pass
            typer.echo(f"Logs: {display_log}")
        return

    _clear_state()
    typer.echo("AIAC server is not running (stale state was cleaned).")


@server_app.command("stop")
def stop_server():
    """Stop the local AIAC background server."""
    state = _read_state()
    pid = int(state.get("pid", 0) or 0)
    if not pid:
        typer.echo("AIAC server is not running.")
        return

    if not _is_pid_running(pid):
        _delete_log_file(state.get("log_path"))
        _clear_state()
        typer.echo("AIAC server is not running (stale state was cleaned).")
        return

    if _stop_pid(pid):
        _delete_log_file(state.get("log_path"))
        _clear_state()
        typer.echo(f"AIAC server stopped (PID {pid}).")
    else:
        typer.echo(f"Failed to stop AIAC server (PID {pid}).")
