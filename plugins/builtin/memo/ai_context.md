# Memo Management

Plugin for saving and managing simple text memos.

## DB Schema

```sql
memos (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    content TEXT NOT NULL,     -- Memo content
    created_at TEXT
)
```

## Features

- Add memos
- Delete memos (individually or via multi-select)
- View memo list
- Maximum of 30 memos

## AI Assistance

- Categorize memos by content
- Group and summarize related memos
- Search memos by topic
- Suggest memo organization and structuring

## MCP Tools

Use the `query_db` tool when you need to query or modify data. The `{chat_id}` placeholder is substituted automatically.

- List all: `query_db("SELECT * FROM memos WHERE chat_id = {chat_id}")`
- Keyword search: `query_db("SELECT * FROM memos WHERE chat_id = {chat_id} AND content LIKE '%keyword%'")`
- Delete: `query_db("DELETE FROM memos WHERE id = 3 AND chat_id = {chat_id}")`
- Inspect table structure: `db_schema("memos")`

## Constraints

- Isolated per user (chat_id)
- Maximum of 30 memos stored
- Managed as a single flat list with no date separation
