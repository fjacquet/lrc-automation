"""Tests for geocoder module."""

import pytest

from lrc_automation.geocoder import LocationResolver, _sanitize_folder_name


class TestSanitizeFolderName:
    def test_strips_unsafe_characters(self) -> None:
        assert _sanitize_folder_name('New/York:City*"test') == "NewYorkCitytest"

    def test_strips_angle_brackets_and_pipe(self) -> None:
        assert _sanitize_folder_name("City<>|Name") == "CityName"

    def test_preserves_spaces(self) -> None:
        assert _sanitize_folder_name("New York") == "New York"

    def test_collapses_multiple_spaces(self) -> None:
        assert _sanitize_folder_name("New   York") == "New York"

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert _sanitize_folder_name("  Zurich  ") == "Zurich"

    def test_handles_unicode(self) -> None:
        result = _sanitize_folder_name("Zürich")
        assert result == "Zürich"

    def test_handles_accented_chars(self) -> None:
        result = _sanitize_folder_name("São Paulo")
        assert result == "São Paulo"

    def test_empty_string(self) -> None:
        assert _sanitize_folder_name("") == ""


class TestLocationResolver:
    def test_resolve_known_coordinates(self) -> None:
        """Zurich coords should return a valid country/city pair."""
        resolver = LocationResolver()
        result = resolver.resolve(47.3769, 8.5417)
        assert result is not None
        country, city = result
        assert country == "CH"
        assert isinstance(city, str)
        assert len(city) > 0

    def test_resolve_returns_tuple(self) -> None:
        """Paris coords should return a valid result."""
        resolver = LocationResolver()
        result = resolver.resolve(48.8566, 2.3522)
        assert result is not None
        country, _city = result
        assert country == "FR"

    def test_resolve_batch(self) -> None:
        resolver = LocationResolver()
        coords = [(47.3769, 8.5417), (48.8566, 2.3522)]
        results = resolver.resolve_batch(coords)
        assert len(results) == 2
        assert (47.3769, 8.5417) in results
        assert (48.8566, 2.3522) in results

    def test_resolve_batch_empty(self) -> None:
        resolver = LocationResolver()
        results = resolver.resolve_batch([])
        assert results == {}

    def test_resolve_caches_results(self) -> None:
        """Same coords twice should use cache."""
        resolver = LocationResolver()
        result1 = resolver.resolve(47.3769, 8.5417)
        # Second call should hit cache
        result2 = resolver.resolve(47.3769, 8.5417)
        assert result1 == result2
        assert (47.3769, 8.5417) in resolver._cache

    def test_batch_uses_cache(self) -> None:
        """Batch resolve should use cache for already-resolved coords."""
        resolver = LocationResolver()
        # Pre-populate cache
        resolver.resolve(47.3769, 8.5417)
        # Now batch with one cached and one new
        results = resolver.resolve_batch([(47.3769, 8.5417), (48.8566, 2.3522)])
        assert len(results) == 2

    def test_import_error_when_not_installed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raise ImportError with helpful message when not installed."""
        resolver = LocationResolver()
        resolver._rg = None  # Reset state

        def fake_import(name: str, *args: object, **kwargs: object) -> None:
            if name == "reverse_geocoder":
                raise ImportError("No module named 'reverse_geocoder'")

        monkeypatch.setattr("builtins.__import__", fake_import)
        monkeypatch.delitem("sys.modules", "reverse_geocoder", raising=False)

        with pytest.raises(ImportError, match="pip install lrc-automation"):
            resolver.resolve(47.3769, 8.5417)

    def test_resolve_southern_hemisphere(self) -> None:
        """New Zealand coords should work."""
        resolver = LocationResolver()
        result = resolver.resolve(-46.615, 168.339)
        assert result is not None
        country, _city = result
        assert country == "NZ"
