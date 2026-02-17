"""Lightroom Classic Catalog Automation CLI."""

from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console

from .catalog import CatalogConnection, CatalogError

load_dotenv()

console = Console()


@click.group()
@click.option(
    "--catalog",
    "-c",
    type=click.Path(exists=True),
    envvar="LRC_CATALOG_PATH",
    required=True,
    help="Path to .lrcat catalog file",
)
@click.option("--verbose", "-v", is_flag=True)
@click.option(
    "--target-layout",
    envvar="LRC_TARGET_LAYOUT",
    default="%Y/%m/",
    show_default=True,
    help="Target folder layout (strftime format)",
)
@click.pass_context
def cli(ctx: click.Context, catalog: str, verbose: bool, target_layout: str) -> None:
    """Lightroom Classic Catalog Automation Tool."""
    ctx.ensure_object(dict)
    catalog_path = Path(catalog)
    if catalog_path.suffix != ".lrcat":
        raise click.BadParameter(
            "File must have .lrcat extension", param_hint="--catalog"
        )
    ctx.obj["catalog_path"] = catalog_path
    ctx.obj["verbose"] = verbose
    ctx.obj["target_layout"] = target_layout


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Export results to file (JSON or CSV)",
)
@click.pass_context
def scan(ctx: click.Context, output: str | None) -> None:
    """Scan catalog for misplaced photos and duplicate filenames."""
    from .reporter import Reporter
    from .scanner import CatalogScanner

    catalog_path: Path = ctx.obj["catalog_path"]
    target_layout: str = ctx.obj["target_layout"]
    reporter = Reporter(console)

    try:
        with CatalogConnection(catalog_path) as cat:
            cat.validate_is_lrcat()
            conn = cat.open(readonly=True)

            schema_version = cat.get_schema_version()
            if schema_version:
                console.print(f"Catalog schema version: {schema_version}")

            scanner = CatalogScanner(conn, target_layout=target_layout)
            total = scanner.get_total_photo_count()
            misplaced = scanner.scan_misplaced_photos()
            duplicates = scanner.scan_duplicate_prefixes()

            reporter.print_scan_summary(total, misplaced, duplicates, target_layout)

            if output:
                output_path = Path(output)
                # Export scan results as a simple plan preview
                from .models import ChangePlan, ChangeType, FileChange

                plan = ChangePlan()
                for photo in misplaced:
                    plan.changes.append(
                        FileChange(
                            change_type=ChangeType.MOVE_PHOTO,
                            photo=photo,
                            source_folder_path=photo.current_folder_path,
                            target_folder_path=photo.get_expected_folder_path(
                                target_layout
                            ),
                        )
                    )
                for photo, cleaned in duplicates:
                    plan.changes.append(
                        FileChange(
                            change_type=ChangeType.RENAME_FILE,
                            photo=photo,
                            old_name=photo.base_name,
                            new_name=cleaned,
                        )
                    )
                if output_path.suffix == ".json":
                    reporter.export_plan_json(plan, output_path)
                elif output_path.suffix == ".csv":
                    reporter.export_plan_csv(plan, output_path)
                else:
                    console.print("[red]Output format must be .json or .csv[/red]")

    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e


@cli.command()
@click.option(
    "--fix",
    type=click.Choice(["moves", "renames", "all"]),
    default="all",
    help="Which fixes to plan",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Export plan to file (JSON or CSV)",
)
@click.pass_context
def plan(ctx: click.Context, fix: str, output: str | None) -> None:
    """Generate a change plan (read-only)."""
    from .planner import ChangePlanner
    from .reporter import Reporter
    from .scanner import CatalogScanner

    catalog_path: Path = ctx.obj["catalog_path"]
    target_layout: str = ctx.obj["target_layout"]
    reporter = Reporter(console)

    try:
        with CatalogConnection(catalog_path) as cat:
            cat.validate_is_lrcat()
            conn = cat.open(readonly=True)

            scanner = CatalogScanner(conn, target_layout=target_layout)
            planner = ChangePlanner(conn, scanner, target_layout=target_layout)

            change_plan = planner.build_plan(
                include_moves=(fix in ("moves", "all")),
                include_renames=(fix in ("renames", "all")),
            )

            reporter.print_change_plan(change_plan)

            if output:
                output_path = Path(output)
                if output_path.suffix == ".json":
                    reporter.export_plan_json(change_plan, output_path)
                elif output_path.suffix == ".csv":
                    reporter.export_plan_csv(change_plan, output_path)
                else:
                    console.print("[red]Output format must be .json or .csv[/red]")

    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e


@cli.command()
@click.option(
    "--fix",
    type=click.Choice(["moves", "renames", "all"]),
    default="all",
    help="Which fixes to apply",
)
@click.option("--no-backup", is_flag=True, help="Skip catalog backup (dangerous)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option(
    "--backup-dir",
    type=click.Path(),
    envvar="LRC_BACKUP_DIR",
    help="Directory for backup file",
)
@click.pass_context
def apply(
    ctx: click.Context, fix: str, no_backup: bool, yes: bool, backup_dir: str | None
) -> None:
    """Apply changes to catalog and disk. Requires Lightroom to be closed."""
    from .executor import ChangeExecutor
    from .planner import ChangePlanner
    from .reporter import Reporter
    from .scanner import CatalogScanner
    from .validators import CatalogValidator

    catalog_path: Path = ctx.obj["catalog_path"]
    target_layout: str = ctx.obj["target_layout"]
    reporter = Reporter(console)

    try:
        with CatalogConnection(catalog_path) as cat:
            cat.validate_is_lrcat()
            cat.check_lightroom_not_running()

            # Backup first
            if not no_backup:
                bdir = Path(backup_dir) if backup_dir else None
                backup_path = cat.backup(bdir)
                console.print(f"Backup created: [green]{backup_path}[/green]")

            conn = cat.open(readonly=True)

            # Build plan
            scanner = CatalogScanner(conn, target_layout=target_layout)
            planner = ChangePlanner(conn, scanner, target_layout=target_layout)
            change_plan = planner.build_plan(
                include_moves=(fix in ("moves", "all")),
                include_renames=(fix in ("renames", "all")),
            )

            if not change_plan.changes:
                console.print("[green]No changes needed.[/green]")
                return

            reporter.print_change_plan(change_plan)

            if not yes and not click.confirm("\nApply these changes?"):
                console.print("Aborted.")
                return

            # Close readonly and reopen for writing
            cat.close()

            # Pre-flight validation
            conn = cat.open(readonly=False)
            validator = CatalogValidator(conn)
            warnings = validator.preflight_check()
            for warning in warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")

            # Execute
            executor = ChangeExecutor(cat, change_plan)
            report = executor.execute()

            # Post-flight validation
            post_warnings = validator.postflight_check(change_plan)
            for warning in post_warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")

            reporter.print_execution_report(report)

    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e


@cli.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Run integrity checks on the catalog."""
    from .validators import CatalogValidator

    catalog_path: Path = ctx.obj["catalog_path"]

    try:
        with CatalogConnection(catalog_path) as cat:
            cat.validate_is_lrcat()
            conn = cat.open(readonly=True)
            validator = CatalogValidator(conn)

            console.print("[bold]Running catalog integrity checks...[/bold]")
            warnings = validator.preflight_check()

            if warnings:
                for w in warnings:
                    console.print(f"[yellow]Warning:[/yellow] {w}")
            else:
                console.print("[green]All checks passed.[/green]")

    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e


@cli.command()
@click.option(
    "--backup-path",
    type=click.Path(exists=True),
    required=True,
    help="Path to backup file to restore",
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def restore(ctx: click.Context, backup_path: str, yes: bool) -> None:
    """Restore catalog from a backup file."""
    import shutil

    catalog_path: Path = ctx.obj["catalog_path"]
    backup = Path(backup_path)

    if not yes and not click.confirm(
        f"Restore {catalog_path.name} from {backup.name}? "
        "This will overwrite the current catalog."
    ):
        console.print("Aborted.")
        return

    try:
        with CatalogConnection(catalog_path) as cat:
            cat.check_lightroom_not_running()

        shutil.copy2(backup, catalog_path)
        console.print(f"[green]Catalog restored from {backup.name}[/green]")

    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e


def main() -> None:
    cli()
