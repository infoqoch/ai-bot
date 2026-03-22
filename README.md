# Telegram AI CLI Bot

Control local AI coding agents (Claude Code, Codex CLI) from your phone via Telegram.

Use your existing Claude Code / Codex CLI login from Telegram, create new sessions remotely, continue the sessions you already have on your machine, and keep longer-running work stable.

---

## Why It Is Practical

- Use the CLI subscriptions and logins you already have; no separate API-first setup is required
- Chat with Claude Code or Codex from Telegram wherever you are
- Create new sessions from Telegram when you want fresh work
- Import local CLI sessions and continue them from Telegram without starting over

## Why Sessions Matter

- Multi-session workflow across providers, projects, and tasks
- Workspace and folder aware execution that applies each project's `CLAUDE.md`
- Session switching, queueing, and session-level isolation for safer long-running work
- Fast-path plugin handling so simple actions do not always pay the AI latency cost

## Why It Feels Stable

- Long-running work runs in detached workers instead of living only in the main bot process
- SQLite-backed state adds persistence for locks, queued work, and delivery tracking
- Delivery retry and persistent queueing make responses less likely to disappear on restarts or send failures

## Why It Extends

- Scheduler-driven work for chat, workspace, folder, and plugin actions
- MCP-backed access to live bot data during AI work
- An extension surface for custom plugins, using the built-ins as reference implementations

## Built-In Plugins

Todo, Memo, Diary, Calendar, and Weather ship by default.

Treat them as both useful defaults and reference implementations for extension. Detailed behavior belongs in the plugin spec, not in this README:

- Built-in plugin spec: [docs/SPEC_PLUGINS_BUILTIN.md](docs/SPEC_PLUGINS_BUILTIN.md)
- Extension rules and plugin interfaces: [CLAUDE.md](CLAUDE.md)

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/infoqoch/telegram-ai-cli-bot.git
cd telegram-ai-cli-bot
python -m venv venv && source venv/bin/activate
pip install -e .
```

### 2. Create a Telegram Bot

1. Open [@BotFather](https://t.me/BotFather) and run `/newbot`
2. Copy the API token

### 3. Finish Setup

If you have [Claude Code](https://claude.ai/claude-code) installed, let it guide you through setup interactively:

```bash
claude
# Then say: "help me set up"
```

Claude reads the project's `CLAUDE.md` automatically and walks you through creating `.env`, configuring tokens, and starting the bot.

For manual setup, runtime commands, security controls, and environment variables, see [docs/SETUP.md](docs/SETUP.md).

---

## Documentation

| Doc | Content |
|-----|---------|
| [CLAUDE.md](CLAUDE.md) | Development rules, architecture contracts, extension interfaces |
| [docs/SETUP.md](docs/SETUP.md) | User-facing setup, runtime commands, security, and environment variables |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Runtime boundaries and code ownership |
| [docs/SPEC.md](docs/SPEC.md) | UI/UX specification, session/schedule/restart scenarios |
| [docs/SPEC_PLUGINS_BUILTIN.md](docs/SPEC_PLUGINS_BUILTIN.md) | Builtin plugin UI/UX specifications |

---

## Built With

Developed with [Claude Code](https://claude.ai/claude-code) and [Codex CLI](https://github.com/openai/codex).

## License

MIT
