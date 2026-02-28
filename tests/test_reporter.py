"""Tests for Reporter output, focused on correctness of computed paths."""

from __future__ import annotations

from datetime import datetime

from rich.console import Console

from lrc_automation.constants import LocationOrder
from lrc_automation.models import PhotoRecord
from lrc_automation.reporter import Reporter


def _make_photo(
    *,
    file_id: int = 1,
    base_name: str = "IMG_001",
    extension: str = "JPG",
    folder_id: int = 1,
    root_folder_id: int = 1,
    current_folder_path: str = "2012/06/",
    root_absolute_path: str = "/photos/",
    capture_time: datetime | None = None,
    gps_latitude: float | None = None,
    gps_longitude: float | None = None,
) -> PhotoRecord:
    return PhotoRecord(
        image_id=file_id,
        file_id=file_id,
        folder_id=folder_id,
        root_folder_id=root_folder_id,
        base_name=base_name,
        extension=extension,
        sidecar_extensions=None,
        capture_time=capture_time,
        current_folder_path=current_folder_path,
        root_absolute_path=root_absolute_path,
        gps_latitude=gps_latitude,
        gps_longitude=gps_longitude,
    )


class TestPrintPrefixFormatSummary:
    """Reporter.print_prefix_format_summary() target folder must not double CC/City."""

    def test_no_location_uses_current_folder(self) -> None:
        """Without GPS location, Target Folder shows current_folder_path."""
        photo = _make_photo(
            current_folder_path="2012/06/",
            capture_time=datetime(2012, 6, 15),
        )
        reporter = Reporter(console=Console(width=200, highlight=False, record=True))
        reporter.print_prefix_format_summary(
            [(photo, "120615-IMG_001", None)],
            target_layout="%Y/%m/",
        )
        output = reporter.console.export_text()
        assert "2012/06/" in output

    def test_with_location_no_doubling_month_cc_city(self) -> None:
        """Photo in 06/CH/Aubonne/: target must be 2012/06/CH/Aubonne/, not doubled."""
        photo = _make_photo(
            current_folder_path="2012/06/CH/Aubonne/",
            capture_time=datetime(2012, 6, 15),
            gps_latitude=46.5,
            gps_longitude=6.3,
        )
        reporter = Reporter(console=Console(width=300, highlight=False, record=True))
        reporter.print_prefix_format_summary(
            [(photo, "120615-IMG_001", ("CH", "Aubonne"))],
            target_layout="%Y/%m/",
            location_order=LocationOrder.MONTH_CC_CITY,
        )
        output = reporter.console.export_text()
        # Must NOT produce the doubled path
        assert "CH/Aubonne/CH/Aubonne" not in output
        # Must show the correct path
        assert "2012/06/CH/Aubonne/" in output

    def test_with_location_cc_city_month_order(self) -> None:
        """CC_CITY_MONTH order: target is YYYY/CC/City/MM/ (no doubling)."""
        photo = _make_photo(
            current_folder_path="2012/CH/Aubonne/06/",
            capture_time=datetime(2012, 6, 15),
            gps_latitude=46.5,
            gps_longitude=6.3,
        )
        reporter = Reporter(console=Console(width=300, highlight=False, record=True))
        reporter.print_prefix_format_summary(
            [(photo, "120615-IMG_001", ("CH", "Aubonne"))],
            target_layout="%Y/%m/",
            location_order=LocationOrder.CC_CITY_MONTH,
        )
        output = reporter.console.export_text()
        assert "2012/CH/Aubonne/06/" in output
        assert "CH/Aubonne/CH/Aubonne" not in output

    def test_no_output_for_empty_conversions(self) -> None:
        """Empty conversions list produces no output."""
        reporter = Reporter(console=Console(width=200, highlight=False, record=True))
        reporter.print_prefix_format_summary([], target_layout="%Y/%m/")
        output = reporter.console.export_text()
        assert output.strip() == ""
