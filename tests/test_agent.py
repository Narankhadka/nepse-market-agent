"""Tests for rules-based and LLM-backed agent routing."""

from types import SimpleNamespace
import pytest
from app import agent
from app.db import get_conn


@pytest.fixture
def conn():
    c = get_conn()
    yield c
    c.close()


def test_which_sector_rose_and_why(conn):
    r = agent.ask_rules(conn, "Aaja kun sector badhyo, kina?")
    assert r["tool"] == "explain_sector"
    assert "turnover" in r["answer"].lower()


def test_worst_sector(conn):
    r = agent.ask_rules(conn, "which sector fell the most today")
    assert r["tool"] == "sector_performance"
    assert "weakest" in r["answer"]


def test_top_gainers_in_sector(conn):
    r = agent.ask_rules(conn, "top gainers in hydropower")
    assert r["tool"] == "top_movers"
    assert "Hydropower" in r["answer"]


def test_company_question(conn):
    r = agent.ask_rules(conn, "show SGBL price")
    assert r["tool"] == "company_history"
    assert "Sagarmatha Grand Bank" in r["answer"]


def test_non_life_is_not_life(conn):
    r = agent.ask_rules(conn, "why did non-life insurance move")
    assert "Non-Life Insurance" in r["answer"]


def test_microfinance_is_not_finance(conn):
    r = agent.ask_rules(conn, "explain microfinance")
    assert "Microfinance" in r["answer"]


def test_unknown_question_gives_help(conn):
    r = agent.ask_rules(conn, "what is the weather")
    assert r["tool"] is None and "Try:" in r["answer"]

def test_ask_uses_rules_without_key(conn, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert agent.ask(conn, "top losers")["mode"] == "rules"


class FakeGeminiClient:
    """Stub Gemini client to verify tool wiring offline."""

    def __init__(self):
        self.models = self

    def generate_content(self, **kwargs):
        tools = {fn.__name__: fn for fn in kwargs["config"].tools}
        data = tools["top_movers"](direction="gainers", limit=2)
        assert len(data["stocks"]) == 2
        return SimpleNamespace(text="Done.")


def test_llm_loop_runs_tool_then_answers(conn):
    r = agent.ask_llm(conn, "top 2 gainers?", client=FakeGeminiClient())
    assert r == {"answer": "Done.", "tool": "gemini_tools", "mode": "llm"}
