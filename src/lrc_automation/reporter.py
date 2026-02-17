"""Reporter - terminal output, CSV/JSON export."""

import csv
import json
from io import StringIO
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .models import ChangePlan, ChangeType, ExecutionReport, FileChange, PhotoRecord


class Reporter:
    """Formats and outputs scan results and change plans."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def print_scan_summary(
        self,
        total_photos: int,
        misplaced: list[PhotoRecord],
        duplicates: list[tuple[PhotoRecord, str]],
        target_layout: str = "%Y/%m/",
        location_folders: bool = False,
    ) -> None:
        """Print a summary of scan results."""
        self.console.print("\n[bold]Catalog Scan Results[/bold]")
        self.console.print(f"Total photos: {total_photos}")
        self.console.print(f"Target layout: {target_layout}")
        if location_folders:
            self.console.print("Location folders: [green]enabled[/green]")
            gps_count = sum(1 for p in misplaced if p.gps_latitude is not None)
            self.console.print(f"Misplaced photos with GPS: [cyan]{gps_count}[/cyan]")
        self.console.print(f"Misplaced photos: [yellow]{len(misplaced)}[/yellow]")
        self.console.print(f"Duplicate prefixes: [yellow]{len(duplicates)}[/yellow]")

        if misplaced:
            self.console.print(
                f"\n[bold]Misplaced Photos[/bold] (wrong {target_layout} folder)"
            )
            table = Table(show_lines=False)
            table.add_column("#", style="dim", width=6)
            table.add_column("File")
            table.add_column("Current Folder")
            table.add_column("Expected Folder")
            table.add_column("Capture Date")
            if location_folders:
                table.add_column("GPS")

            for i, photo in enumerate(misplaced[:50], 1):
                expected = photo.get_expected_folder_path(target_layout) or "?"
                capture = (
                    photo.capture_time.strftime("%Y-%m-%d %H:%M")
                    if photo.capture_time
                    else "?"
                )
                row = [
                    str(i),
                    f"{photo.base_name}.{photo.extension}",
                    photo.current_folder_path,
                    expected,
                    capture,
                ]
                if location_folders:
                    if photo.gps_latitude is not None:
                        row.append(
                            f"{photo.gps_latitude:.2f}, {photo.gps_longitude:.2f}"
                            if photo.gps_longitude is not None
                            else "?"
                        )
                    else:
                        row.append("-")
                table.add_row(*row)

            self.console.print(table)
            if len(misplaced) > 50:
                self.console.print(
                    f"  ... and {len(misplaced) - 50} more. Use --output to export all."
                )

        if duplicates:
            self.console.print("\n[bold]Duplicate Prefixes[/bold]")
            table = Table(show_lines=False)
            table.add_column("#", style="dim", width=6)
            table.add_column("Current Name")
            table.add_column("Cleaned Name")
            table.add_column("Folder")

            for i, (photo, cleaned) in enumerate(duplicates[:50], 1):
                table.add_row(
                    str(i),
                    photo.base_name,
                    cleaned,
                    photo.current_folder_path,
                )

            self.console.print(table)
            if len(duplicates) > 50:
                self.console.print(
                    f"  ... and {len(duplicates) - 50} more. "
                    "Use --output to export all."
                )

    def print_change_plan(self, plan: ChangePlan) -> None:
        """Print a change plan as a Rich table."""
        self.console.print("\n[bold]Change Plan[/bold]")
        self.console.print(f"Moves: {plan.move_count}")
        self.console.print(f"Renames: {plan.rename_count}")
        self.console.print(f"Folders to create: {len(plan.folders_to_create)}")

        if plan.folders_to_create:
            self.console.print("\n[bold]New Folders[/bold]")
            for root_id, path in plan.folders_to_create:
                self.console.print(f"  [green]+[/green] {path} (root: {root_id})")

        if plan.changes:
            table = Table(show_lines=False)
            table.add_column("#", style="dim", width=6)
            table.add_column("Type")
            table.add_column("File")
            table.add_column("From")
            table.add_column("To")

            for i, change in enumerate(plan.changes[:100], 1):
                if change.change_type == ChangeType.MOVE_PHOTO:
                    table.add_row(
                        str(i),
                        "[cyan]MOVE[/cyan]",
                        f"{change.photo.base_name}.{change.photo.extension}",
                        change.source_folder_path or "",
                        change.target_folder_path or "",
                    )
                else:
                    table.add_row(
                        str(i),
                        "[magenta]RENAME[/magenta]",
                        f"{change.old_name}.{change.photo.extension}",
                        change.old_name or "",
                        change.new_name or "",
                    )

            self.console.print(table)
            if len(plan.changes) > 100:
                self.console.print(f"  ... and {len(plan.changes) - 100} more.")

    def print_execution_report(self, report: ExecutionReport) -> None:
        """Print execution results."""
        self.console.print("\n[bold]Execution Report[/bold]")
        self.console.print(f"Succeeded: [green]{len(report.succeeded)}[/green]")
        self.console.print(f"Failed: [red]{len(report.failed)}[/red]")

        if report.failed:
            self.console.print("\n[bold red]Failures:[/bold red]")
            for change, error in report.failed:
                self.console.print(
                    f"  [red]x[/red] {change.photo.base_name}"
                    f".{change.photo.extension}: {error}"
                )

    def export_plan_json(self, plan: ChangePlan, output_path: Path) -> None:
        """Export change plan to JSON."""
        data = {
            "folders_to_create": [
                {"root_folder_id": rid, "path_from_root": path}
                for rid, path in plan.folders_to_create
            ],
            "changes": [self._change_to_dict(c) for c in plan.changes],
        }
        output_path.write_text(json.dumps(data, indent=2, default=str))
        self.console.print(f"Plan exported to [bold]{output_path}[/bold]")

    def export_plan_csv(self, plan: ChangePlan, output_path: Path) -> None:
        """Export change plan to CSV."""
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["type", "file", "extension", "from", "to", "folder"])
        for change in plan.changes:
            if change.change_type == ChangeType.MOVE_PHOTO:
                writer.writerow(
                    [
                        "MOVE",
                        f"{change.photo.base_name}.{change.photo.extension}",
                        change.photo.extension,
                        change.source_folder_path,
                        change.target_folder_path,
                        change.photo.current_folder_path,
                    ]
                )
            else:
                writer.writerow(
                    [
                        "RENAME",
                        f"{change.old_name}.{change.photo.extension}",
                        change.photo.extension,
                        change.old_name,
                        change.new_name,
                        change.photo.current_folder_path,
                    ]
                )
        output_path.write_text(output.getvalue())
        self.console.print(f"Plan exported to [bold]{output_path}[/bold]")

    @staticmethod
    def _change_to_dict(change: FileChange) -> dict[str, object]:
        result: dict[str, object] = {
            "type": change.change_type.value,
            "file_id": change.photo.file_id,
            "base_name": change.photo.base_name,
            "extension": change.photo.extension,
            "current_folder": change.photo.current_folder_path,
        }
        if change.change_type == ChangeType.MOVE_PHOTO:
            result["source_folder"] = change.source_folder_path
            result["target_folder"] = change.target_folder_path
        else:
            result["old_name"] = change.old_name
            result["new_name"] = change.new_name
        return result
