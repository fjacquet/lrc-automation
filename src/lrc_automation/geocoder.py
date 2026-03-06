"""Offline reverse geocoding for GPS-tagged photos."""

from __future__ import annotations

import re
import types
import unicodedata

# Characters not allowed in folder names
_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|]')


def _sanitize_folder_name(name: str) -> str:
    """Sanitize a string for use as a folder name.

    Strips control characters and filesystem-unsafe characters,
    normalizes unicode to NFC form.
    """
    # Normalize unicode (e.g. composed form)
    name = unicodedata.normalize("NFC", name)
    # Remove unsafe filesystem characters
    name = _UNSAFE_CHARS.sub("", name)
    # Strip leading/trailing whitespace
    name = name.strip()
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name)
    return name


class LocationResolver:
    """Resolves GPS coordinates to (ISO-country-code, city) using offline geocoding."""

    def __init__(self) -> None:
        self._rg: types.ModuleType | None = None
        self._cache: dict[tuple[float, float], tuple[str, str]] = {}

    def _ensure_loaded(self) -> None:
        """Lazy-load reverse_geocoder on first use."""
        if self._rg is None:
            try:
                import reverse_geocoder

                self._rg = reverse_geocoder
            except ImportError as e:
                raise ImportError(
                    "reverse_geocoder is required for --location-folders. "
                    "Install it with: pip install lrc-automation[geo]"
                ) from e

    def resolve(self, lat: float, lon: float) -> tuple[str, str] | None:
        """Resolve a single coordinate to (country_code, city).

        Returns None if the coordinate cannot be resolved.
        """
        key = (lat, lon)
        if key in self._cache:
            return self._cache[key]

        self._ensure_loaded()
        assert self._rg is not None

        results: list[dict[str, str]] = self._rg.search([(lat, lon)])
        if not results:
            return None

        result = results[0]
        country = _sanitize_folder_name(result.get("cc", "").upper())
        city = _sanitize_folder_name(result.get("name", ""))

        if not country or not city:
            return None

        pair = (country, city)
        self._cache[key] = pair
        return pair

    def resolve_batch(
        self, coords: list[tuple[float, float]]
    ) -> dict[tuple[float, float], tuple[str, str]]:
        """Batch-resolve coordinates to (country_code, city) pairs.

        Returns a dict mapping each coordinate to its (country_code, city).
        Coordinates that cannot be resolved are omitted.
        """
        if not coords:
            return {}

        # Split into cached and uncached
        results: dict[tuple[float, float], tuple[str, str]] = {}
        uncached: list[tuple[float, float]] = []

        for coord in coords:
            if coord in self._cache:
                results[coord] = self._cache[coord]
            else:
                uncached.append(coord)

        if not uncached:
            return results

        self._ensure_loaded()
        assert self._rg is not None

        rg_results: list[dict[str, str]] = self._rg.search(uncached)

        for coord, result in zip(uncached, rg_results, strict=True):
            country = _sanitize_folder_name(result.get("cc", "").upper())
            city = _sanitize_folder_name(result.get("name", ""))

            if country and city:
                pair = (country, city)
                self._cache[coord] = pair
                results[coord] = pair

        return results
