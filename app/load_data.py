
"""Load data/companies.csv and data/prices.csv into SQLite.

Run: python -m app.load_data
Safe to run many times: it clears old rows first.
"""

import csv
import os
from contextlib import closing

from app.db import get_conn, init_db


def load(data_dir="data"):
    init_db()

    with open(
        os.path.join(data_dir, "companies.csv"),
        encoding="utf-8",
        newline="",
    ) as f:
        companies = [
            (r["symbol"], r["name"], r["sector"])
            for r in csv.DictReader(f)
        ]

    with open(
        os.path.join(data_dir, "prices.csv"),
        encoding="utf-8",
        newline="",
    ) as f:
        prices = [
            (
                r["symbol"],
                r["trade_date"],
                float(r["open"]),
                float(r["high"]),
                float(r["low"]),
                float(r["close"]),
                int(r["volume"]),
            )
            for r in csv.DictReader(f)
        ]

    with closing(get_conn()) as conn:
        with conn:
            conn.execute("DELETE FROM prices")
            conn.execute("DELETE FROM companies")

            conn.executemany(
                """
                INSERT INTO companies (symbol, name, sector)
                VALUES (?, ?, ?)
                """,
                companies,
            )

            conn.executemany(
                """
                INSERT INTO prices
                (symbol, trade_date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                prices,
            )

    return len(companies), len(prices)


if __name__ == "__main__":
    company_count, price_count = load()
    print(
        f"Loaded {company_count} companies and "
        f"{price_count} price rows into the database."
    )
