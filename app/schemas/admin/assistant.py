from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AssistantChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantChatRequest(BaseModel):
    messages: list[AssistantChatMessage] = Field(min_length=1)
    conversation_id: int | None = None
    title: str | None = Field(default=None, max_length=120)
    mode: Literal["hybrid", "openai", "deepseek"] | None = None
    context: str | None = Field(default=None, max_length=2000)
    include_snapshot: bool = True


class AssistantChatResponse(BaseModel):
    conversation_id: int
    reply: str
    provider: str
    usage: dict | None = None
    truncated: bool = False
    error: str | None = None


class AssistantConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    context: str | None = Field(default=None, max_length=2000)
    mode: Literal["hybrid", "openai", "deepseek"] | None = None


class AssistantConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    context: str | None = Field(default=None, max_length=2000)
    mode: Literal["hybrid", "openai", "deepseek"] | None = None


class AssistantConversationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    admin_id: int
    title: str | None = None
    context: str | None = None
    mode: str
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssistantMessageOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    conversation_id: int
    role: str
    content: str
    provider: str | None = None
    usage_json: dict | None = None
    truncated: bool
    error: str | None = None
    created_at: datetime | None = None


class AssistantActionCreate(BaseModel):
    conversation_id: int | None = None
    action_type: str = Field(min_length=1, max_length=50)
    summary: str | None = Field(default=None, max_length=255)
    payload: dict | None = None


class AssistantActionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    conversation_id: int | None = None
    admin_id: int
    status: str
    action_type: str
    summary: str | None = None
    payload_json: dict | None = None
    result_json: dict | None = None
    error: str | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
