"""Logging configuration for lrc-automation."""

import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def configure_logging(log_file: Path | None, verbose: bool = False) -> None:
    """Configure root logger: console at WARNING + file at DEBUG.

    When verbose=True the console handler is lowered to DEBUG as well.
    The file handler (if log_file is given) always writes at DEBUG level
    so every operation is recorded regardless of verbosity.
    """
    console_level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=console_level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        root = logging.getLogger()
        root.addHandler(fh)
        # Ensure root passes DEBUG records through to the file handler
        root.setLevel(logging.DEBUG)
