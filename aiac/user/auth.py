import typer , requests
from aiac.config import get_config , save_config

auth_app = typer.Typer(help="user authentication commands")

@auth_app.command("register")
def register(username: str = typer.Option(..., prompt=True, help="Username for registration"),
             password: str = typer.Option(..., prompt=True, hide_input=True, help="Password for registration"),
             email: str = typer.Option(..., prompt=True , help="Email address for registration", hide_input=True),
             role: str = typer.Option(choices=["client", "admin"], prompt=True, help="Role of the user")):
    
    "Register a new user"
    config = get_config()
    url = f"{config}/register/"
    data = {"username": username, "password": password, "email": email, "role": role}
    response = requests.post(url, json=data)
    if response.status_code == 201:
        typer.echo("Registration successful! Please check your email to activate your account.")
    else:
        typer.echo(f"Registration failed: {response.text}")

@auth_app.command("login")
def login(email: str= typer.Option(..., prompt=True, hide_input=True, help="Email address for login"),
          password: str = typer.Option(..., prompt=True, hide_input=True, help="Password for login")):
    
    "Login a user"
    config = get_config()
    url = f"{config}/login/"
    data = {"email": email, "password": password}
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        access = response.json().get("access")
        refresh = response.json().get("refresh")
        save_config({"access": access, "refresh": refresh}, config)
        typer.echo(f"Login successful! Your token: access : {access} refresh : {refresh}")
    else:
        typer.echo(f"Login failed: {response.text}")

@auth_app.command("logout")
def logout(refresh_token: str = typer.Option(..., prompt=True, hide_input=True, help="Refresh token to logout")):
    
    "Logout a user"
    config = get_config()
    url = f"{config}/logout/"
    data = {"refresh": refresh_token}
    response = requests.post(url, json=data)
    if response.status_code == 200:
        typer.echo("Logout successful!")
    else:
        typer.echo(f"Logout failed: {response.text}")

