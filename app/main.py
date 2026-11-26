from contextlib import asynccontextmanager
from typing import Optional
from fastapi import Depends, FastAPI, Query
from fastapi.responses import JSONResponse
from app import queries
from app.db import get_conn, init_db
from app.queries import NotFound

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="NEPSE Agent API (simulated data)", lifespan=lifespan)

def get_db():
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()

@app.exception_handler(NotFound)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"error": str(exc)})

@app.get("/health")
def health():
    return{"status":"ok"}

@app.get("/sectors")
def sectors(date: Optional[str] = Query(None, pattern=DATE_PATTERN), conn=Depends(get_db)):
    return queries.sector_performance(conn, date)

@app.get("/movers")
def movers(
    direction: str = Query("gainers", pattern="^(gainers|losers)$"),
    limit: int = Query(5, ge=1, le=20),
    sector: Optional[str] = None,
    date: Optional[str] = Query(None, pattern=DATE_PATTERN),
    conn=Depends(get_db),
):
    return queries.top_movers(conn, direction, limit, sector, date)

@app.get("/companies/{symbol}/history")
def history(symbol: str, days: int = Query(10, ge=1, le=60), conn=Depends(get_db)):
    return queries.company_history(conn, symbol, days)
