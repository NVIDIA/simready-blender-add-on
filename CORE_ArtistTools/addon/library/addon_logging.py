# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import datetime
import logging
import logging.handlers
import os
import pathlib
import sys
import traceback

import bpy

# Public API ---------------------------------------------------------------

_logger: logging.Logger | None = None
_log_dir: pathlib.Path | None = None
_log_path: pathlib.Path | None = None


def setup_logger(
    addon_name: str,
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    capture_prints: bool = True,
) -> tuple[logging.Logger, pathlib.Path]:
    """
    Initialize a rotating file logger for this add-on.
    Returns (logger, log_path).
    Safe to call multiple times; reuses existing logger.
    """
    global _logger, _log_dir, _log_path
    if _logger:
        return _logger, _log_path

    # Put logs in the user's Blender config dir, namespaced by add-on
    cfg_dir = bpy.utils.user_resource("CONFIG") or os.path.expanduser("~")
    _log_dir = pathlib.Path(cfg_dir) / addon_name / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_path = _log_dir / f"{addon_name}_{stamp}.log"

    logger = logging.getLogger(addon_name)
    logger.setLevel(level)
    logger.propagate = False  # don't spam Blender's root logger

    # File handler (rotating)
    fh = logging.handlers.RotatingFileHandler(_log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(fh)

    # Optional: echo to console if System Console is open
    ch = logging.StreamHandler(stream=sys.__stdout__)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(ch)

    # Capture unhandled exceptions into the log
    def _excepthook(exc_type, exc, tb):
        logger.error("Uncaught exception", exc_info=(exc_type, exc, tb))
        # Preserve Blender's default behavior too
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    if capture_prints:
        _tee_prints_to_logger(logger)

    # Nice header
    logger.info("=== %s session start ===", addon_name)
    logger.info("Blender %s  build %s", bpy.app.version_string, bpy.app.build_hash)
    logger.info("Args: %s", getattr(bpy.app, "argv", []))

    _logger = logger
    return logger, _log_path


def get_logger(child: str | None = None) -> logging.Logger:
    """
    Get the add-on logger or a namespaced child, e.g., get_logger("io.export").
    """
    if not _logger:
        # Fallback if dev forgot to call setup_logger; use a temp logger
        tmp = logging.getLogger("addon")
        if not tmp.handlers:
            tmp.addHandler(logging.NullHandler())
        return tmp if not child else tmp.getChild(child)
    return _logger if not child else _logger.getChild(child)


def log_info(message: str, *args, **kwargs):
    """Convenience function to log info messages."""
    get_logger().info(message, *args, **kwargs)


def log_warning(message: str, *args, **kwargs):
    """Convenience function to log warning messages."""
    get_logger().warning(message, *args, **kwargs)


def log_error(message: str, *args, **kwargs):
    """Convenience function to log error messages."""
    get_logger().error(message, *args, **kwargs)


def logs_dir() -> pathlib.Path:
    return _log_dir if _log_dir else pathlib.Path(bpy.utils.user_resource("CONFIG") or "~")


def latest_log_path() -> pathlib.Path | None:
    if not _log_dir or not _log_dir.exists():
        return None
    logs = sorted(_log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


# Utilities ---------------------------------------------------------------


class _StreamToLogger:
    """Tee stdout/stderr into logger while preserving original streams."""

    def __init__(self, logger: logging.Logger, level: int, orig):
        self.logger = logger
        self.level = level
        self.orig = orig

    def write(self, buf):
        # Split on newlines to avoid giant concatenated lines
        for line in str(buf).splitlines():
            line = line.strip()
            if line:
                self.logger.log(self.level, line)
        # Don't write to original stream to avoid duplication
        # The logger's console handler will handle the output

    def flush(self):
        if self.orig:
            self.orig.flush()


def _tee_prints_to_logger(logger: logging.Logger):
    try:
        sys.stdout = _StreamToLogger(logger, logging.INFO, sys.__stdout__)
        sys.stderr = _StreamToLogger(logger, logging.ERROR, sys.__stderr__)
    except Exception:
        logger.warning("Failed to tee stdout/stderr to logger:\n%s", traceback.format_exc())
