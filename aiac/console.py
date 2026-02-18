from rich.console import Console
from rich.text import Text
import sys

console = Console()

def print_message(message: str):
    console.print(f"[bold green]{message}[/bold green]")

def print_error(message: str):
    console.print(f"[bold red]{message}[/bold red]")

def print_warning(message: str):
    console.print(f"[bold yellow]{message}[/bold yellow]")

def print_info(message: str):
    console.print(f"[bold blue]{message}[/bold blue]")


def _supports_unicode_banner() -> bool:
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    return "utf" in encoding


def print_aiac_banner(minimal: bool = False) -> None:
    """Render the CLI banner for AIAC."""
    if minimal:
        if _supports_unicode_banner():
            console.print("[bold blue]AIAC[/bold blue] :: Deploy • Monitor • Govern")
        else:
            console.print("[bold blue]AIAC[/bold blue] :: Deploy - Monitor - Govern")
        return

    banner = Text()
    if _supports_unicode_banner():
        banner.append(" █████╗ ██╗ █████╗  ██████╗\n", style="bold blue")
        banner.append("██╔══██╗██║██╔══██╗██╔════╝\n", style="bold blue")
        banner.append("███████║██║███████║██║     \n", style="bold blue")
        banner.append("██╔══██║██║██╔══██║██║     \n", style="bold blue")
        banner.append("██║  ██║██║██║  ██║╚██████╗\n", style="bold blue")
        banner.append("╚═╝  ╚═╝╚═╝╚═╝  ╚═╝ ╚═════╝\n\n", style="bold blue")
    else:
        banner.append("    _    ___    _    ____\n", style="bold blue")
        banner.append("   / \\  |_ _|  / \\  / ___|\n", style="bold blue")
        banner.append("  / _ \\  | |  / _ \\| |\n", style="bold blue")
        banner.append(" / ___ \\ | | / ___ \\ |___\n", style="bold blue")
        banner.append("/_/   \\_\\___/_/   \\_\\____|\n\n", style="bold blue")

    banner.append("      ", style="white")
    banner.append("AIAC", style="bold bright_blue")
    if _supports_unicode_banner():
        banner.append("  ·  AI ACCELERATOR CORE\n", style="bold white")
        banner.append(" Deploy  •  Monitor  •  Govern\n", style="dim")
    else:
        banner.append("  -  AI ACCELERATOR CORE\n", style="bold white")
        banner.append(" Deploy  -  Monitor  -  Govern\n", style="dim")

    console.print(banner)
