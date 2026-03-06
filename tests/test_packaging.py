"""Tests verifying packaging import guards work without optional dependencies."""

from __future__ import annotations

import importlib
import sys
import types

import pytest


class TestCliImportWithoutReverseGeocoder:
    """Verify that lrc_automation.cli imports cleanly without reverse_geocoder."""

    def test_cli_import_succeeds_without_reverse_geocoder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing lrc_automation.cli must not raise when reverse_geocoder is absent.

        This confirms that no top-level import of reverse_geocoder exists in cli.py
        or any module it imports unconditionally.
        """
        # Simulate reverse_geocoder being absent by mapping it to None in sys.modules.
        # Python treats None values in sys.modules as "module not found".
        monkeypatch.setitem(sys.modules, "reverse_geocoder", None)  # type: ignore[arg-type]

        # Remove previously cached lrc_automation modules so they re-import cleanly.
        cached = [k for k in sys.modules if k.startswith("lrc_automation")]
        for key in cached:
            monkeypatch.delitem(sys.modules, key, raising=False)

        # This must not raise ImportError even though reverse_geocoder is absent.
        module = importlib.import_module("lrc_automation.cli")
        assert module is not None


class TestGeocoderImportGuard:
    """Verify LocationResolver raises a clear error when reverse_geocoder is absent."""

    def test_geocoder_import_raises_without_geo_extra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Calling resolve() without reverse_geocoder raises ImportError.

        The error message must contain guidance about installing the [geo] extra.
        """
        # Remove reverse_geocoder from sys.modules to simulate absence.
        monkeypatch.setitem(sys.modules, "reverse_geocoder", None)  # type: ignore[arg-type]

        # Re-import geocoder module without the cached reverse_geocoder reference.
        cached = [k for k in sys.modules if k.startswith("lrc_automation")]
        for key in cached:
            monkeypatch.delitem(sys.modules, key, raising=False)

        from lrc_automation.geocoder import LocationResolver

        resolver = LocationResolver()

        with pytest.raises(ImportError, match="lrc-automation\\[geo\\]"):
            resolver.resolve(48.8566, 2.3522)

    def test_geocoder_batch_raises_without_geo_extra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Calling resolve_batch() without reverse_geocoder raises ImportError."""
        monkeypatch.setitem(sys.modules, "reverse_geocoder", None)  # type: ignore[arg-type]

        cached = [k for k in sys.modules if k.startswith("lrc_automation")]
        for key in cached:
            monkeypatch.delitem(sys.modules, key, raising=False)

        from lrc_automation.geocoder import LocationResolver

        resolver = LocationResolver()

        with pytest.raises(ImportError, match="lrc-automation\\[geo\\]"):
            resolver.resolve_batch([(48.8566, 2.3522)])

    def test_geocoder_lazy_load_not_triggered_at_import(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing lrc_automation.geocoder must not trigger reverse_geocoder load."""
        # Track whether reverse_geocoder is accessed.
        accessed: list[str] = []

        class _SentinelModule(types.ModuleType):
            def __getattr__(self, name: str) -> object:
                accessed.append(name)
                return None

        monkeypatch.setitem(
            sys.modules, "reverse_geocoder", _SentinelModule("reverse_geocoder")
        )

        cached = [k for k in sys.modules if k.startswith("lrc_automation")]
        for key in cached:
            monkeypatch.delitem(sys.modules, key, raising=False)

        # Importing the module must not call any attribute on reverse_geocoder.
        importlib.import_module("lrc_automation.geocoder")

        # No attribute should have been accessed on the sentinel — confirms lazy load.
        assert accessed == [], (
            f"Unexpected accesses to reverse_geocoder at import time: {accessed}"
        )
