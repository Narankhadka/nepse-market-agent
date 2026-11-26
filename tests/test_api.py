"""HTTP tests for FastAPI endpoints and error responses."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_sectors():
    r = client.get("/sectors")
    assert r.status_code == 200 and len(r.json()["sectors"]) == 13


def test_movers_validation():
    assert client.get("/movers?direction=sideways").status_code == 422
    assert client.get("/movers?limit=0").status_code == 422
    assert client.get("/movers?direction=losers&limit=2").status_code == 200


def test_unknown_symbol_404():
    r = client.get("/companies/XXXX/history")
    assert r.status_code == 404 and "error" in r.json()


def test_explain_unknown_sector_404():
    assert client.get("/sectors/Space%20Mining/explain").status_code == 404


def test_explain_ok():
    r = client.get("/sectors/Commercial%20Banks/explain")
    assert r.status_code == 200 and r.json()["sector"] == "Commercial Banks"


def test_bad_date_422():
    assert client.get("/sectors?date=yesterday").status_code == 422


def test_ask():
    r = client.post("/ask", json={"question": "Which sector rose today and why?"})
    assert r.status_code == 200 and r.json()["tool"] == "explain_sector"


def test_ask_too_short_422():
    assert client.post("/ask", json={"question": "hi"}).status_code == 422
