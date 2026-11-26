"""Tests for database query functions in app/queries.py."""

import pytest
from app import queries
from app.db import get_conn
from app.queries import NotFound


@pytest.fixture
def conn():
    c = get_conn()
    yield c
    c.close()


def test_latest_date(conn):
    assert queries.latest_date(conn) == "2026-11-26"


def test_sector_performance_sorted_best_first(conn):
    r = queries.sector_performance(conn)
    changes = [s["avg_change_pct"] for s in r["sectors"]]
    assert len(changes) == 13
    assert changes == sorted(changes, reverse=True)


def test_top_movers_order_and_limit(conn):
    r = queries.top_movers(conn, "gainers", 3)
    values = [s["change_pct"] for s in r["stocks"]]
    assert len(values) == 3 and values == sorted(values, reverse=True)


def test_top_movers_sector_filter(conn):
    r = queries.top_movers(conn, "losers", 5, "hydropower")
    assert r["sector"] == "Hydropower"
    assert all(s["sector"] == "Hydropower" for s in r["stocks"])
def test_company_history(conn):
    r = queries.company_history(conn, "sgbl", 5)
    assert r["company"]["symbol"] == "SGBL"
    assert len(r["history"]) == 5
    dates = [h["trade_date"] for h in r["history"]]
    assert dates == sorted(dates)


def test_explain_sector_fields(conn):
    e = queries.explain_sector(conn, "Microfinance")
    assert e["stocks_total"] == 3
    assert e["best_stock"]["change_pct"] >= e["worst_stock"]["change_pct"]


def test_unknown_things_raise(conn):
    with pytest.raises(NotFound):
        queries.company_history(conn, "XXXX")
    with pytest.raises(NotFound):
        queries.resolve_sector(conn, "Space Mining")
    with pytest.raises(NotFound):
        queries.sector_performance(conn, "2020-01-01")


def test_first_day_has_no_change(conn):
    with pytest.raises(NotFound):
        queries.sector_performance(conn, "2026-09-06")
