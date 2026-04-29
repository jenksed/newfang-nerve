import typer
from rich.console import Console
from typing import Optional
import uvicorn

app = typer.Typer(
    name="newfang",
    help="NewFang (Spine): Local-first AI project planning and documentation OS.",
    add_completion=False,
)
console = Console()

from newfang.core.scanner import Scanner
from rich.table import Table

@app.command()
def scan(
    path: str = typer.Argument(".", help="Path to the project to scan."),
):
    """
    Find docs, code, and project structure.
    """
    console.print(f"[bold blue]Scanning project at:[/bold blue] {path}")
    
    scanner = Scanner(path)
    state = scanner.scan()

    table = Table(title=f"Project Scan: {state.name}")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_column("Files (preview)", style="green")

    def get_preview(files):
        return ", ".join([f.path for f in files[:3]]) + ("..." if len(files) > 3 else "")

    table.add_row("Documentation", str(state.stats["docs_count"]), get_preview(state.docs_files))
    table.add_row("Code", str(state.stats["code_count"]), get_preview(state.code_files))
    table.add_row("System (.newfang)", str(state.stats["system_count"]), get_preview(state.system_files))

    console.print(table)
    console.print(f"\n[bold green]Total Files Tracked:[/bold green] {state.stats['total_files']}")

from newfang.core.reconciler import Reconciler
from newfang.utils.config import load_config
import asyncio

@app.command()
def reconcile(
    path: str = typer.Argument(".", help="Path to the project to reconcile."),
    target: Optional[str] = typer.Option(None, help="Specific target to reconcile (e.g., 'docs')."),
):
    """
    Outcome-based drift detection using repo-native playbooks.
    """
    console.print(f"[bold magenta]Reconciling project drift at:[/bold magenta] {path}")
    
    config = load_config(path)
    scanner = Scanner(path)
    state = scanner.scan()
    
    reconciler = Reconciler(config)
    
    with console.status("[bold green]Auditing docs vs code... (Local LLM)"):
        report = asyncio.run(reconciler.reconcile(state))

    console.print(f"\n[bold yellow]Drift Report for {report.project_name}[/bold yellow]")
    for item in report.items:
        console.print(f"\n[bold]{item.title}[/bold] ({item.severity})")
        console.print(f"[dim]{item.type.value}[/dim]")
        console.print(item.description)

    console.print(f"\n[bold green]Reconciliation complete.[/bold green]")

@app.command()
def cleanup(
    apply: bool = typer.Option(False, "--apply", help="Apply the cleanup changes."),
):
    """
    Verification-loop-driven doc standardization.
    """
    if not apply:
        console.print("[bold yellow]Running doc cleanup dry-run...[/bold yellow]")
    else:
        console.print("[bold green]Applying doc cleanup...[/bold green]")
    # TODO: Implement cleanup logic
    console.print("[green]Cleanup complete (stubs).[/green]")

@app.command()
def plan():
    """
    Multi-agent roadmap and milestone generation.
    """
    console.print("[bold cyan]Generating project plan...[/bold cyan]")
    # TODO: Implement planning logic
    console.print("[green]Planning complete (stubs).[/green]")

@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
):
    """
    Launch the NewFang Agency Tool (Local Web Dashboard).
    """
    console.print(f"[bold green]Launching NewFang Agency Tool at http://{host}:{port}[/bold green]")
    uvicorn.run("newfang.api.app:app", host=host, port=port, reload=True)

if __name__ == "__main__":
    app()
