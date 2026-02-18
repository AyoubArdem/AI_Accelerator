import typer , requests
from aiac.config import get_config , save_config, load_config
from aiac.client import AIACClient
from rich.console import Console
from rich.table import Table

auth_app = typer.Typer()
console = Console()


@auth_app.command("register")
def register(
    email: str = typer.Option(..., prompt=True, help="Email address for registration"),
    username: str = typer.Option(..., prompt=True, help="Username for registration"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password for registration"),
    role: str = typer.Option(..., prompt=True, help="Role of the user (client or admin)")
):
    "Register a new user"
    config = get_config()
    url = f"{config.api_base_url}/api/users/register/"
    data = {"email": email, "username": username, "password": password, "role": role}
    response = requests.post(url, json=data)
    if response.status_code == 201:
        payload = response.json()
        typer.echo("Registration successful! Please check your email to activate your account.")
        if payload.get("activation_link"):
            typer.echo(f"Activation link: {payload['activation_link']}")
    else:
        message = None
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        if isinstance(payload, dict):
            if "username" in payload:
                message = "This username is already taken. Please choose another username."
            elif "email" in payload:
                message = "This email is already registered. Try logging in or use another email."
            elif "password" in payload:
                message = "Password does not meet requirements. Please choose a stronger password."
            elif "role" in payload:
                message = "Invalid role. Please use one of the supported roles."
            elif "detail" in payload:
                message = str(payload["detail"])
            elif "error" in payload:
                message = str(payload["error"])
            elif payload:
                first_key = next(iter(payload))
                value = payload[first_key]
                if isinstance(value, list) and value:
                    message = str(value[0])
                else:
                    message = str(value)

        if not message:
            message = "Registration failed. Please check your input and try again."
        typer.echo(message)

@auth_app.command("login")

def login(email: str = typer.Option(..., prompt=True, help="Email address for login"),
          password: str = typer.Option(..., prompt=True, hide_input=True, help="Password for login")):

    "Login a user"
    config = get_config()
    url = f"{config.api_base_url}/api/users/login/"
    data = {"email": email, "password": password}
    response = requests.post(url, json=data)

    if response.status_code == 200:
        access = response.json().get("access")
        refresh = response.json().get("refresh")
        save_config({"access": access, "refresh": refresh}, config.api_base_url)
        typer.echo(f"Login successful! Tokens saved.")
    else:
        typer.echo(f"Login failed: {response.text}")

@auth_app.command("logout")
def logout(refresh_token: str = typer.Option("", prompt=True, hide_input=True, help="Refresh token to logout (leave blank to use saved)")):

    "Logout a user"
    tokens = load_config()
    if not refresh_token.strip():
        if tokens and "refresh" in tokens:
            refresh_token = tokens["refresh"]
        else:
            typer.echo("Refresh token is required.")
            return
    config = get_config()
    url = f"{config.api_base_url}/api/users/logout/"
    data = {"refresh": refresh_token}
    headers = {}
    if tokens and "access" in tokens:
        headers["Authorization"] = f"Bearer {tokens['access']}"
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        typer.echo("Logout successful!")
    else:
        msg = response.text.strip()
        if not msg:
            msg = f"Status {response.status_code}"
        typer.echo(f"Logout failed: {msg}")


@auth_app.command("me")
def me():
    "Get current user info"
    client = AIACClient(base_path="users")
    try:
        response = client.get("me/")
        data = response.json()
        if not isinstance(data, dict):
            typer.echo("User information is not available in expected format.")
            return

        table = Table(title="Current User Profile")
        table.add_column("Field", style="bold cyan")
        table.add_column("Value", style="white")
        table.add_row("ID", str(data.get("id", "-")))
        table.add_row("Email", str(data.get("email", "-")))
        table.add_row("Username", str(data.get("username", "-")))
        table.add_row("Role", str(data.get("role", "-")))
        table.add_row("Active", "yes" if data.get("is_active") else "no")
        table.add_row("Staff", "yes" if data.get("is_staff") else "no")
        table.add_row("Joined", str(data.get("date_joined", "-")))
        console.print(table)
    except Exception as e:
        msg = str(e)
        if "401" in msg and (
            "token_not_valid" in msg
            or "Token is expired" in msg
            or "Given token not valid for any token type" in msg
        ):
            typer.echo(
                "Session expired or token is invalid. Please run `aiac auth login` and try again."
            )
            return
        typer.echo(f"Failed to fetch user info: {msg}")


@auth_app.command("token-show")
def token_show(
    email: str = typer.Option(..., prompt=True, help="Email address"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password")
):
    "Show saved tokens after password verification"
    config = get_config()
    url = f"{config.api_base_url}/api/users/login/"
    data = {"email": email, "password": password}
    response = requests.post(url, json=data)
    if response.status_code != 200:
        typer.echo("Invalid email or password.")
        return

    display_path = "~/.aiac/config.json"
    tokens = load_config()
    if not tokens:
        typer.echo(f"No tokens found. Expected at: {display_path}")
        return

    def mask_token(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 12:
            return "*" * len(value)
        return f"{value[:6]}...{value[-6:]}"

    masked = {
        "API_BASE_URL": tokens.get("API_BASE_URL"),
        "access": mask_token(tokens.get("access", "")),
        "refresh": mask_token(tokens.get("refresh", "")),
    }

    typer.echo(f"Token file: {display_path}")
    typer.echo(masked)

