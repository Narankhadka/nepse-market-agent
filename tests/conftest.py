"""Pytest fixtures: build an isolated temporary database for the test session."""

import pytest
from app import load_data


@pytest.fixture(scope="session", autouse=True)
def test_database(tmp_path_factory):
    """Load CSV data into a temporary SQLite DB so real data/nepse.db is untouched."""
    folder = tmp_path_factory.mktemp("nepse")
    mp = pytest.MonkeyPatch()
    mp.setenv("NEPSE_DB", str(folder / "test.db"))
    mp.delenv("ANTHROPIC_API_KEY", raising=False)
    load_data.load("data")
    yield
    mp.undo()
