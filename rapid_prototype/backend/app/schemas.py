from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    created_at: datetime
    settings: dict[str, Any] = {}

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SettingsUpdate(BaseModel):
    settings: dict[str, Any]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None
    model: str | None = None
    source_filter: str | None = None


class SourceOut(BaseModel):
    document_id: int
    filename: str
    modality: str
    source: str
    excerpt: str
    score: float


class ChatResponse(BaseModel):
    conversation_id: int
    answer: str
    sources: list[SourceOut]
    model: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float


class ConnectorConnectRequest(BaseModel):
    account_email: str | None = None
