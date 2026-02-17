"""Tests for utils module."""

from datetime import datetime

from lrc_automation.utils import (
    clean_duplicate_prefix,
    extract_yyyy_mm,
    parse_capture_time,
    parse_sidecar_extensions,
)


class TestParseCaptureTime:
    def test_iso_format(self) -> None:
        result = parse_capture_time("2023-06-15T14:30:00")
        assert result == datetime(2023, 6, 15, 14, 30, 0)

    def test_iso_with_timezone(self) -> None:
        result = parse_capture_time("2023-06-15T14:30:00+02:00")
        assert result is not None
        assert result.year == 2023
        assert result.month == 6

    def test_exif_format(self) -> None:
        result = parse_capture_time("2023:06:15 14:30:00")
        assert result == datetime(2023, 6, 15, 14, 30, 0)

    def test_none_input(self) -> None:
        assert parse_capture_time(None) is None

    def test_empty_string(self) -> None:
        assert parse_capture_time("") is None

    def test_invalid_format(self) -> None:
        assert parse_capture_time("not-a-date") is None


class TestExtractYyyyMm:
    def test_simple_path(self) -> None:
        assert extract_yyyy_mm("2023/06/") == (2023, 6)

    def test_nested_path(self) -> None:
        assert extract_yyyy_mm("2023/06/subfolder/") == (2023, 6)

    def test_invalid_path(self) -> None:
        assert extract_yyyy_mm("photos/vacation/") is None

    def test_single_component(self) -> None:
        assert extract_yyyy_mm("2023/") is None

    def test_invalid_month(self) -> None:
        assert extract_yyyy_mm("2023/13/") is None


class TestCleanDuplicatePrefix:
    def test_basic_duplicate(self) -> None:
        result = clean_duplicate_prefix("29122012-29122012-IMG_20121229_131334")
        assert result == "29122012-IMG_131334"

    def test_no_duplicate(self) -> None:
        result = clean_duplicate_prefix("IMG_20121229_131334")
        assert result is None

    def test_different_prefixes(self) -> None:
        result = clean_duplicate_prefix("29122012-01012013-IMG_131334")
        assert result is None

    def test_duplicate_without_img_date(self) -> None:
        result = clean_duplicate_prefix("12345678-12345678-PHOTO_001")
        assert result == "12345678-PHOTO_001"


class TestParseSidecarExtensions:
    def test_multiple(self) -> None:
        assert parse_sidecar_extensions("JPG,xmp") == ["JPG", "xmp"]

    def test_single(self) -> None:
        assert parse_sidecar_extensions("xmp") == ["xmp"]

    def test_none(self) -> None:
        assert parse_sidecar_extensions(None) == []

    def test_empty(self) -> None:
        assert parse_sidecar_extensions("") == []
