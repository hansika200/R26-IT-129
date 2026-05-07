"""
utils/logger.py
===============
Centralized logging configuration for the Hansika Teacher Dashboard.

Sets up a rotating file handler + console handler so all modules
share consistent log formatting.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
import logging.handlers
import sys
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FORMAT = (
    "[%(asctime)s] %(levelname)-8s %(name)-30s %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "hansika",
    level: int = logging.DEBUG,
    log_file: str = "hansika.log",
) -> logging.Logger:
    """
    Configure and return a named logger.

    Args:
        name:     Logger namespace — use __name__ in each module.
        level:    Minimum log level (DEBUG in dev, INFO in prod).
        log_file: Filename inside the logs/ directory.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers when called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── Console handler ───────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ── Rotating file handler (10 MB × 5 backups) ─────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# Module-level root logger — import and use across the project
logger = setup_logger("hansika")
