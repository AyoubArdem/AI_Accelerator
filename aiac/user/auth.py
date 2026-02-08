import typer , requests
from aiac.config import get_config , save_config

auth_app = typer.Typer()


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
        typer.echo("✅ Registration successful! Please check your email to activate your account.")
    else:
        typer.echo(f"❌ Registration failed ({response.status_code}): {response.text}")

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
def logout(refresh_token: str = typer.Option(..., prompt=True, hide_input=True, help="Refresh token to logout")):

    "Logout a user"
    config = get_config()
    url = f"{config.api_base_url}/api/users/logout/"
    data = {"refresh": refresh_token}
    response = requests.post(url, json=data)
    if response.status_code == 200:
        typer.echo("Logout successful!")
    else:
        typer.echo(f"Logout failed: {response.text}")

