# Diary Management

Plugin for writing and managing one diary entry per day.

## DB Schema

```sql
diaries (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    date TEXT NOT NULL,         -- YYYY-MM-DD (one per day, UNIQUE)
    content TEXT NOT NULL,      -- Diary content
    created_at TEXT,
    updated_at TEXT
)
```

## Features

- Write today's or yesterday's diary entry
- Edit and delete diary entries
- View monthly list (navigate between months)
- View individual entry by date
- Diary writing reminder schedule

## AI Assistance

- Writing assistant (refine prose, enrich content)
- Emotion and mood analysis
- Generate monthly retrospectives and summaries
- Suggest reflective questions
- Discover recurring patterns or growth points

## MCP Tools

Use the `query_db` tool when you need to query or modify data. The `{chat_id}` placeholder is substituted automatically.

- Monthly query: `query_db("SELECT * FROM diaries WHERE chat_id = {chat_id} AND date LIKE '2026-03%'")`
- Specific date: `query_db("SELECT * FROM diaries WHERE chat_id = {chat_id} AND date = '2026-03-22'")`
- Inspect table structure: `db_schema("diaries")`

## Constraints

- Only one diary entry per day (chat_id + date UNIQUE)
- Isolated per user (chat_id)
- List managed in monthly units
