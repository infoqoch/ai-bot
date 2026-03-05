"""Message service - message processing business logic."""

import asyncio
from typing import TYPE_CHECKING, Optional

from src.logging_config import logger

if TYPE_CHECKING:
    from src.claude.client import ClaudeClient
    from src.services.session_service import SessionService
    from src.plugins.loader import PluginLoader


class MessageService:
    """Message processing service.

    Handles message routing and processing:
    - Plugin processing
    - Claude chat
    - Response formatting
    """

    def __init__(
        self,
        session_service: "SessionService",
        claude_client: "ClaudeClient",
        plugin_loader: Optional["PluginLoader"] = None,
    ):
        self._sessions = session_service
        self._claude = claude_client
        self._plugins = plugin_loader

    async def process_with_plugin(self, message: str, chat_id: int) -> Optional[dict]:
        """Try to process message with plugins.

        Returns:
            Plugin result dict if handled, None if not handled
        """
        if not self._plugins:
            return None

        try:
            result = await self._plugins.process_message(message, chat_id)
            if result.handled:
                return {
                    "handled": True,
                    "response": result.response,
                    "reply_markup": result.reply_markup,
                    "processor": f"plugin:{result.plugin_name}" if result.plugin_name else "plugin",
                }
        except Exception as e:
            logger.warning(f"Plugin processing error: {e}")

        return None

    async def process_with_claude(
        self,
        message: str,
        session_id: str,
        model: str = "sonnet",
        cwd: Optional[str] = None,
    ) -> str:
        """Process message with Claude.

        Returns:
            Claude response text
        """
        response = await self._claude.chat(
            message=message,
            session_id=session_id,
            model=model,
            cwd=cwd,
        )
        return response

    async def create_session_and_chat(
        self,
        user_id: str,
        message: str,
        model: str = "sonnet",
        cwd: Optional[str] = None,
    ) -> tuple[str, str]:
        """Create new Claude session and send first message.

        Returns:
            (session_id, response)
        """
        session_id = await self._claude.create_session(
            model=model,
            cwd=cwd,
        )

        if not session_id:
            raise RuntimeError("Failed to create Claude session")

        response = await self._claude.chat(
            message=message,
            session_id=session_id,
            model=model,
            cwd=cwd,
        )

        return session_id, response

    def record_message(
        self,
        session_id: str,
        message: str,
        processor: str = "claude"
    ) -> None:
        """Record message to session history."""
        self._sessions.add_message(
            session_id=session_id,
            message=message,
            processed=True,
            processor=processor,
        )
