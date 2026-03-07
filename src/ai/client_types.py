"""Common AI client response types."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol


class ChatError(Enum):
    """CLI chat error types."""

    TIMEOUT = "TIMEOUT"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    CLI_ERROR = "CLI_ERROR"


@dataclass
class ChatResponse:
    """Normalized CLI response."""

    text: str
    error: Optional[ChatError] = None
    session_id: Optional[str] = None

    def __iter__(self):
        """Support tuple unpacking used by existing call sites."""
        error_str = self.error.value if self.error else None
        return iter((self.text, error_str, self.session_id))


class AIClient(Protocol):
    """Protocol shared by Claude/Codex CLI wrappers."""

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> ChatResponse:
        """Send one message to the provider."""

