import typer , requests
from aiac.config import get_config , save_config, load_config, delete_config
from aiac.client import AIACClient
from rich.console import Console
from rich.table import Table

auth_app = typer.Typer()
console = Console()


def _friendly_network_error(action: str, api_base_url: str) -> str:
    return (
        f"Unable to {action} because the API server is not reachable at {api_base_url}.\n"
        "Start the server with `aiac server run --host 127.0.0.1 --port 8000` and try again."
    )


def _is_html_error_blob(text: str) -> bool:
    t = (text or "").lower()
    return "<!doctype html>" in t or "<html" in t


def _friendly_backend_error(prefix: str, error_text: str) -> str:
    text = str(error_text or "")
    if "API server is not reachable" in text:
        return text
    if "OperationalError" in text:
        return (
            f"{prefix}: backend database is not ready.\n"
            "Start the API server with migrations:\n"
            "  aiac server run --migrate\n"
            "Then retry."
        )
    if _is_html_error_blob(text):
        return (
            f"{prefix}: backend returned an internal server error.\n"
            "Check backend logs with:\n"
            "  aiac server status\n"
            "  type %USERPROFILE%\\.aiac\\server.log"
        )
    return f"{prefix}: {text}"


def _friendly_http_error(prefix: str, status_code: int, text: str) -> str:
    raw = (text or "").strip()
    if status_code == 401:
        return "Invalid email or password."
    if status_code == 403:
        return "Access denied. Please check your account permissions."
    if status_code == 404:
        return f"{prefix}: endpoint not found. Ensure server and API routes are up to date."
    if status_code >= 500:
        return _friendly_backend_error(prefix, raw)
    if raw:
        return f"{prefix} ({status_code}): {raw[:300]}"
    return f"{prefix} ({status_code})."


def _extract_first_error_message(payload) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        for item in payload:
            msg = _extract_first_error_message(item)
            if msg:
                return msg
        return ""
    if isinstance(payload, dict):
        # Prefer common DRF keys first.
        for key in ("detail", "error", "non_field_errors"):
            if key in payload:
                msg = _extract_first_error_message(payload.get(key))
                if msg:
                    return msg
        # Fallback to first available field error.
        for value in payload.values():
            msg = _extract_first_error_message(value)
            if msg:
                return msg
    return ""


@auth_app.command("register")
def register(
    email: str = typer.Option(..., prompt=True, help="Email address for registration"),
    username: str = typer.Option(..., prompt=True, help="Username for registration"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password for registration"),
    role: str = typer.Option(..., prompt=True, help="Role of the user (client, developer, admin)")
):
    "Register a new user"
    config = get_config()
    url = f"{config.api_base_url}/api/users/register/"
    data = {"email": email, "username": username, "password": password, "role": role}
    try:
        response = requests.post(url, json=data)
    except requests.RequestException:
        typer.echo(_friendly_network_error("register", config.api_base_url))
        return
    if response.status_code == 201:
        payload = response.json()
        typer.echo("Registration successful! Please check your email to activate your account.")
        if payload.get("activation_link"):
            typer.echo(f"Activation link: {payload['activation_link']}")
    else:
        message = None
        raw_error_text = (response.text or "").strip()
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
            else:
                extracted = _extract_first_error_message(payload)
                if extracted:
                    message = f"Registration failed: {extracted}"

        if not message:
            if raw_error_text:
                snippet = raw_error_text[:300]
                message = f"Registration failed ({response.status_code}): {snippet}"
            else:
                message = f"Registration failed ({response.status_code}). Please check your input and try again."
        typer.echo(message)

@auth_app.command("login")

def login(email: str = typer.Option(..., prompt=True, help="Email address for login"),
          password: str = typer.Option(..., prompt=True, hide_input=True, help="Password for login")):

    "Login a user"
    config = get_config()
    url = f"{config.api_base_url}/api/users/login/"
    data = {"email": email, "password": password}
    try:
        response = requests.post(url, json=data)
    except requests.RequestException:
        typer.echo(_friendly_network_error("login", config.api_base_url))
        return

    if response.status_code == 200:
        access = response.json().get("access")
        refresh = response.json().get("refresh")
        save_config({"access": access, "refresh": refresh}, config.api_base_url)
        typer.echo(f"Login successful! Tokens saved.")
    else:
        typer.echo(_friendly_http_error("Login failed", response.status_code, response.text))

@auth_app.command("logout")
def logout(
    refresh_token: str = typer.Option(
        None,
        "--refresh",
        help="Refresh token to logout (defaults to saved token)",
    ),
):

    "Logout a user"
    tokens = load_config()
    if not refresh_token:
        if tokens and "refresh" in tokens:
            refresh_token = tokens["refresh"]
            source = "saved token"
        else:
            refresh_token = typer.prompt("Refresh token", hide_input=True)
            if not refresh_token.strip():
                typer.echo("Refresh token is required.")
                return
            source = "prompt"
    else:
        source = "flag"
    config = get_config()
    url = f"{config.api_base_url}/api/users/logout/"
    data = {"refresh": refresh_token}
    headers = {}
    if tokens and "access" in tokens:
        headers["Authorization"] = f"Bearer {tokens['access']}"
    try:
        response = requests.post(url, json=data, headers=headers)
    except requests.RequestException:
        typer.echo(_friendly_network_error("logout", config.api_base_url))
        return
    if response.status_code == 200:
        delete_config()
        typer.echo(f"Logout successful! ({source}) Token file removed.")
    else:
        if response.status_code == 400:
            typer.echo("Logout failed: refresh token is invalid or already revoked. Please login again.")
        elif response.status_code == 401:
            typer.echo("Logout failed: access token is invalid or expired. Please login again.")
        else:
            typer.echo(_friendly_http_error("Logout failed", response.status_code, response.text))


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
        typer.echo(_friendly_backend_error("Failed to fetch user info", msg))


@auth_app.command("token-show")
def token_show(
    email: str = typer.Option(..., prompt=True, help="Email address"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password")
):
    "Show saved tokens after password verification"
    config = get_config()
    url = f"{config.api_base_url}/api/users/login/"
    data = {"email": email, "password": password}
    try:
        response = requests.post(url, json=data)
    except requests.RequestException:
        typer.echo(_friendly_network_error("show tokens", config.api_base_url))
        return
    if response.status_code != 200:
        typer.echo(_friendly_http_error("Token check failed", response.status_code, response.text))
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
    table = Table(title="Saved Tokens (masked)")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("API_BASE_URL", str(masked.get("API_BASE_URL", "")))
    table.add_row("access", str(masked.get("access", "")))
    table.add_row("refresh", str(masked.get("refresh", "")))
    console.print(table)
    typer.echo("Security note: keep this file private. Anyone with access can act as you.")


@auth_app.command("password-reset")
def password_reset(
    email: str = typer.Option(..., prompt=True, help="Email address to reset password"),
):
    "Request a secure password reset link"
    config = get_config()
    url = f"{config.api_base_url}/api/users/password-reset/request/"
    try:
        response = requests.post(url, json={"email": email})
    except requests.RequestException:
        typer.echo(_friendly_network_error("request password reset", config.api_base_url))
        return
    if response.status_code == 200:
        payload = response.json() if response.text else {}
        typer.echo("Password reset link sent. Check your link.")
        if isinstance(payload, dict) and payload.get("reset_link"):
            typer.echo(f"Reset link: {payload['reset_link']}")
    else:
        typer.echo(_friendly_http_error("Password reset request failed", response.status_code, response.text))
