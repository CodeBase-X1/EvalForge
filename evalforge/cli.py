"""
EvalForge CLI

Usage:
    evalforge run --traces 500 --output ./my_evals
    evalforge ui
    evalforge status
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="evalforge",
    help="Auto-generate eval suites from your production AI agent traces.",
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        from evalforge import __version__

        typer.echo(f"evalforge {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """EvalForge — auto-generate eval suites from production AI agent traces."""


@app.command()
def run(
    traces: int = typer.Option(500, "--traces", "-n", help="Number of traces to analyze"),
    output: str = typer.Option("./output", "--output", "-o", help="Output directory"),
    project: str | None = typer.Option(None, "--project", "-p", help="Phoenix project name"),
    phoenix: str | None = typer.Option(None, "--phoenix", help="Phoenix endpoint URL"),
    clusters: int = typer.Option(0, "--clusters", "-k", help="Number of clusters (0=auto)"),
    cases: int = typer.Option(10, "--cases", "-c", help="Eval cases per cluster"),
) -> None:
    """Run the full EvalForge pipeline and generate an eval dataset."""
    from evalforge.config import settings

    # Override settings from CLI flags
    if phoenix:
        settings.phoenix_endpoint = phoenix
    if clusters:
        settings.evalforge_num_clusters = clusters
    if cases:
        settings.evalforge_cases_per_cluster = cases
    settings.evalforge_output_dir = output

    if not settings.gemini_api_key:
        console.print(
            "[red]Error:[/red] GEMINI_API_KEY is not set. "
            "Add it to your .env file or set the environment variable."
        )
        raise typer.Exit(1)

    console.print()
    console.print("[bold]⚒️  EvalForge[/bold]")
    console.print(f"   Phoenix:  {settings.phoenix_endpoint}")
    console.print(f"   Traces:   {traces}")
    console.print(f"   Output:   {output}")
    console.print()

    from evalforge.agent.agent import run_pipeline

    asyncio.run(run_pipeline(trace_limit=traces, output_dir=output, project_name=project))


@app.command()
def ui(
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)"),
) -> None:
    """Launch the EvalForge web UI."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn is required:[/red] pip install uvicorn")
        raise typer.Exit(1)

    console.print(f"[bold]⚒️  EvalForge UI[/bold] → http://{host}:{port}")
    uvicorn.run(
        "evalforge.ui.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def status() -> None:
    """Check Phoenix connection and configuration."""
    import asyncio

    from evalforge.config import settings

    console.print()
    console.print("[bold]EvalForge Configuration[/bold]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()

    table.add_row("Phoenix endpoint", settings.phoenix_endpoint)
    table.add_row("Gemini model", settings.gemini_model)
    table.add_row("Trace limit", str(settings.evalforge_trace_limit))
    table.add_row("Failure threshold", str(settings.evalforge_failure_threshold))
    table.add_row("Cases per cluster", str(settings.evalforge_cases_per_cluster))
    table.add_row("Output dir", settings.evalforge_output_dir)
    table.add_row(
        "Gemini API key",
        "[green]set[/green]" if settings.gemini_api_key else "[red]NOT SET[/red]",
    )

    console.print(table)
    console.print()

    # Test Phoenix connection
    async def _check():
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{settings.phoenix_endpoint}/healthz")
                if r.status_code == 200:
                    console.print("[green]✓[/green] Phoenix is reachable")
                else:
                    console.print(f"[yellow]⚠[/yellow] Phoenix returned {r.status_code}")
        except Exception as exc:
            console.print(f"[red]✗[/red] Cannot reach Phoenix: {exc}")

    asyncio.run(_check())


if __name__ == "__main__":
    app()
