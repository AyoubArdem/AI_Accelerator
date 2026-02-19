import os
import typer


server_app = typer.Typer(help="Local API server commands")


@server_app.command("run")
def run_server(
    host: str = typer.Option("127.0.0.1", help="Host for the Django server"),
    port: int = typer.Option(8000, help="Port for the Django server"),
    no_reload: bool = typer.Option(True, help="Disable Django auto-reloader"),
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
    command = ["aiac", "runserver", f"{host}:{port}"]
    if no_reload:
        command.append("--noreload")
    execute_from_command_line(command)
