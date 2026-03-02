# AI Bot

Telegram bot interface for AI CLI with session persistence.

## Features

- Multi-session support per user
- Session switching and history
- AI-powered session summaries
- Async architecture for better performance
- Optional authentication

## Quick Start

### 1. Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your settings
```

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
| `/new` | Start new session |
| `/session` | Show current session info |
| `/session_list` | List all sessions |
| `/s_<id>` | Switch to session |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_TOKEN` | (required) | Bot API token |
| `ALLOWED_CHAT_IDS` | (empty) | Allowed chat IDs |
| `MAINTAINER_CHAT_ID` | (empty) | Dev notification target |
| `AI_COMMAND` | `claude` | AI CLI command |
| `SESSION_TIMEOUT_HOURS` | `24` | Session expiry |
| `REQUIRE_AUTH` | `true` | Require authentication |

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Architecture

```
src/
├── main.py           # Entry point
├── config.py         # Configuration
├── bot/
│   ├── handlers.py   # Command handlers
│   ├── middleware.py # Auth middleware
│   └── formatters.py # Message formatting
└── claude/
    ├── client.py     # Async CLI wrapper
    └── session.py    # Session storage
```

## License

MIT
