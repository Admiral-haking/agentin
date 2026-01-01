from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Button(BaseModel):
    type: Literal["web_url", "postback"] = "web_url"
    title: str
    url: str | None = None
    payload: str | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "Button":
        if self.type == "web_url" and not self.url:
            raise ValueError("web_url buttons require url")
        if self.type == "postback" and not self.payload:
            raise ValueError("postback buttons require payload")
        return self


class QuickReplyOption(BaseModel):
    title: str
    payload: str


class TemplateElement(BaseModel):
    title: str
    subtitle: str | None = None
    image_url: str | None = None
    buttons: list[Button] = Field(default_factory=list)


class OutboundPlan(BaseModel):
    type: Literal[
        "text",
        "button",
        "quick_reply",
        "generic_template",
        "photo",
        "video",
        "audio",
    ]
    text: str | None = None
    image_url: str | None = None
    video_url: str | None = None
    audio_url: str | None = None
    buttons: list[Button] = Field(default_factory=list)
    quick_replies: list[QuickReplyOption] = Field(default_factory=list)
    elements: list[TemplateElement] = Field(default_factory=list)
