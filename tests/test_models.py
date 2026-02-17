"""Tests for models module - PhotoRecord location path methods."""

from datetime import datetime

from lrc_automation.models import PhotoRecord


def _make_photo(
    capture_time: datetime | None = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
) -> PhotoRecord:
    """Helper to create a PhotoRecord with optional GPS."""
    return PhotoRecord(
        image_id=1,
        file_id=1,
        folder_id=1,
        root_folder_id=1,
        base_name="IMG_0001",
        extension="JPG",
        sidecar_extensions=None,
        capture_time=capture_time,
        current_folder_path="2023/07/",
        root_absolute_path="/photos/",
        gps_latitude=gps_lat,
        gps_longitude=gps_lon,
    )


class TestPhotoRecordLocationPath:
    def test_get_expected_folder_path_with_location(self) -> None:
        photo = _make_photo(datetime(2023, 6, 15, 14, 30))
        result = photo.get_expected_folder_path_with_location("%Y/%m/", "CH", "Zurich")
        assert result == "2023/06/CH/Zurich/"

    def test_location_path_no_gps(self) -> None:
        """Without country/city, falls back to date-only path."""
        photo = _make_photo(datetime(2023, 6, 15, 14, 30))
        result = photo.get_expected_folder_path_with_location("%Y/%m/", None, None)
        assert result == "2023/06/"

    def test_location_path_no_capture_time(self) -> None:
        """Without capture time, returns None."""
        photo = _make_photo(capture_time=None)
        result = photo.get_expected_folder_path_with_location("%Y/%m/", "CH", "Zurich")
        assert result is None

    def test_location_path_custom_layout(self) -> None:
        photo = _make_photo(datetime(2023, 6, 15, 14, 30))
        result = photo.get_expected_folder_path_with_location(
            "%Y/%m/%d/", "CH", "Zurich"
        )
        assert result == "2023/06/15/CH/Zurich/"

    def test_location_path_trailing_slash(self) -> None:
        photo = _make_photo(datetime(2023, 6, 15))
        result = photo.get_expected_folder_path_with_location(
            "%Y/%m/", "NZ", "Invercargill"
        )
        assert result is not None
        assert result.endswith("/")

    def test_location_path_only_country_no_city(self) -> None:
        """With only country (no city), falls back to date-only path."""
        photo = _make_photo(datetime(2023, 6, 15))
        result = photo.get_expected_folder_path_with_location("%Y/%m/", "CH", None)
        assert result == "2023/06/"

    def test_location_path_only_city_no_country(self) -> None:
        """With only city (no country), falls back to date-only path."""
        photo = _make_photo(datetime(2023, 6, 15))
        result = photo.get_expected_folder_path_with_location("%Y/%m/", None, "Zurich")
        assert result == "2023/06/"

    def test_gps_fields_default_none(self) -> None:
        photo = _make_photo(datetime(2023, 6, 15))
        assert photo.gps_latitude is None
        assert photo.gps_longitude is None

    def test_gps_fields_set(self) -> None:
        photo = _make_photo(datetime(2023, 6, 15), gps_lat=47.37, gps_lon=8.54)
        assert photo.gps_latitude == 47.37
        assert photo.gps_longitude == 8.54
