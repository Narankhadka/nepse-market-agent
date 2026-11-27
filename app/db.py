
"""Database helpers: one place that knows where the SQLite file is."""

import os
import sqlite3

DEFAULT_DB = os.path.join("data", "nepse.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    symbol TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    sector TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT NOT NULL REFERENCES companies(symbol),
    trade_date TEXT NOT NULL,
    open       REAL NOT NULL,
    high       REAL NOT NULL,
    low        REAL NOT NULL,
    close      REAL NOT NULL,
    volume     INTEGER NOT NULL,
    UNIQUE (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(trade_date);
"""


def get_conn():
    """Open a SQLite connection with Row access and foreign keys enabled."""
    path = os.environ.get("NEPSE_DB", DEFAULT_DB)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
