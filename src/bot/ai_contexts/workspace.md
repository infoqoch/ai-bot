# Workspace - Local Project Directory Management

## Feature Overview
A feature for registering local development project directories with the bot, allowing the context of those projects (CLAUDE.md, etc.) to be applied to AI conversations.

## DB Schema (workspaces table)
| Column | Description |
|--------|-------------|
| id | Workspace unique ID |
| user_id | User ID |
| path | Absolute project path |
| name | Workspace name (display label) |
| description | Project description |
| keywords | Keyword list (JSON array) |
| created_at | Registration time |
| last_used | Last used time |
| use_count | Usage count |

## User Operations
- **Add**: Register a new workspace (enter path, name, and description)
- **Delete**: Remove a workspace
- **Create session**: Start an AI session based on the workspace (specifies the project directory via the --cwd option)
- **Register schedule**: Set up a recurring task based on the workspace
- **View list**: See registered workspaces

## Workspace Session Behavior
- The project path is specified via `--cwd` when creating a session
- Telegram formatting rules are injected via `--append-system-prompt`
- The project's CLAUDE.md rules are automatically applied to the AI

## AI Assistance Areas
- Analyze and summarize project status
- Workspace usage suggestions (automate frequently used tasks)
- Recommend custom schedules per project
- Advice on workspace organization and structuring

## MCP Tools

Use the `query_db` tool when you need to query data. The `{chat_id}` placeholder is automatically substituted as user_id.

- List all: `query_db("SELECT * FROM workspaces WHERE user_id = '{chat_id}'")`
- Inspect table structure: `db_schema("workspaces")`
