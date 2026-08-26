from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import traceback

from app.runtime_paths import ensure_user_directories, logs_root
from app.version import APP_NAME, APP_VERSION


def configure_logging() -> Path:
    ensure_user_directories()
    log_path = logs_root() / "sprite_studio.log"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == log_path for handler in root.handlers):
        handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    logging.getLogger(__name__).info("Starting %s %s frozen=%s", APP_NAME, APP_VERSION, bool(getattr(sys, "frozen", False)))
    return log_path


def install_exception_hook() -> None:
    logger = logging.getLogger("unum_sunt.crash")
    previous = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb) -> None:  # type: ignore[no-untyped-def]
        logger.critical("Unhandled exception\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "Unum Sunt Sprite Studio",
                    'An unhandled error occurred. Details were recorded in the application log.',
                )
        except Exception:
            pass
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook
