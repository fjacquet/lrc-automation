"""Tests for models module - PhotoRecord location path methods."""

from datetime import datetime

from lrc_automation.constants import LocationOrder
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


class TestPhotoRecordLocationOrders:
    """Tests for get_expected_folder_path_with_location with all LocationOrder."""

    def test_cc_city_month_order(self) -> None:
        photo = _make_photo(datetime(2023, 6, 15, 14, 30))
        result = photo.get_expected_folder_path_with_location(
            "%Y/%m/", "CH", "Zurich", LocationOrder.CC_CITY_MONTH
        )
        assert result == "2023/CH/Zurich/06/"

    def test_cc_month_city_order(self) -> None:
        photo = _make_photo(datetime(2023, 6, 15, 14, 30))
        result = photo.get_expected_folder_path_with_location(
            "%Y/%m/", "CH", "Zurich", LocationOrder.CC_MONTH_CITY
        )
        assert result == "2023/CH/06/Zurich/"

    def test_month_cc_city_order_explicit(self) -> None:
        """MONTH_CC_CITY matches the default behaviour."""
        photo = _make_photo(datetime(2023, 6, 15, 14, 30))
        result = photo.get_expected_folder_path_with_location(
            "%Y/%m/", "CH", "Zurich", LocationOrder.MONTH_CC_CITY
        )
        assert result == "2023/06/CH/Zurich/"

    def test_cc_city_month_no_capture_time(self) -> None:
        photo = _make_photo(capture_time=None)
        result = photo.get_expected_folder_path_with_location(
            "%Y/%m/", "CH", "Zurich", LocationOrder.CC_CITY_MONTH
        )
        assert result is None

    def test_cc_city_month_no_country(self) -> None:
        """Falls back to date-only when country is missing."""
        photo = _make_photo(datetime(2023, 6, 15))
        result = photo.get_expected_folder_path_with_location(
            "%Y/%m/", None, "Zurich", LocationOrder.CC_CITY_MONTH
        )
        assert result == "2023/06/"

    def test_all_orders_end_with_slash(self) -> None:
        photo = _make_photo(datetime(2023, 6, 15))
        for order in LocationOrder:
            result = photo.get_expected_folder_path_with_location(
                "%Y/%m/", "FR", "Paris", order
            )
            assert result is not None
            assert result.endswith("/")


class TestFileChangeCrossRoot:
    """FileChange cross-root fields default to None and can be set."""

    def _make_photo(
        self, root_folder_id: int = 1, current_folder_path: str = "2023/07/"
    ) -> PhotoRecord:
        return PhotoRecord(
            image_id=1,
            file_id=1,
            folder_id=1,
            root_folder_id=root_folder_id,
            base_name="IMG_0001",
            extension="JPG",
            sidecar_extensions=None,
            capture_time=None,
            current_folder_path=current_folder_path,
            root_absolute_path="/photos/",
        )

    def test_defaults_to_none(self) -> None:
        """New FileChange has target_root_id and target_root_absolute_path as None."""
        from lrc_automation.models import ChangeType, FileChange

        change = FileChange(change_type=ChangeType.MOVE_PHOTO, photo=self._make_photo())
        assert change.target_root_id is None
        assert change.target_root_absolute_path is None

    def test_cross_root_fields_set(self) -> None:
        """Cross-root fields can be set and are preserved."""
        from lrc_automation.models import ChangeType, FileChange

        change = FileChange(
            change_type=ChangeType.MOVE_PHOTO,
            photo=self._make_photo(root_folder_id=2, current_folder_path="2012/08/"),
            target_root_id=1,
            target_root_absolute_path="/lr/2012/",
        )
        assert change.target_root_id == 1
        assert change.target_root_absolute_path == "/lr/2012/"
