from aiac.deployment.commands import api_app_deployment as deployment_app
from aiac.monitoring.commands import monitoring_api_app as monitoring_app
from aiac.governance.commands import governance_api_app as governance_app

def register_commands(main_app):
    main_app.add_typer(governance_app, name="governance", help="Governance related commands for AIAC.")
    main_app.add_typer(deployment_app, name="deployment", help="Deployment related commands for AIAC.")
    main_app.add_typer(monitoring_app , name="monitoring", help="Monitoring related commands for AIAC.")
