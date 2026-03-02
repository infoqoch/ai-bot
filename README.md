# Telegram Claude Bot

Telegram bot interface for Claude Code CLI with session persistence.

## Features

- 🔐 Optional authentication with secret key
- 💬 Multi-session support per user
- 🔄 Session switching and history
- 📝 AI-powered session summaries
- 🚀 Async architecture for better performance

## Quick Start

### 1. Clone and setup

```bash
cd telegram-claude-bot
python -m venv venv
source venv/bin/activate
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings
```

Required settings:
- `TELEGRAM_TOKEN`: Your Telegram bot token from @BotFather
- `ALLOWED_CHAT_IDS`: Comma-separated list of allowed Telegram chat IDs

### 3. Run

```bash
python -m src.main
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show bot status |
| `/help` | Show help message |
| `/auth <key>` | Authenticate (if required) |
| `/status` | Check auth status |
| `/new` | Start new Claude session |
| `/session` | Show current session info |
| `/session_list` | List all sessions with AI summaries |
| `/s_<id>` | Switch to session by ID prefix |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_TOKEN` | (required) | Bot API token |
| `ALLOWED_CHAT_IDS` | (empty) | Allowed chat IDs (empty = all) |
| `CLAUDE_COMMAND` | `claude` | Claude CLI command |
| `SESSION_TIMEOUT_HOURS` | `24` | Session expiry time |
| `REQUIRE_AUTH` | `true` | Require authentication |
| `AUTH_SECRET_KEY` | (empty) | Secret key for auth |
| `AUTH_TIMEOUT_MINUTES` | `30` | Auth session timeout |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=src
```

## Architecture

```
src/
├── main.py           # Entry point
├── config.py         # Configuration management
├── bot/
│   ├── handlers.py   # Telegram command handlers
│   ├── middleware.py # Auth middleware
│   └── formatters.py # Message formatting
└── claude/
    ├── client.py     # Async Claude CLI wrapper
    └── session.py    # Session storage
```

## License

MIT
