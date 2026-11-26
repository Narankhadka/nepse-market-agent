"""All database questions live here. No FastAPI, no AI — just plain functions."""


class NotFound(Exception):
    """Raised when a sector, symbol, or date does not exist."""


def latest_date(conn):
    row = conn.execute("SELECT MAX(trade_date) AS d FROM prices").fetchone()
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
    rows = conn.execute("SELECT DISTINCT sector FROM companies ORDER BY sector").fetchall()
    return [r["sector"] for r in rows]

def resolve_sector(conn,name):
    target = name.strip().lower()
    for s in list_sectors(conn):
        if s.lower() == target:
            return s

    raise NotFound(f"Sector '{name}' not found")

def stock_changes(conn, date=None):
    date = _resolve_date(conn, date)
    prev = previous_date(conn, date)
    if prev is None:
        raise NotFound(f"{date} is the first day in the data, so there is no change to show.")
    rows = conn.execute(
        """
        SELECT p.symbol, c.name, c.sector, p.close, q.close AS prev_close,
               ROUND((p.close - q.close) * 100.0 / q.close, 2) AS change_pct,
               ROUND(p.close * p.volume, 0) AS turnover,
               ROUND(q.close * q.volume, 0) AS prev_turnover
        FROM prices p
        JOIN companies c ON c.symbol = p.symbol
        JOIN prices q ON q.symbol = p.symbol AND q.trade_date = ?
        WHERE p.trade_date = ?
        """,
        (prev, date),
    ).fetchall()
    return date, prev, [dict(r) for r in rows]

def sector_performance(conn, date=None):
    date, prev, stocks = stock_changes(conn, date)
    by_sector = {}
    for s in stocks:
        d = by_sector.setdefault(s["sector"], {"changes": [], "turnover": 0})
        d["changes"].append(s["change_pct"])
        d["turnover"] += s["turnover"]

    result = []
    for sector, d in by_sector.items():
        result.append(
            {
                "sector": sector,
                "avg_change_pct": round(sum(d["changes"]) / len(d["changes"]), 2),
                "turnover": d["turnover"],
                "stocks": len(d["changes"]),
            }
        )
    result.sort(key=lambda r: r["avg_change_pct"], reverse=True)
    return {"date": date, "previous_date": prev, "sectors": result}
