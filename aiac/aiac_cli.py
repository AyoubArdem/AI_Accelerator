#!/usr/bin/env python3
"""
AIAC CLI - Command Line Interface for AI Accelerator

This script provides the main entry point for the AIAC CLI tool.
"""

import typer
import sys
from aiac.user.auth import auth_app
from aiac.deployment.commands import api_app_deployment
from aiac.monitoring.commands import monitoring_api_app
from aiac.governance.commands import governance_api_app
from aiac.server.commands import server_app
from aiac.console import print_aiac_banner

# Create the main CLI app
app = typer.Typer(
    name="aiac",
    help="AI Accelerator Command Line Interface",
    add_completion=False,
)

# Add sub-commands
app.add_typer(auth_app, name="auth", help="Authentication commands")
app.add_typer(api_app_deployment, name="deployment", help="Deployment management commands")
app.add_typer(monitoring_api_app, name="monitoring", help="Monitoring and analytics commands")
app.add_typer(governance_api_app, name="governance", help="Governance and policy commands")
app.add_typer(server_app, name="server", help="Local API server commands")


@app.callback(invoke_without_command=True)
def root(ctx: typer.Context):
    """Show AIAC banner when CLI is invoked without a subcommand."""
    if ctx.invoked_subcommand is None:
        print_aiac_banner()
        typer.echo(ctx.get_help())
        raise typer.Exit()


def main():
    if len(sys.argv) == 2 and sys.argv[1] in {"--help", "-h"}:
        print_aiac_banner()
    app()

if __name__ == "__main__":
    main()
