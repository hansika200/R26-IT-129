"""
database/db.py
==============
SQLite database connection manager for the Hansika Teacher Dashboard.

Uses Python's built-in sqlite3 module — no extra dependencies needed.
Provides a thread-safe connection context manager used by all services.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from config.settings import get_config

logger = logging.getLogger(__name__)
cfg = get_config()


def get_db_path() -> str:
    """Return the absolute path to the SQLite database file."""
    db_path = Path(cfg.DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path)


def get_connection() -> sqlite3.Connection:
    """
    Create and return a new SQLite connection.

    Row factory set to sqlite3.Row so results can be accessed
    by column name (e.g. row["id"]) as well as by index.
    """
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")   # enforce FK constraints
    conn.execute("PRAGMA journal_mode = WAL;")   # better concurrency
    return conn


@contextmanager
def db_context() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that yields a database connection and automatically
    commits on success or rolls back on exception.

    Usage:
        with db_context() as conn:
            conn.execute("INSERT INTO ...")
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Database transaction rolled back: %s", exc)
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Initialize the database by executing schema.sql.
    Safe to call on every startup — uses CREATE TABLE IF NOT EXISTS.
    """
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        logger.error("schema.sql not found at %s", schema_path)
        raise FileNotFoundError(f"schema.sql not found at {schema_path}")

    with get_connection() as conn:
        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()
        conn.executescript(sql)
        conn.commit()

    logger.info("Database initialized successfully at %s", get_db_path())


def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row object to a plain Python dictionary."""
    return dict(row) if row else {}


def rows_to_list(rows) -> list:
    """Convert a list of sqlite3.Row objects to a list of dicts."""
    return [dict(r) for r in rows] if rows else []
