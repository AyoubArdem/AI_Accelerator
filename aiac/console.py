from rich.console import Console

console = Console()

def print_message(message: str):
    console.print(f"[bold green]{message}[/bold green]")

def print_error(message: str):
    console.print(f"[bold red]{message}[/bold red]")

def print_warning(message: str):
    console.print(f"[bold yellow]{message}[/bold yellow]")

def print_info(message: str):
    console.print(f"[bold blue]{message}[/bold blue]")
