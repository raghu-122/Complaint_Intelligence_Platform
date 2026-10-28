"""
YottaFlex Complaint Intelligence Platform — CLI
Usage: python cli.py [command]
"""
from __future__ import annotations

import os
import sys

# Ensure backend root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import time
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import select

from app.anomaly.detector import AnomalyDetector, inject_anomalies
from app.config import get_settings
from app.database import Base, SessionLocal, init_db
from app.exports.exporter import BaselineExporter, CSVExporter, JSONExporter
from app.generator.loader import load_all
from app.generator.orchestrator import DataGenerator
from app.reproducibility.engine import ReproducibilityEngine
from app.validation.validator import ValidationEngine

console = Console()


@click.group()
def cli():
    """YottaFlex Complaint Intelligence Platform CLI."""
    pass


@cli.command()
@click.option(
    "--scale",
    type=click.Choice(["starter", "full"], case_sensitive=False),
    default="starter",
    help="Scale: 'starter' (~50 complaints) or 'full' (~2000 complaints).",
)
@click.option(
    "--seed",
    default=20261022,
    type=int,
    help="Random seed for reproducible generation.",
)
@click.option(
    "--clear/--no-clear",
    default=True,
    help="Clear existing database records before loading.",
)
@click.option(
    "--export/--no-export",
    default=True,
    help="Export CSV/JSON baseline files and manifest.",
)
def generate(scale: str, seed: int, clear: bool, export: bool):
    """Run data generation, persist to SQLite, and export baseline files."""
    init_db()
    console.print(
        f"[bold cyan]YottaFlex Data Generator[/bold cyan] (Scale: [yellow]{scale}[/yellow], Seed: [yellow]{seed}[/yellow])"
    )

    start_time = time.time()
    with console.status("[bold green]Generating synthetic entities..."):
        generator = DataGenerator(seed=seed, scale=scale)
        data = generator.generate_all()

    with console.status("[bold green]Persisting to SQLite database..."):
        with SessionLocal() as db:
            counts = load_all(db, data, clear_first=clear)

    manifest_info = None
    if export:
        with console.status("[bold green]Exporting CSVs, JSONs, and manifest with SHA-256 hashes..."):
            exporter = BaselineExporter()
            manifest = exporter.export_and_create_manifest(data=data, seed=seed, scale=scale)
            manifest_info = manifest

    elapsed = round(time.time() - start_time, 2)

    # Print Rich Table of counts
    table = Table(
        title="Generated Dataset Summary",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Entity", style="cyan", width=26)
    table.add_column("Record Count", justify="right", style="bold green")

    for entity, count in sorted(counts.items(), key=lambda x: x[0]):
        table.add_row(entity.replace("_", " ").title(), f"{count:,}")

    console.print(table)
    console.print(
        f"\n[bold green]Success![/bold green] Generated {counts.get('complaints', 0):,} complaints across {len(counts)} entity types in [bold]{elapsed}s[/bold]."
    )

    if manifest_info:
        console.print(
            "[dim]Baseline manifest saved to [cyan]backend/data/baseline/manifest.json[/cyan][/dim]"
        )


@cli.command()
def validate():
    """Run ValidationEngine and print findings summary."""
    init_db()
    console.print("[bold cyan]Running YottaFlex Data Validation Suite...[/bold cyan]\n")

    with SessionLocal() as db:
        engine = ValidationEngine(db)
        report = engine.run_all()

    table = Table(
        title="Validation Findings",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Category", style="cyan", width=16)
    table.add_column("Check Name", style="bold", width=34)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Message", style="dim")

    for f in report.findings:
        if f.status == "pass":
            status_badge = "[green]PASS[/green]"
        elif f.status == "warn":
            status_badge = "[yellow]WARN[/yellow]"
        else:
            status_badge = "[red]FAIL[/red]"
        table.add_row(
            f.category.replace("_", " ").title(),
            f.check_name,
            status_badge,
            f.message,
        )

    console.print(table)

    summary = report.summary
    summary_text = (
        f"Total Checks: [bold]{summary.total}[/bold] | "
        f"Passed: [bold green]{summary.passed}[/bold green] | "
        f"Warnings: [bold yellow]{summary.warned}[/bold yellow] | "
        f"Failed: [bold red]{summary.failed}[/bold red] "
        f"([dim]Execution time: {summary.execution_time_seconds}s[/dim])"
    )
    console.print(Panel(summary_text, title="Validation Summary", border_style="cyan"))

    if summary.failed > 0:
        sys.exit(1)


@cli.command("detect-anomalies")
def detect_anomalies_cmd():
    """Run AnomalyDetector and print detection metrics."""
    init_db()
    console.print("[bold cyan]Running YottaFlex Anomaly Detection Suite...[/bold cyan]\n")

    with SessionLocal() as db:
        detector = AnomalyDetector(db)
        result = detector.detect()

    metrics_text = (
        f"Detected: [bold]{result.detected_count}[/bold] | "
        f"Ground Truth: [bold]{result.ground_truth_count}[/bold] | "
        f"Precision: [bold green]{result.precision:.2%}[/bold green] | "
        f"Recall: [bold green]{result.recall:.2%}[/bold green] | "
        f"F1-Score: [bold green]{result.f1_score:.2%}[/bold green]"
    )
    console.print(Panel(metrics_text, title="Anomaly Detection Metrics", border_style="cyan"))

    table = Table(
        title="Detected Anomalies",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Anomaly ID", style="cyan", width=16)
    table.add_column("Type", style="bold", width=28)
    table.add_column("Severity", justify="center", width=10)
    table.add_column("Complaint ID", style="yellow", width=22)
    table.add_column("Description", style="dim")

    for a in result.anomalies:
        sev_style = "red" if a.severity.lower() == "high" else "yellow"
        table.add_row(
            a.anomaly_id,
            a.anomaly_type,
            f"[{sev_style}]{a.severity.upper()}[/{sev_style}]",
            a.complaint_id or "-",
            a.description,
        )

    console.print(table)


@cli.command("inject-anomalies")
@click.option("--count", default=6, type=int, help="Number of anomaly scenarios to inject.")
def inject_anomalies_cmd(count: int):
    """Inject test anomalies into the active database."""
    init_db()
    console.print(f"[bold cyan]Injecting {count} anomaly scenarios...[/bold cyan]")

    with SessionLocal() as db:
        resp = inject_anomalies(db, count=count)

    if not resp.success:
        console.print(f"[bold red]Injection failed:[/bold red] {resp.message}")
        sys.exit(1)

    table = Table(
        title="Injected Anomalies",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Anomaly ID", style="cyan", width=14)
    table.add_column("Type", style="bold", width=28)
    table.add_column("Severity", justify="center", width=10)
    table.add_column("Complaint ID", style="yellow", width=22)
    table.add_column("Description", style="dim")

    for a in resp.anomalies:
        table.add_row(
            a.anomaly_id,
            a.anomaly_type,
            a.severity.upper(),
            a.complaint_id or "-",
            a.description,
        )

    console.print(table)
    console.print(
        f"[bold green]Success![/bold green] Injected {resp.injected_count} anomaly records."
    )


@cli.command()
@click.option("--run-id", default=None, type=str, help="Generation Run ID to verify.")
@click.option("--seed", default=None, type=int, help="Seed to verify against baseline manifest.")
@click.option(
    "--scale",
    default=None,
    type=click.Choice(["starter", "full"], case_sensitive=False),
    help="Scale to verify.",
)
def reproduce(run_id: str | None, seed: int | None, scale: str | None):
    """Verify deterministic generation and bitwise reproducibility."""
    console.print("[bold cyan]Running Reproducibility Verification...[/bold cyan]")

    target_seed = seed
    target_scale = scale

    if run_id:
        with SessionLocal() as db:
            from app.models.generation_run import GenerationRun
            run = db.scalars(select(GenerationRun).where(GenerationRun.run_id == run_id)).first()
            if run:
                target_seed = run.seed
                target_scale = run.scale
                console.print(
                    f"Found Run ID [yellow]{run_id}[/yellow]: Seed={target_seed}, Scale={target_scale}"
                )
            else:
                console.print(
                    f"[yellow]Run ID {run_id} not found in database; using manifest/specified params.[/yellow]"
                )

    engine = ReproducibilityEngine()
    result = engine.run_check(seed=target_seed, scale=target_scale)

    if result.get("status") == "ERROR":
        console.print(f"[bold red]Error:[/bold red] {result.get('message')}")
        sys.exit(1)

    table = Table(
        title="Bitwise Reproducibility Audit",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Artifact File", style="cyan", width=34)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Baseline SHA-256", style="dim", width=18)
    table.add_column("Reproduced SHA-256", style="dim", width=18)

    for item in result.get("comparisons", []):
        status_badge = (
            "[green]MATCH[/green]" if item["status"] == "MATCH" else "[red]MISMATCH[/red]"
        )
        table.add_row(
            item["file"],
            status_badge,
            item["original_sha256"],
            item["new_sha256"],
        )

    console.print(table)

    if result.get("reproducible"):
        console.print(
            Panel(
                f"[bold green]100% BITWISE MATCH DETECTED[/bold green]\n"
                f"All {result.get('total_files')} exported baseline files matched identical SHA-256 hashes.",
                title="Verdict: PASS",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]REPRODUCIBILITY CHECK FAILED[/bold red]\n"
                f"{len(result.get('mismatches', []))} files differed from baseline manifest.",
                title="Verdict: FAIL",
                border_style="red",
            )
        )
        sys.exit(1)


@cli.command()
@click.option("--host", default="127.0.0.1", type=str, help="Host binding.")
@click.option("--port", default=8000, type=int, help="Port binding.")
@click.option("--reload/--no-reload", default=False, help="Auto-reload on code changes.")
def server(host: str, port: int, reload: bool):
    """Start the FastAPI application server."""
    import uvicorn
    settings = get_settings()

    target_host = host or settings.api_host
    target_port = port or settings.api_port
    target_reload = reload if reload is not None else settings.api_reload

    console.print("[bold cyan]Starting YottaFlex Complaint Intelligence Server[/bold cyan]")
    console.print(
        f"Listening on: [bold green]http://{target_host}:{target_port}[/bold green] (reload={target_reload})\n"
    )

    uvicorn.run(
        "app.main:app",
        host=target_host,
        port=target_port,
        reload=target_reload,
    )


@cli.command()
@click.option(
    "--format",
    "export_format",
    type=click.Choice(["csv", "json", "both"], case_sensitive=False),
    default="both",
    help="Export file format: csv, json, or both.",
)
@click.option(
    "--output-dir",
    type=str,
    default="data/exports",
    help="Output directory for exported files.",
)
def export(export_format: str, output_dir: str):
    """Export dataset to CSV and/or JSON format."""
    init_db()
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    console.print(
        f"[bold cyan]Exporting data to [yellow]{out_path}[/yellow] (Format: [yellow]{export_format}[/yellow])...[/bold cyan]"
    )

    data: dict[str, list[dict]] = {}
    with SessionLocal() as db:
        for table_name, table in Base.metadata.tables.items():
            rows = db.execute(select(table)).mappings().all()
            records = []
            for row in rows:
                rec = {}
                for col, val in row.items():
                    if isinstance(val, (datetime, date)):
                        rec[col] = val.isoformat()
                    elif isinstance(val, Decimal):
                        rec[col] = str(val)
                    else:
                        rec[col] = val
                records.append(rec)
            data[table_name] = records

    # If database is empty, generate starter dataset for export
    total_records = sum(len(v) for v in data.values())
    if total_records == 0:
        console.print("[yellow]Database is empty. Generating starter dataset to export...[/yellow]")
        gen = DataGenerator(seed=20261022, scale="starter")
        data = gen.generate_all()

    table = Table(title="Export Summary", show_header=True, header_style="bold magenta")
    table.add_column("Entity / Table", style="cyan", width=26)
    table.add_column("Records", justify="right", style="green")
    table.add_column("CSV Export", style="dim")
    table.add_column("JSON Export", style="dim")

    csv_exp = CSVExporter(out_path / "csv") if export_format in ("csv", "both") else None
    json_exp = JSONExporter(out_path / "json") if export_format in ("json", "both") else None

    for entity_name, records in sorted(data.items(), key=lambda x: x[0]):
        csv_file = "-"
        json_file = "-"
        if csv_exp:
            p = csv_exp.export_entity(entity_name, records)
            csv_file = p.name
        if json_exp:
            p = json_exp.export_entity(entity_name, records)
            json_file = p.name
        table.add_row(entity_name, f"{len(records):,}", csv_file, json_file)

    console.print(table)
    console.print(
        f"\n[bold green]Success![/bold green] Data successfully exported to [cyan]{out_path}[/cyan]."
    )


if __name__ == "__main__":
    cli()
