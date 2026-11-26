# NEPSE Market Agent

Backend API and question-answering agent built with FastAPI and SQLite for analyzing simulated Nepal Stock Exchange (NEPSE) market data.

**Note:** All company names, ticker symbols, and price records in `data/companies.csv` and `data/prices.csv` are simulated for this project. They do not represent live or historical NEPSE trading data, and nothing here is investment advice.

## Dataset

The repository includes two CSV files in `data/`:

- `companies.csv` (39 rows): 3 fictional companies in each of NEPSE's 13 sectors (`Commercial Banks`, `Development Banks`, `Finance`, `Hotels and Tourism`, `Hydropower`, `Investment`, `Life Insurance`, `Manufacturing and Processing`, `Microfinance`, `Mutual Fund`, `Non-Life Insurance`, `Others`, `Trading`).
- `prices.csv` (2,340 rows): 60 trading days ending `2026-11-26`, skipping Fridays and Saturdays to follow NEPSE's Sunday–Thursday schedule. Each row has `symbol`, `trade_date`, `open`, `high`, `low`, `close`, and `volume`.

## Setup and Run

### Using standard `venv` and `pip`

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.load_data
uvicorn app.main:app --reload
```

### Using `uv`

```bash
uv sync
uv run python -m app.load_data
uv run uvicorn app.main:app --reload
```

Once the server is running, open `http://127.0.0.1:8000/docs` to test the endpoints in Swagger UI.

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check (`{"status": "ok"}`) |
| `GET` | `/sectors` | Sector performance ranked by average `% change` and turnover |
| `GET` | `/sectors/{sector}/explain` | Explains why a sector moved (vs market average, best/worst stock, turnover change) |
| `GET` | `/movers` | Top gainers or losers (`?direction=gainers&limit=5&sector=Hydropower`) |
| `GET` | `/companies/{symbol}/history` | Recent daily OHLCV prices for a company (`?days=10`) |
| `POST` | `/ask` | Answers natural-language questions (`{"question": "..."}`) |

Missing records return HTTP `404` with `{"error": "..."}`. Invalid parameters return HTTP `422`.

## How the Agent Works

Every answer comes directly from the SQLite query functions in `app/queries.py`:

- **Rules mode (default):** Works offline with no API key. Matches English and Nepali market keywords (`badhyo`, `girdo`, `ghatyo`, `kina`) and checks longer sector phrases first so `Non-Life Insurance` and `Microfinance` do not collide with `Life Insurance` or `Finance`.
- **LLM mode (optional):** If `ANTHROPIC_API_KEY` is set, Claude calls the four database query tools via tool-use and answers from their outputs. If the API call fails, it falls back to rules mode automatically.

Example request (`POST /ask`):

```json
{"question": "Aaja kun sector badhyo, kina?"}
```

Example response:

```json
{
  "answer": "Hydropower rose 2.32% on 2026-11-26 (market average +0.16%, so it did more than the market). 3 of 3 stocks went up. Best: TMHP (+4.41%, close 298.4). Worst: BGHP (+0.78%, close 192.9). Turnover was Rs 73.5 million, down 16.0% from 2026-11-25.",
  "tool": "explain_sector",
  "mode": "rules"
}
```

## Project Layout

```text
nepse-agent/
├── app/
│   ├── db.py           # SQLite connection, foreign keys, and schema
│   ├── load_data.py    # Loads companies.csv and prices.csv into SQLite
│   ├── queries.py      # Market calculations and query functions
│   ├── agent.py        # Rules router and optional Claude tool-use agent
│   └── main.py         # FastAPI endpoints and validation
├── data/
│   ├── companies.csv
│   └── prices.csv
├── tests/
│   ├── conftest.py     # Temporary test DB fixture
│   ├── test_data.py
│   ├── test_queries.py
│   ├── test_agent.py
│   └── test_api.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Running Tests

```bash
pytest
```

Tests run against a temporary SQLite database configured in `tests/conftest.py` and do not touch `data/nepse.db`.

## Limitations

- Price movements are simulated, so sector explanations are based on internal price, breadth, and turnover numbers rather than real news events.
- No authentication, live NEPSE scraping, or frontend UI is included.
