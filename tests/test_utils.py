"""Tests for utils module."""

from datetime import datetime

from lrc_automation.constants import layout_to_regex
from lrc_automation.models import PhotoRecord
from lrc_automation.utils import (
    clean_duplicate_prefix,
    extract_date_from_path,
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

    def test_custom_layout_day(self) -> None:
        assert extract_yyyy_mm("2023/06/15/", layout="%Y/%m/%d/") == (2023, 6)

    def test_custom_layout_dash(self) -> None:
        assert extract_yyyy_mm("2023-06/", layout="%Y-%m/") == (2023, 6)

    def test_custom_layout_no_match(self) -> None:
        assert extract_yyyy_mm("photos/vacation/", layout="%Y/%m/%d/") is None


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


class TestLayoutToRegex:
    def test_default_layout(self) -> None:
        pattern = layout_to_regex("%Y/%m/")
        assert pattern.match("2023/06/")
        assert not pattern.match("photos/06/")

    def test_day_layout(self) -> None:
        pattern = layout_to_regex("%Y/%m/%d/")
        assert pattern.match("2023/06/15/")
        assert not pattern.match("2023/06/")

    def test_dash_layout(self) -> None:
        pattern = layout_to_regex("%Y-%m/")
        assert pattern.match("2023-06/")
        assert not pattern.match("2023/06/")


class TestGetExpectedFolderPath:
    def _make_photo(self, capture_time: datetime | None) -> PhotoRecord:
        return PhotoRecord(
            image_id=1,
            file_id=1,
            folder_id=1,
            root_folder_id=1,
            base_name="test",
            extension="jpg",
            sidecar_extensions=None,
            capture_time=capture_time,
            current_folder_path="2023/06/",
            root_absolute_path="/tmp/",
        )

    def test_default_layout(self) -> None:
        photo = self._make_photo(datetime(2023, 6, 15, 14, 30))
        assert photo.get_expected_folder_path("%Y/%m/") == "2023/06/"

    def test_day_layout(self) -> None:
        photo = self._make_photo(datetime(2023, 6, 15, 14, 30))
        assert photo.get_expected_folder_path("%Y/%m/%d/") == "2023/06/15/"

    def test_flat_year_layout(self) -> None:
        photo = self._make_photo(datetime(2023, 6, 15, 14, 30))
        assert photo.get_expected_folder_path("%Y/") == "2023/"

    def test_none_capture_time(self) -> None:
        photo = self._make_photo(None)
        assert photo.get_expected_folder_path("%Y/%m/") is None

    def test_trailing_slash_ensured(self) -> None:
        photo = self._make_photo(datetime(2023, 6, 15, 14, 30))
        result = photo.get_expected_folder_path("%Y/%m")
        assert result is not None
        assert result.endswith("/")

    def test_property_backward_compat(self) -> None:
        photo = self._make_photo(datetime(2023, 6, 15, 14, 30))
        assert photo.expected_folder_path == "2023/06/"


class TestExtractDateFromPath:
    def test_standard_yyyy_mm(self) -> None:
        assert extract_date_from_path("/photos/2023/06/") == (2023, 6)

    def test_standard_yyyy_mm_nested(self) -> None:
        assert extract_date_from_path("/photos/2023/06/subfolder/") == (2023, 6)

    def test_iso_date_folder(self) -> None:
        assert extract_date_from_path("/photos/2023-12-24/") == (2023, 12)

    def test_iso_date_ignores_day(self) -> None:
        assert extract_date_from_path("/photos/2023-06-01/") == (2023, 6)

    def test_french_date_avril(self) -> None:
        assert extract_date_from_path("/photos/1 avril 2016/") == (2016, 4)

    def test_french_date_decembre_accent(self) -> None:
        assert extract_date_from_path("/photos/25 décembre 2020/") == (2020, 12)

    def test_french_date_fevrier_no_accent(self) -> None:
        assert extract_date_from_path("/photos/14 fevrier 2019/") == (2019, 2)

    def test_french_date_case_insensitive(self) -> None:
        assert extract_date_from_path("/photos/1 AVRIL 2016/") == (2016, 4)

    def test_year_in_root_month_in_path(self) -> None:
        assert extract_date_from_path("/photos/2021/06/") == (2021, 6)

    def test_year_in_root_topical_subfolder(self) -> None:
        assert extract_date_from_path("/photos/2021/Vacances/") is None

    def test_topical_folder_returns_none(self) -> None:
        assert extract_date_from_path("/photos/Vacances/Summer/") is None

    def test_empty_path_returns_none(self) -> None:
        assert extract_date_from_path("") is None

    def test_1904_epoch_filtered_iso(self) -> None:
        assert extract_date_from_path("/photos/1904-01-01/") is None

    def test_1904_epoch_filtered_yyyy_mm(self) -> None:
        assert extract_date_from_path("/photos/1904/01/") is None

    def test_invalid_month_13(self) -> None:
        assert extract_date_from_path("/photos/2023-13-01/") is None

    def test_deeper_iso_wins_over_shallower_year(self) -> None:
        # Right-to-left: deeper 2023-12-24 is found before shallower 2020
        assert extract_date_from_path("/photos/2020/2023-12-24/") == (2023, 12)

    def test_real_catalog_root_with_date(self) -> None:
        # Simulates root=/Volumes/photo/2021/ pathFromRoot=06/
        assert extract_date_from_path("/Volumes/photo/2021/06/") == (2021, 6)

    def test_french_date_aout_accent(self) -> None:
        assert extract_date_from_path("/photos/15 août 2018/") == (2018, 8)


class TestParseSidecarExtensions:
    def test_multiple(self) -> None:
        assert parse_sidecar_extensions("JPG,xmp") == ["JPG", "xmp"]

    def test_single(self) -> None:
        assert parse_sidecar_extensions("xmp") == ["xmp"]

    def test_none(self) -> None:
        assert parse_sidecar_extensions(None) == []

    def test_empty(self) -> None:
        assert parse_sidecar_extensions("") == []
