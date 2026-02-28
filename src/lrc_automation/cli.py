"""Lightroom Classic Catalog Automation CLI."""

import logging
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
@click.option(
    "--location-folders",
    is_flag=True,
    default=False,
    envvar="LRC_LOCATION_FOLDERS",
    help="Append Country/City subfolders via GPS (requires lrc-automation[geo])",
)
@click.option(
    "--log-file",
    type=click.Path(),
    envvar="LRC_LOG_FILE",
    default=None,
    help="Log file path (default: <catalog>.log alongside the catalog)",
)
@click.pass_context
def cli(
    ctx: click.Context,
    catalog: str,
    verbose: bool,
    target_layout: str,
    location_folders: bool,
    log_file: str | None,
) -> None:
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
    ctx.obj["location_folders"] = location_folders

    from .log import configure_logging

    log_path = Path(log_file) if log_file else catalog_path.with_suffix(".log")
    configure_logging(log_path, verbose)
    logging.getLogger(__name__).info("lrc-auto started: catalog=%s", catalog_path)


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
    location_folders: bool = ctx.obj["location_folders"]
    reporter = Reporter(console)

    try:
        with CatalogConnection(catalog_path) as cat:
            cat.validate_is_lrcat()
            conn = cat.open(readonly=True)

            schema_version = cat.get_schema_version()
            if schema_version:
                console.print(f"Catalog schema version: {schema_version}")

            scanner = CatalogScanner(
                conn,
                target_layout=target_layout,
                location_folders=location_folders,
            )
            total = scanner.get_total_photo_count()
            misplaced = scanner.scan_misplaced_photos()
            duplicates = scanner.scan_duplicate_prefixes()
            resolver = None
            if location_folders:
                from .geocoder import LocationResolver

                resolver = LocationResolver()
            prefix_conversions = scanner.scan_prefix_format(resolver)
            needs_location = len(scanner.scan_needs_location_folder())
            year_in_year = len(scanner.scan_year_in_year_photos())

            reporter.print_scan_summary(
                total,
                misplaced,
                duplicates,
                target_layout,
                location_folders,
                needs_location=needs_location,
                year_in_year=year_in_year,
            )
            reporter.print_prefix_format_summary(prefix_conversions)

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
    location_folders: bool = ctx.obj["location_folders"]
    reporter = Reporter(console)

    try:
        with CatalogConnection(catalog_path) as cat:
            cat.validate_is_lrcat()
            conn = cat.open(readonly=True)

            scanner = CatalogScanner(
                conn,
                target_layout=target_layout,
                location_folders=location_folders,
            )
            planner = ChangePlanner(
                conn,
                scanner,
                target_layout=target_layout,
                location_folders=location_folders,
            )

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
    from .models import ChangeType
    from .planner import ChangePlanner
    from .reporter import Reporter
    from .scanner import CatalogScanner
    from .validators import CatalogValidator

    catalog_path: Path = ctx.obj["catalog_path"]
    target_layout: str = ctx.obj["target_layout"]
    location_folders: bool = ctx.obj["location_folders"]
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
            scanner = CatalogScanner(
                conn,
                target_layout=target_layout,
                location_folders=location_folders,
            )
            planner = ChangePlanner(
                conn,
                scanner,
                target_layout=target_layout,
                location_folders=location_folders,
            )
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

            # Plan source-file check: surface all missing files before touching anything
            missing_sources = validator.preflight_plan_check(change_plan)
            if missing_sources:
                n = len(missing_sources)
                console.print(
                    f"\n[yellow]Warning:[/yellow] {n} source file(s) "
                    "not found on disk and will be skipped:"
                )
                for path in missing_sources[:20]:
                    console.print(f"  [dim]missing:[/dim] {path}")
                if len(missing_sources) > 20:
                    console.print(f"  ... and {len(missing_sources) - 20} more")
                if not yes and not click.confirm(
                    "\nProceed anyway (skipping missing files)?"
                ):
                    console.print("Aborted.")
                    return

            # Execute with progress bar
            from rich.progress import (
                BarColumn,
                MofNCompleteColumn,
                Progress,
                SpinnerColumn,
                TaskProgressColumn,
                TextColumn,
                TimeElapsedColumn,
            )

            from .models import FileChange as _FileChange

            total = len(change_plan.changes)
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
                transient=True,
            ) as progress:
                task_id = progress.add_task("Applying…", total=total)

                def _on_progress(change: _FileChange, ok: bool) -> None:
                    label = change.photo.base_name
                    status = "" if ok else " [yellow](skipped)[/yellow]"
                    progress.update(
                        task_id,
                        advance=1,
                        description=f"{label}{status}",
                    )

                executor = ChangeExecutor(cat, change_plan, on_progress=_on_progress)
                report = executor.execute()

            # Post-flight validation (skip disk checks if rolled back)
            post_warnings = validator.postflight_check(
                [] if report.rolled_back else report.succeeded
            )
            for warning in post_warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")

            reporter.print_execution_report(report)
            logging.getLogger(__name__).info(
                "apply: succeeded=%d failed=%d removed=%d rolled_back=%s",
                len(report.succeeded),
                len(report.failed),
                report.folders_removed,
                report.rolled_back,
            )

            if any(c.change_type == ChangeType.RENAME_FILE for c in report.succeeded):
                console.print(
                    "\n[bold yellow]Next step:[/bold yellow] Open Lightroom Classic, "
                    "select all renamed photos, then use "
                    "[bold]Metadata \u2192 Save Metadata to Files[/bold] "
                    "to regenerate .xmp sidecars."
                )

    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Export disk audit to file (JSON or CSV)",
)
@click.pass_context
def validate(ctx: click.Context, output: str | None) -> None:
    """Run integrity checks and full disk audit on the catalog."""
    from .reporter import Reporter
    from .validators import CatalogValidator

    catalog_path: Path = ctx.obj["catalog_path"]
    reporter = Reporter(console)
    log = logging.getLogger(__name__)

    try:
        with CatalogConnection(catalog_path) as cat:
            cat.validate_is_lrcat()
            conn = cat.open(readonly=True)
            validator = CatalogValidator(conn)

            console.print("[bold]Running catalog integrity checks...[/bold]")
            log.info("validate: starting integrity checks on %s", catalog_path)
            warnings = validator.preflight_check()
            warnings += validator.check_year_in_year()
            if warnings:
                for w in warnings:
                    console.print(f"[yellow]Warning:[/yellow] {w}")
                    log.warning("integrity: %s", w)

            # Full disk audit with parent-folder search for missing files
            result = validator.audit_files_on_disk()
            reporter.print_audit_result(result)
            log.info(
                "validate: checked=%d missing=%d found_elsewhere=%d truly_missing=%d",
                result.total_checked,
                len(result.missing),
                result.found_elsewhere_count,
                result.truly_missing_count,
            )

            if output:
                output_path = Path(output)
                if output_path.suffix == ".json":
                    reporter.export_audit_json(result, output_path)
                elif output_path.suffix == ".csv":
                    reporter.export_audit_csv(result, output_path)
                else:
                    console.print("[red]Output format must be .json or .csv[/red]")

            if not warnings and not result.missing:
                console.print("[green]All checks passed.[/green]")

    except CatalogError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e


@cli.command()
@click.pass_context
def reconcile(ctx: click.Context) -> None:
    """Fix catalog pointers for files found at a different disk location.

    Runs a full disk audit, then for each file that exists on disk but is
    registered at the wrong catalog path, updates AgLibraryFile.folder to
    match where the file actually lives.  No files are moved on disk.

    Ambiguous matches (same filename in multiple locations) are skipped and
    reported for manual resolution.
    """
    from .reconciler import CatalogReconciler
    from .reporter import Reporter

    catalog_path: Path = ctx.obj["catalog_path"]
    reporter = Reporter(console)
    log = logging.getLogger(__name__)

    try:
        with CatalogConnection(catalog_path) as cat:
            cat.validate_is_lrcat()
            cat.check_lightroom_not_running()
            cat.backup()

            conn = cat.open(readonly=False)
            reconciler = CatalogReconciler(conn)
            log.info("reconcile: starting on %s", catalog_path)

            console.print("[bold]Running catalog reconciliation...[/bold]")
            conn.execute("BEGIN IMMEDIATE")
            report = reconciler.reconcile()
            conn.commit()

            reporter.print_reconcile_report(report)
            log.info(
                "reconcile: reconciled=%d skipped=%d truly_missing=%d",
                len(report.reconciled),
                len(report.skipped_ambiguous),
                len(report.truly_missing),
            )

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
