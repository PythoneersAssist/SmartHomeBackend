"""
Pydantic models for Gemini chat interactions.
"""
from typing import Any
from pydantic import BaseModel


class ChatMessage(BaseModel):
    """Represents a single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """WebSocket chat request from client."""
    message: str


class ChatResponse(BaseModel):
    """WebSocket chat response to client."""
    role: str  # "assistant"
    content: str
    function_calls: list[dict[str, Any]] | None = None  # Functions executed by Gemini


class FunctionCall(BaseModel):
    """Represents a function call from Gemini."""
    name: str
    args: dict[str, Any]
