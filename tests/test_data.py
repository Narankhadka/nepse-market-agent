"""Tests for database schema, constraints, and loaded CSV dataset."""

from datetime import date
import sqlite3
import pytest
from app.db import get_conn
from app.load_data import load


def test_13_sectors_and_39_companies():
    with get_conn() as conn:
        sectors = conn.execute("SELECT COUNT(DISTINCT sector) FROM companies").fetchone()[0]
        companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    assert sectors == 13
    assert companies == 39


def test_every_company_has_60_days():
    with get_conn() as conn:
        rows = conn.execute("SELECT symbol, COUNT(*) AS n FROM prices GROUP BY symbol").fetchall()
    assert len(rows) == 39
    assert all(r["n"] == 60 for r in rows)


def test_prices_are_sane():
    with get_conn() as conn:
        bad = conn.execute(
            "SELECT COUNT(*) FROM prices WHERE low > high OR close <= 0 OR volume <= 0"
        ).fetchone()[0]
    assert bad == 0


def test_no_friday_or_saturday():
    with get_conn() as conn:
        dates = [r["trade_date"] for r in conn.execute("SELECT DISTINCT trade_date FROM prices")]
    assert len(dates) == 60
    assert all(date.fromisoformat(d).weekday() not in (4, 5) for d in dates)


def test_loader_is_idempotent():
    c, p = load("data")
    assert (c, p) == (39, 2340)
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 39
        assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 2340


def test_db_constraints_enforced():
    with get_conn() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO prices (symbol, trade_date, open, high, low, close, volume) "
                "VALUES ('FAKE', '2026-11-26', 100, 110, 90, 105, 1000)"
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO prices (symbol, trade_date, open, high, low, close, volume) "
                "VALUES ('SGBL', '2026-11-26', 100, 110, 90, 105, 1000)"
            )
