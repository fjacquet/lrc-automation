"""Tests for CLI auto-discovery of the default Lightroom catalog."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from lrc_automation.cli import _discover_default_catalog, cli

# ---------------------------------------------------------------------------
# Unit tests for _discover_default_catalog()
# ---------------------------------------------------------------------------


def test_discover_finds_lrcat(tmp_path: Path) -> None:
    """When tmp_path/Pictures/Lightroom/ contains a .lrcat, returns its path."""
    lr_dir = tmp_path / "Pictures" / "Lightroom"
    lr_dir.mkdir(parents=True)
    catalog = lr_dir / "Catalog.lrcat"
    catalog.touch()

    result = _discover_default_catalog(home_dir=tmp_path)

    assert result == str(catalog)


def test_discover_returns_none_no_dir(tmp_path: Path) -> None:
    """When ~/Pictures/Lightroom/ does not exist, returns None."""
    # tmp_path has no Pictures/Lightroom subdirectory
    result = _discover_default_catalog(home_dir=tmp_path)

    assert result is None


def test_discover_returns_none_empty_dir(tmp_path: Path) -> None:
    """When ~/Pictures/Lightroom/ exists but has no .lrcat files, returns None."""
    lr_dir = tmp_path / "Pictures" / "Lightroom"
    lr_dir.mkdir(parents=True)
    # No .lrcat files, only an unrelated file
    (lr_dir / "some_other_file.txt").touch()

    result = _discover_default_catalog(home_dir=tmp_path)

    assert result is None


def test_discover_returns_first_when_multiple(tmp_path: Path) -> None:
    """When multiple .lrcat files exist, returns the first (sorted) one."""
    lr_dir = tmp_path / "Pictures" / "Lightroom"
    lr_dir.mkdir(parents=True)
    catalog_b = lr_dir / "B-Catalog.lrcat"
    catalog_a = lr_dir / "A-Catalog.lrcat"
    catalog_b.touch()
    catalog_a.touch()

    result = _discover_default_catalog(home_dir=tmp_path)

    # sorted() → A-Catalog.lrcat is first
    assert result == str(catalog_a)


# ---------------------------------------------------------------------------
# Integration tests via CliRunner
# ---------------------------------------------------------------------------


def test_cli_auto_discovers_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cli proceeds past discovery when no --catalog and a path is found."""
    fake_catalog = tmp_path / "Test.lrcat"
    fake_catalog.touch()

    # Monkeypatch the module-level function so the CLI uses our fake path
    import lrc_automation.cli as cli_module

    monkeypatch.setattr(
        cli_module, "_discover_default_catalog", lambda: str(fake_catalog)
    )
    monkeypatch.delenv("LRC_CATALOG_PATH", raising=False)

    runner = CliRunner()
    # The catalog exists but is not a real LR catalog; CatalogConnection will fail,
    # which is fine — we just need to confirm the discovery path doesn't raise
    # "No catalog specified" UsageError.
    result = runner.invoke(cli, ["scan"])

    # Must NOT contain the "No catalog specified" usage error
    assert "No catalog specified" not in result.output


def test_cli_errors_when_no_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cli raises UsageError when no --catalog and discovery returns None."""
    import lrc_automation.cli as cli_module

    monkeypatch.setattr(cli_module, "_discover_default_catalog", lambda: None)
    monkeypatch.delenv("LRC_CATALOG_PATH", raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["scan"])

    assert "No catalog specified" in result.output


def test_cli_explicit_catalog_not_found(tmp_path: Path) -> None:
    """BadParameter with 'Catalog not found' when --catalog path does not exist."""
    nonexistent = tmp_path / "ghost.lrcat"
    runner = CliRunner()
    result = runner.invoke(cli, ["--catalog", str(nonexistent), "scan"])

    assert "Catalog not found" in result.output


def test_cli_explicit_catalog_still_works(tmp_path: Path) -> None:
    """Explicit --catalog path that exists proceeds past the auto-discovery logic."""
    fake_catalog = tmp_path / "MyLR.lrcat"
    fake_catalog.touch()

    runner = CliRunner()
    result = runner.invoke(cli, ["--catalog", str(fake_catalog), "scan"])

    # Must NOT raise "No catalog specified" or "Catalog not found"
    assert "No catalog specified" not in result.output
    assert "Catalog not found" not in result.output
