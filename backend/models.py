from pydantic import BaseModel, Field, field_validator
import base64
import binascii
from typing import List, Any, Optional


class ConnectRequest(BaseModel):
    connection_string: str


class ConnectResponse(BaseModel):
    success: bool


class ImageAttachment(BaseModel):
    name: str = Field(max_length=200)
    mime_type: str
    data: str = Field(max_length=5_592_408)

    @field_validator("mime_type")
    @classmethod
    def supported_type(cls, value):
        if value not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError("Use PNG, JPEG, or WebP images")
        return value

    @field_validator("data")
    @classmethod
    def valid_image(cls, value, info):
        try:
            raw = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Invalid image encoding")
        if not raw or len(raw) > 4 * 1024 * 1024:
            raise ValueError("Images must be at most 4 MB each")
        mime = info.data.get("mime_type")
        matches = {
            "image/png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/jpeg": raw.startswith(b"\xff\xd8\xff"),
            "image/webp": raw.startswith(b"RIFF") and raw[8:12] == b"WEBP",
        }
        if not matches.get(mime):
            raise ValueError("Image contents do not match the declared file type")
        return value


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    images: List[ImageAttachment] = Field(default_factory=list, max_length=3)


class QueryStep(BaseModel):
    """One step in the agentic loop — a SQL statement and its outcome."""
    sql: str
    columns: List[str] = []
    rows: List[List[Any]] = []
    error: Optional[str] = None
    # How this step was executed:
    #   "auto"     — SELECT, run automatically
    #   "approved" — INSERT/UPDATE, user approved
    #   "rejected" — INSERT/UPDATE, user rejected (not run)
    #   "blocked"  — DROP/DELETE/etc., rejected server-side
    kind: str = "auto"


class ChatMessageResponse(BaseModel):
    """
    Returned by both POST /chat/message and POST /chat/execute.

    status == "done":
        reply            — the LLM's final answer text
        completed_steps  — all steps executed in this round

    status == "needs_approval":
        pending_sql      — the write SQL the LLM wants to run
        completed_steps  — SELECT steps that already ran before the pause
    """
    status: str               # "done" | "needs_approval"
    reply: str = ""
    pending_sql: str = ""
    completed_steps: List[QueryStep] = []


class ChatExecuteRequest(BaseModel):
    """Sent by the frontend after the user decides on a pending write query."""
    approved: bool
    sql: Optional[str] = None  # display-only; execution uses server-side pending SQL


class QueryRunRequest(BaseModel):
    sql: str


class QueryRunResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
