"""Route market questions to database queries via rules or Claude."""
import json
import os
import re

from app import queries
from app.queries import NotFound

SECTOR_WORDS = {
    "commercial bank": "Commercial Banks",
    "commercial banks": "Commercial Banks",
    "banking": "Commercial Banks",
    "banks": "Commercial Banks",
    "bank": "Commercial Banks",
    "development bank": "Development Banks",
    "development banks": "Development Banks",
    "finance": "Finance",
    "hotel": "Hotels and Tourism",
    "hotels": "Hotels and Tourism",
    "tourism": "Hotels and Tourism",
    "hydropower": "Hydropower",
    "hydro": "Hydropower",
    "investment": "Investment",
    "life insurance": "Life Insurance",
    "life": "Life Insurance",
    "non-life": "Non-Life Insurance",
    "non life": "Non-Life Insurance",
    "nonlife": "Non-Life Insurance",
    "non-life insurance": "Non-Life Insurance",
    "manufacturing": "Manufacturing and Processing",
    "processing": "Manufacturing and Processing",
    "microfinance": "Microfinance",
    "micro finance": "Microfinance",
    "mutual fund": "Mutual Fund",
    "mutual funds": "Mutual Fund",
    "others": "Others",
    "trading": "Trading",
}

WHY_WORDS = {"why", "reason", "explain", "because", "kina", "kinaki", "kasari"}
LOSER_WORDS = {
    "loser", "losers", "fall", "fell", "falling", "drop", "dropped",
    "decline", "worst", "down", "lower", "weak", "weakest",
}
LOSER_STEMS = ("gir", "ghat", "ghatyo")
GAINER_WORDS = {
    "gainer", "gainers", "rise", "rose", "rising", "gain", "best",
    "up", "increase", "highest", "strong", "strongest", "top",
}
GAINER_STEMS = ("badh",)
STOCK_WORDS = {
    "stock", "stocks", "share", "shares", "company", "companies",
    "gainers", "losers", "movers", "mover",
}

HELP = (
    "I can answer questions about the simulated market data. Try: "
    "'Which sector rose today and why?', 'Top 3 gainers in Hydropower', "
    "'Show SGBL price', or 'Why did Microfinance fall?'"
)


def _find_sector(text):
    for word in sorted(SECTOR_WORDS, key=len, reverse=True):
        if re.search(r"(?<![a-z-])" + re.escape(word) + r"(?![a-z-])", text):
            return SECTOR_WORDS[word]
    return None


def _find_symbol(conn, question):
    rows = conn.execute("SELECT symbol FROM companies").fetchall()
    symbols = {r["symbol"] for r in rows}
    for token in re.findall(r"[A-Za-z0-9]+", question):
        if token.upper() in symbols:
            return token.upper()
    return None


def _direction(text, tokens):
    if tokens & LOSER_WORDS or any(s in text for s in LOSER_STEMS):
        return "losers"
    if tokens & GAINER_WORDS or any(s in text for s in GAINER_STEMS):
        return "gainers"
    return None


def _money(x):
    return f"Rs {x / 1_000_000:,.1f} million"


def _fmt_stock(s):
    return f"{s['symbol']} ({s['change_pct']:+.2f}%, close {s['close']})"


def _explain_text(e):
    direction = "rose" if e["avg_change_pct"] > 0 else "fell" if e["avg_change_pct"] < 0 else "was flat"
    vs = "more than" if e["avg_change_pct"] > e["market_avg_change_pct"] else "less than"
    turn = "up" if e["turnover_change_pct"] >= 0 else "down"
    return (
        f"{e['sector']} {direction} {abs(e['avg_change_pct']):.2f}% on {e['date']} "
        f"(market average {e['market_avg_change_pct']:+.2f}%, so it did {vs} the market). "
        f"{e['stocks_up']} of {e['stocks_total']} stocks went up. "
        f"Best: {_fmt_stock(e['best_stock'])}. Worst: {_fmt_stock(e['worst_stock'])}. "
        f"Turnover was {_money(e['turnover'])}, {turn} {abs(e['turnover_change_pct']):.1f}% from {e['previous_date']}."
    )

def ask_rules(conn, question):
    """Pick the right query tool using keywords and format the database result."""
    text = question.lower()
    tokens = set(re.findall(r"[a-z]+", text))
    sector = _find_sector(text)
    symbol = _find_symbol(conn, question)
    wants_why = bool(tokens & WHY_WORDS)
    direction = _direction(text, tokens)
    stock_level = bool(tokens & STOCK_WORDS)

    if symbol:
        r = queries.company_history(conn, symbol, days=5)
        last = r["history"][-1]
        first = r["history"][0]
        change = round((last["close"] - first["open"]) * 100 / first["open"], 2)
        c = r["company"]
        answer = (
            f"{c['name']} ({c['symbol']}, {c['sector']}) closed at {last['close']} on "
            f"{last['trade_date']}. Over the last {len(r['history'])} trading days it moved {change:+.2f}%."
        )
        return {"answer": answer, "tool": "company_history", "mode": "rules"}

    if wants_why:
        if sector is None:
            perf = queries.sector_performance(conn)["sectors"]
            sector = perf[-1]["sector"] if direction == "losers" else perf[0]["sector"]
        e = queries.explain_sector(conn, sector)
        return {"answer": _explain_text(e), "tool": "explain_sector", "mode": "rules"}

    if stock_level and direction:
        r = queries.top_movers(conn, direction, 3, sector)
        where = f" in {r['sector']}" if r["sector"] else ""
        lines = "; ".join(_fmt_stock(s) for s in r["stocks"])
        return {
            "answer": f"Top {direction}{where} on {r['date']}: {lines}.",
            "tool": "top_movers",
            "mode": "rules",
        }

    if sector and not direction:
        e = queries.explain_sector(conn, sector)
        return {"answer": _explain_text(e), "tool": "explain_sector", "mode": "rules"}

    if direction or sector or "sector" in tokens or "market" in tokens:
        perf = queries.sector_performance(conn)
        rows = perf["sectors"]
        if direction == "losers":
            rows = list(reversed(rows))
        top = rows[:3]
        lines = "; ".join(f"{r['sector']} {r['avg_change_pct']:+.2f}%" for r in top)
        label = "weakest" if direction == "losers" else "strongest"
        return {
            "answer": f"On {perf['date']} the {label} sectors were: {lines}.",
            "tool": "sector_performance",
            "mode": "rules",
        }

    return {"answer": HELP, "tool": None, "mode": "rules"}

TOOLS = [
    {
        "name": "sector_performance",
        "description": "Average % change and turnover for every sector on a day, best first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD. Leave out for the latest day."}
            },
        },
    },
    {
        "name": "top_movers",
        "description": "Top gaining or losing stocks on a day, optionally inside one sector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["gainers", "losers"]},
                "limit": {"type": "integer"},
                "sector": {"type": "string"},
                "date": {"type": "string"},
            },
            "required": ["direction"],
        },
    },
    {
        "name": "company_history",
        "description": "Recent daily prices for one stock symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "days": {"type": "integer"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "explain_sector",
        "description": "Why a sector moved: change vs market, best and worst stock, turnover change.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {"type": "string"},
                "date": {"type": "string"},
            },
            "required": ["sector"],
        },
    },
]

SYSTEM_PROMPT = (
    "You answer questions about a SIMULATED Nepal stock market dataset. "
    "Always use the tools and answer only from their results. "
    "Keep answers short and simple. If the data does not have the answer, say so. "
    "Do not give investment advice."
)


def _run_tool(conn, name, args):
    funcs = {
        "sector_performance": queries.sector_performance,
        "top_movers": queries.top_movers,
        "company_history": queries.company_history,
        "explain_sector": queries.explain_sector,
    }
    if name not in funcs:
        return json.dumps({"error": f"Unknown tool: {name}"}), True
    try:
        return json.dumps(funcs[name](conn, **args), default=str), False
    except (NotFound, TypeError) as e:
        return json.dumps({"error": str(e)}), True


def ask_llm(conn, question, client=None, model=None):
    """Run Claude tool-use loop so answers stay grounded in database results."""
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    model = model or os.environ.get("NEPSE_AGENT_MODEL", "claude-sonnet-4-5")
    messages = [{"role": "user", "content": question}]
    tool_used = None

    for _ in range(5):
        resp = client.messages.create(
            model=model,
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return {"answer": text, "tool": tool_used, "mode": "llm"}

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                tool_used = block.name
                content, is_error = _run_tool(conn, block.name, block.input)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                        "is_error": is_error,
                    }
                )
        messages.append({"role": "user", "content": results})

    return {
        "answer": "Sorry, I could not finish answering. Please ask in a simpler way.",
        "tool": tool_used,
        "mode": "llm",
    }


def ask(conn, question):
    """Use Claude if ANTHROPIC_API_KEY is set, otherwise fall back to rules."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return ask_llm(conn, question)
        except Exception:
            pass
    try:
        return ask_rules(conn, question)
    except NotFound as e:
        return {"answer": str(e), "tool": None, "mode": "rules"}
