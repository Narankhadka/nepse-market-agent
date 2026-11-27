
"""All database questions live here. No FastAPI, no AI — just plain functions."""


class NotFound(Exception):
    """Raised when a sector, symbol, or date does not exist."""


class InvalidQuery(ValueError):
    """Raised when a database query receives invalid arguments."""


def latest_date(conn):
    row = conn.execute(
        "SELECT MAX(trade_date) AS d FROM prices"
    ).fetchone()

    if row["d"] is None:
        raise NotFound("No price data in the database. Run the loader first.")

    return row["d"]


def previous_date(conn, date):
    row = conn.execute(
        "SELECT MAX(trade_date) AS d FROM prices WHERE trade_date < ?",
        (date,),
    ).fetchone()
    return row["d"]


def _resolve_date(conn, date):
    if date is None:
        date = latest_date(conn)

    exists = conn.execute(
        "SELECT 1 FROM prices WHERE trade_date = ? LIMIT 1",
        (date,),
    ).fetchone()

    if not exists:
        raise NotFound(f"No data for date {date}.")

    return date


def list_sectors(conn):
    rows = conn.execute(
        "SELECT DISTINCT sector FROM companies ORDER BY sector"
    ).fetchall()
    return [r["sector"] for r in rows]


def resolve_sector(conn, name):
    target = name.strip().lower()

    for sector in list_sectors(conn):
        if sector.lower() == target:
            return sector

    raise NotFound(f"Sector '{name}' not found.")


def stock_changes(conn, date=None):
    date = _resolve_date(conn, date)
    prev = previous_date(conn, date)

    if prev is None:
        raise NotFound(
            f"{date} is the first day in the data, so there is no change to show."
        )

    rows = conn.execute(
        """
        SELECT
            p.symbol,
            c.name,
            c.sector,
            p.close,
            q.close AS prev_close,
            (p.close - q.close) * 100.0 / q.close AS change_pct,
            p.close * p.volume AS turnover,
            q.close * q.volume AS prev_turnover
        FROM prices p
        JOIN companies c ON c.symbol = p.symbol
        JOIN prices q ON q.symbol = p.symbol AND q.trade_date = ?
        WHERE p.trade_date = ?
        """,
        (prev, date),
    ).fetchall()

    return date, prev, [dict(row) for row in rows]


def sector_performance(conn, date=None):
    date, prev, stocks = stock_changes(conn, date)

    by_sector = {}

    for stock in stocks:
        sector_data = by_sector.setdefault(
            stock["sector"],
            {"changes": [], "turnover": 0},
        )
        sector_data["changes"].append(stock["change_pct"])
        sector_data["turnover"] += stock["turnover"]

    result = []

    for sector, data in by_sector.items():
        result.append(
            {
                "sector": sector,
                "avg_change_pct": round(
                    sum(data["changes"]) / len(data["changes"]), 2
                ),
                "turnover": round(data["turnover"], 0),
                "stocks": len(data["changes"]),
            }
        )

    result.sort(key=lambda row: (-row["avg_change_pct"], row["sector"]))

    return {
        "date": date,
        "previous_date": prev,
        "sectors": result,
    }


def top_movers(conn, direction="gainers", limit=5, sector=None, date=None):
    if direction not in ("gainers", "losers"):
        raise InvalidQuery("direction must be 'gainers' or 'losers'.")

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise InvalidQuery("limit must be a positive integer.")

    date, _, stocks = stock_changes(conn, date)

    if sector is not None:
        sector = resolve_sector(conn, sector)
        stocks = [stock for stock in stocks if stock["sector"] == sector]

    stocks.sort(
        key=lambda stock: (
            stock["change_pct"],
            stock["symbol"],
        ),
        reverse=(direction == "gainers"),
    )

    return {
        "date": date,
        "direction": direction,
        "sector": sector,
        "stocks": stocks[:limit],
    }


def company_history(conn, symbol, days=10):
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise InvalidQuery("days must be a positive integer.")

    symbol = symbol.strip().upper()

    company = conn.execute(
        "SELECT symbol, name, sector FROM companies WHERE symbol = ?",
        (symbol,),
    ).fetchone()

    if company is None:
        raise NotFound(f"Symbol '{symbol}' not found.")

    rows = conn.execute(
        """
        SELECT trade_date, open, high, low, close, volume
        FROM prices
        WHERE symbol = ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (symbol, days),
    ).fetchall()

    if not rows:
        raise NotFound(f"No price history available for '{symbol}'.")

    history = [dict(row) for row in reversed(rows)]

    return {
        "company": dict(company),
        "history": history,
    }


def explain_sector(conn, sector, date=None):
    sector = resolve_sector(conn, sector)
    date, prev, stocks = stock_changes(conn, date)

    mine = [stock for stock in stocks if stock["sector"] == sector]

    if not mine:
        raise NotFound(f"No price data available for sector '{sector}' on {date}.")

    avg = round(
        sum(stock["change_pct"] for stock in mine) / len(mine),
        2,
    )

    turnover = sum(stock["turnover"] for stock in mine)
    prev_turnover = sum(stock["prev_turnover"] for stock in mine)

    turnover_change = (
        round((turnover - prev_turnover) * 100.0 / prev_turnover, 1)
        if prev_turnover > 0
        else None
    )

    ranked = sorted(
        mine,
        key=lambda stock: (stock["change_pct"], stock["symbol"]),
    )

    market_avg = round(
        sum(stock["change_pct"] for stock in stocks) / len(stocks),
        2,
    )

    return {
        "sector": sector,
        "date": date,
        "previous_date": prev,
        "avg_change_pct": avg,
        "market_avg_change_pct": market_avg,
        "turnover": round(turnover, 0),
        "turnover_change_pct": turnover_change,
        "stocks_up": sum(
            1 for stock in mine if stock["change_pct"] > 0
        ),
        "stocks_total": len(mine),
        "best_stock": ranked[-1],
        "worst_stock": ranked[0],
    }
