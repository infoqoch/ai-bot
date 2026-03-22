# Todo Management

Plugin for managing todo lists organized by date.

## DB Schema

```sql
todos (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    date TEXT NOT NULL,        -- YYYY-MM-DD
    slot TEXT DEFAULT 'default',
    text TEXT NOT NULL,        -- Todo content
    done INTEGER DEFAULT 0,   -- 0=incomplete, 1=complete
    created_at TEXT,
    updated_at TEXT
)
```

## Features

- Add todos (bulk add via multi-line input)
- Mark as complete / delete
- Move to tomorrow (incomplete items)
- Bulk complete/delete/move after multi-select
- View by date (navigate to previous/next day)
- Weekly view (7-day progress summary)
- Carry over yesterday's incomplete items

## AI Assistance

- Suggest todo priorities
- Categorize and group todos
- Analyze completion patterns
- Daily/weekly planning assistant
- Identify recurring todo patterns

## MCP Tools

Use the `query_db` tool when you need to query or modify data. The `{chat_id}` placeholder is substituted automatically.

- Query: `query_db("SELECT * FROM todos WHERE chat_id = {chat_id} AND date = '2026-03-22'")`
- Mark complete: `query_db("UPDATE todos SET done = 1 WHERE id = 5 AND chat_id = {chat_id}")`
- Delete: `query_db("DELETE FROM todos WHERE id = 5 AND chat_id = {chat_id}")`
- Inspect table structure: `db_schema("todos")`

## Constraints

- Date-based management (date column)
- Isolated per user (chat_id)
- Todo list is organized in daily units
