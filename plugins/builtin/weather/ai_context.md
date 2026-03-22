# Weather

Plugin for querying weather information using the Open-Meteo API.

## DB Schema

```sql
weather_locations (
    chat_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,        -- Location name
    country TEXT,              -- Country
    lat REAL NOT NULL,         -- Latitude
    lon REAL NOT NULL,         -- Longitude
    updated_at TEXT
)
```

## Features

- Two-level location selection (province/metro → city/county)
- Current weather (temperature, humidity, wind speed, conditions)
- 3-day forecast (low/high temperatures)
- Save location (remembers last queried location)

## AI Assistance

- Clothing and activity recommendations based on weather
- Weather reference when planning trips
- Weekly weather trend analysis
- Schedule adjustment suggestions based on weather conditions

## MCP Tools

Query saved location: `query_db("SELECT * FROM weather_locations WHERE chat_id = {chat_id}")`

Weather data is provided by a real-time API, so current conditions cannot be obtained via DB query. Only location information can be queried.

## Constraints

- Only one saved location per user
- Based on the Open-Meteo API (Korean city CSV mapping)
- Real-time API calls (no cache)
