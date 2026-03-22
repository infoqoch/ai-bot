# Google Calendar

Plugin for managing calendar events via the Google Calendar API.

## External API

Google Calendar API (service account authentication). CRUD operations are performed directly on Google servers — no DB tables.

### CalendarEvent Structure

- `id`: Google event ID
- `summary`: Event title
- `start` / `end`: Start/end time (datetime)
- `location`: Location (optional)
- `description`: Description (optional)
- `all_day`: Whether it is an all-day event

## Features

- View today's events (daily hub view)
- Date navigation (previous/next, calendar grid)
- Add events (date → time → title input)
- Add all-day events
- Edit events (title, date/time)
- Delete events
- Morning briefing schedule

## AI Assistance

- Detect event conflicts and suggest adjustments
- Optimize daily/weekly schedule
- Time management advice based on events
- Analyze recurring event patterns
- Identify free time and suggest how to use it

## Response Format Rules

### Prohibited

- Do not render a calendar grid (monthly calendar layout) in a `<pre>` block — fixed-width alignment breaks in Telegram.
- Do not use tags unsupported by Telegram: `<table>`, `<div>`, `<span>`, etc.
- Do not use Markdown syntax (`**bold**`, `*italic*`, `` `code` ``). Always use HTML tags.
- Do not attach markers (`*`, `>`, `[ ]`, etc.) to dates that would break alignment.

### Date/Time Format

- Date: `M/D (weekday)` — e.g., `3/22 (Sat)`
- Time: `HH:MM` 24-hour — e.g., `09:00`, `14:30`
- Duration: `HH:MM-HH:MM` — e.g., `14:00-15:30`
- All-day events: display as `All day`

### Event List Format

Group by date and display as a list:

```
📅 3/22 (Sat)
• 09:00 Team meeting
• 14:00-15:30 Design review
• All day — Holiday

📅 3/23 (Sun)
• No events
```

### Response Structure by Question Type

| Question | Response Structure |
|----------|--------------------|
| "Today's/tomorrow's events" | Sorted by time; note conflicts explicitly |
| "This week's events" | Grouped by date; days with no events may be omitted; max 7 days |
| "This month's events" | Grouped by date; show only days with events |
| "Schedule analysis/advice" | Summarize relevant events first, then provide analysis/advice |

### Allowed HTML Tags

- `<b>` for titles and date emphasis
- `<i>` for supplementary information
- `<code>` for fixed-width text such as times and IDs

## MCP Tools (when available)

When MCP tools are active, you can query or create calendar data directly using the tools below.
Use the tools instead of context data when you need events for a specific period.

- `calendar_list_events(start_date, end_date)`: List events for a date range (YYYY-MM-DD format)
- `calendar_create_event(summary, start, all_day)`: Create a new event (start in YYYY-MM-DDTHH:MM format)

## Constraints

- Requires Google service account configuration (GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_CALENDAR_ID)
- Unavailable if not configured
- Real-time API calls
