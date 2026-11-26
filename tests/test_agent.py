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


def test_ask_uses_rules_without_key(conn):
    assert agent.ask(conn, "top losers")["mode"] == "rules"


class FakeClient:
    """Stub Anthropic client to verify the tool-use loop offline."""

    def __init__(self):
        self.calls = 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            block = SimpleNamespace(
                type="tool_use",
                id="t1",
                name="top_movers",
                input={"direction": "gainers", "limit": 2},
            )
            return SimpleNamespace(stop_reason="tool_use", content=[block])
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="Done.")],
        )


def test_llm_loop_runs_tool_then_answers(conn):
    r = agent.ask_llm(conn, "top 2 gainers?", client=FakeClient())
    assert r == {"answer": "Done.", "tool": "top_movers", "mode": "llm"}


def test_llm_tool_error_is_returned_not_crashed(conn):
    content, is_error = agent._run_tool(conn, "company_history", {"symbol": "XXXX"})
    assert is_error and "not found" in content
