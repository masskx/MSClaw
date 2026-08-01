# MSClaw

<p align="center">
  <strong>Personal AI Agent powered by Telegram and the Claude Agent SDK</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-blue.svg" alt="Python 3.13+">
</p>

MSClaw is a personal AI assistant that runs as a Telegram bot, backed by the
[Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/claude-agent-sdk). It
provides owner-only access to a Claude-powered agent with filesystem, web, and shell
capabilities — all through a familiar chat interface.

## Features

- **Telegram Bot** — Polling-based entry point with owner-only authorization.
- **Claude Agent SDK** — Full agent loop with tool use, session resume, and MCP integration.
- **Long-term Memory** — `CLAUDE.md` workspace memory loaded as the agent's system prompt.
- **Conversation Archive** — Daily Markdown logs of every exchange.
- **Typed Configuration** — Fail-fast validation at startup with clear error messages.
- **Structured Logging** — Standard-library logging with timestamps and module names.
- **Unit Tests** — `pytest` + `pytest-asyncio` covering config, storage, agent, and handlers.

## Architecture

```
┌──────────────────┐     ┌─────────────────────┐     ┌──────────────────────┐
│   Telegram User   │────▶│   telegram_app.py    │────▶│     agent.py          │
│  (owner only)     │◀────│  auth → handlers     │◀────│  Claude Agent SDK     │
└──────────────────┘     └──────────┬───────────┘     └──────────┬───────────┘
                                    │                            │
                                    ▼                            ▼
                          ┌──────────────────┐     ┌──────────────────────┐
                          │   storage.py      │     │     config.py         │
                          │  sessions, archive│     │  env → Settings       │
                          └──────────────────┘     └──────────────────────┘
```

| Module | Responsibility |
| --- | --- |
| [`config.py`](src/msclaw/config.py) | Typed `Settings` dataclass with fail-fast env parsing |
| [`agent.py`](src/msclaw/agent.py) | Claude Agent SDK wrapper, tool allowlist, MCP server, session resume |
| [`telegram_app.py`](src/msclaw/telegram_app.py) | Telegram handlers, authorization, message splitting, app bootstrap |
| [`storage.py`](src/msclaw/storage.py) | Session ID persistence, workspace bootstrap, conversation archiving |

## Quick Start

### Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** — package manager and virtual environment tool
- A **Telegram bot token** from [@BotFather](https://t.me/BotFather)
- An **Anthropic API key** from the [Anthropic Console](https://console.anthropic.com/)

### Installation

```bash
# Clone the repository
git clone <repo-url> && cd MSClaw

# Install dependencies
uv sync --dev

# Configure environment
cp .env.example .env
# Edit .env with your credentials — never commit this file.
```

### Running

```bash
uv run msclaw
```

The bot starts polling Telegram and responds to the configured owner only.

### Commands

| Command | Description |
| --- | --- |
| `/start` | Greet and confirm the bot is ready |
| `/clear` | Reset the current conversation session |
| Any text | Sent to the Claude agent for processing |

## Configuration

All configuration is read from environment variables or a `.env` file:

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Yes | — | Telegram bot token from @BotFather |
| `OWNER_ID` | Yes | — | Numeric Telegram user ID granted access |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `ANTHROPIC_BASE_URL` | No | — | Custom Anthropic-compatible API endpoint |
| `ASSISTANT_NAME` | No | `Memory Bot` | Display name shown in greetings |
| `MSCLAW_WORKSPACE` | No | `./workspace` | Agent workspace directory |
| `MSCLAW_DATA_DIR` | No | `./data` | Runtime state directory |

> **Note:** The entry point loads `.env` with `override=False` — existing environment
> variables take precedence over `.env` values.

## Development

### Running Tests

```bash
uv run pytest
```

### Linting

```bash
uv run ruff check src/ tests/
```

### Type Checking

MSClaw uses standard Python type hints throughout. Consider adding `mypy` for static analysis:

```bash
uv run mypy src/
```

## Roadmap

| Priority | Task | Notes |
| --- | --- | --- |
| **P0** | Harden tool permissions with workspace boundary enforcement | Security — before HTTP exposure |
| **P1** | FastAPI health/chat endpoints with SSE streaming | Enables web client access |
| **P1** | LangGraph state management and conditional routing | Structured multi-step workflows |
| **P2** | Standalone custom MCP server | Extensible tool ecosystem |
| **P2** | PostgreSQL/Redis persistence + Langfuse tracing | Production-grade observability |
| **P3** | Docker Compose and GitHub Actions CI | Reproducible deployment |

## Project Structure

```
.
├── src/msclaw/           # Application package
│   ├── __init__.py       # Package metadata
│   ├── config.py         # Configuration
│   ├── agent.py          # Claude Agent SDK integration
│   ├── telegram_app.py   # Telegram bot and entry point
│   └── storage.py        # Persistence and archives
├── tests/                # Unit tests
│   ├── test_config.py
│   ├── test_agent.py
│   ├── test_telegram_app.py
│   └── test_storage.py
├── workspace/            # Agent workspace (runtime)
├── data/                 # Session state (runtime)
├── ep1.py – ep5.py       # Tutorial snapshots (archived)
├── ep6.py                # Legacy compatibility entry point
├── pyproject.toml        # Project metadata and dependencies
├── .env.example          # Environment template
└── README.md
```
