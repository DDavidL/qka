# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QKA (快量化 / Quick Quantitative Assistant) is a Python quantitative trading framework for the Chinese A-share stock market. It provides data acquisition (via Akshare), backtesting, and live trading (via QMT/xtquant). The project is published on PyPI as `qka`.

Language: Python 3.10+. Documentation and comments are primarily in Chinese.

## Build & Development Commands

```bash
# Install dependencies (uses uv package manager)
uv sync --all-extras

# Install in editable mode (alternative)
pip install -e .

# Run tests
uv run pytest

# Build distribution
uv build

# Build documentation
uv run mkdocs build

# Serve docs locally
uv run mkdocs serve
```

No linter or formatter is currently configured. No test suite exists yet (pytest is available as a dev dependency).

## Architecture

### Package Structure

```
qka/
├── core/           # Core trading engine
│   ├── data.py     # Data class - retrieval, caching (Parquet), Dask DataFrames
│   ├── strategy.py # Strategy ABC - implement on_bar(date, get)
│   ├── backtest.py # Backtest engine - time-series iteration, Plotly visualization
│   └── broker.py   # Broker - virtual broker for backtesting (cash, positions, trades)
├── brokers/        # Live trading interfaces
│   ├── server.py   # QMTServer - FastAPI wrapper around QMT with token auth
│   ├── client.py   # QMTClient - HTTP client for remote trading
│   └── trade.py    # Order/Trade/Position data models, order lifecycle
├── mcp/            # Model Context Protocol integration (under development)
│   ├── server.py   # FastMCP tool server + ModelServer class
│   └── api.py      # MCPServer/MCPClient (stub implementations, not yet functional)
└── utils/
    ├── logger.py   # StructuredLogger with JSON format + colored console output
    ├── anis.py     # ANSI color codes
    └── util.py     # Helpers (stock code formatting, timestamp conversion)
```

### Public API

Top-level exports via `qka/__init__.py`: `Data`, `Backtest`, `Strategy`. Access as `qka.Data`, `qka.Backtest`, `qka.Strategy`.

### Data Flow

1. **Data retrieval** (`qka.Data`) — parallel download from Akshare via ThreadPoolExecutor, cached as Parquet files, optional custom factor functions, returns Dask DataFrame
2. **Strategy** (subclass `qka.Strategy`) — implement `on_bar(date, get)` where `get(column)` returns a Series keyed by symbol; call `self.broker.buy()`/`self.broker.sell()`
3. **Backtesting** (`qka.Backtest`) — iterates dates (converts Dask to pandas via `.compute()`), calls `strategy.on_bar()`, records broker state each bar
4. **Visualization** (`backtest.plot()`) — interactive Plotly chart of total asset evolution

### Key Conventions

- Stock symbols must include exchange suffix: `000001.SZ`, `600000.SH`, `000063.BJ`
- The suffix is stripped automatically before calling Akshare APIs (in `data.py`)
- The `get()` function inside `on_bar` returns a pandas Series with symbol suffixes stripped from the index
- Column names in the merged DataFrame follow the pattern `{symbol}_{factor}` (e.g. `000001.SZ_close`)
- Factor-to-column mappings are pre-computed in `Backtest.run()` for O(1) lookups
- Broker state should only be modified through `buy()`/`sell()` methods, never directly
- Broker stores positions/trades as JSON strings in its DataFrame for serializability
- `Strategy.__init__` accepts an optional `Broker` instance for custom initial cash configuration
- Data caching means updated market data requires cache clearing (delete Parquet files in `datadir`)
- The QMT trading server defaults to `127.0.0.1` (localhost only) and uses `secrets.token_hex()` for auth tokens

### Known Limitations

- **MCP module is incomplete**: `MCPClient` in `api.py` is a stub that returns hardcoded responses. `MCPServer` doesn't follow JSON-RPC 2.0. The `query_akshare_data` tool in `mcp/server.py` uses `exec()` with a restricted namespace — functional but inherently risky.
- **No test suite**: pytest is configured as a dev dependency but no tests exist yet.
- **No linting**: No ruff/black/mypy configuration.

## Release & CI/CD

- **Versioning:** `hatch-vcs` (git tag based) + `python-semantic-release`
- **Commit convention:** Angular-style prefixes (`feat:`, `fix:`, `perf:`, `docs:`, `refactor:`, `test:`, `ci:`, `build:`, `chore:`, `style:`)
- **Minor bumps:** `feat:` commits. **Patch bumps:** `fix:`, `perf:` commits
- **CI workflows:** `release.yml` (build + PyPI publish on push to main), `docs.yml` (MkDocs to GitHub Pages on docs changes)
