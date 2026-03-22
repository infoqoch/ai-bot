"""MCP bridge server - exposes plugin ToolSpecs as MCP tools for Claude CLI."""

import asyncio
import inspect
import sys
import os
from pathlib import Path

# Add project root to path
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env for environment variables (GOOGLE_SERVICE_ACCOUNT_FILE, etc.)
from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bot-plugins")

_TYPE_MAP = {
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": float,
}


def _make_tool_function(name: str, handler, parameters: dict):
    """Build a function with a proper typed signature so FastMCP generates the correct schema."""
    props = parameters.get("properties", {})
    required = set(parameters.get("required", []))

    params = []
    for param_name, schema in props.items():
        annotation = _TYPE_MAP.get(schema.get("type", "string"), str)
        if param_name in required:
            p = inspect.Parameter(param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation)
        else:
            default = schema.get("default", None)
            p = inspect.Parameter(param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default, annotation=annotation)
        params.append(p)

    sig = inspect.Signature(params)

    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        if asyncio.iscoroutinefunction(handler):
            return asyncio.run(handler(**bound.arguments))
        return handler(**bound.arguments)

    wrapper.__signature__ = sig
    wrapper.__name__ = name
    return wrapper


def _register_plugins():
    """Load plugins and register their ToolSpecs as MCP tools."""
    from src.repository.database import get_connection
    from src.repository.repository import Repository
    from src.plugins.loader import PluginLoader

    db_path = _PROJECT_ROOT / os.getenv("BOT_DATA_DIR", ".data") / "bot.db"
    conn = get_connection(db_path)
    repo = Repository(conn)
    loader = PluginLoader(_PROJECT_ROOT, repository=repo)
    loader.load_all()

    for plugin in loader.plugins:
        for tool in plugin.get_tool_specs():
            fn = _make_tool_function(tool.name, tool.handler, tool.parameters)
            mcp.tool(name=tool.name, description=tool.description)(fn)


_register_plugins()

if __name__ == "__main__":
    mcp.run()
