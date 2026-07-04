from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlalchemy.orm import Session

from modules.database import get_db
from modules.models import Settings as SettingsModel
from modules.sse_manager import sse_manager

router = APIRouter(prefix="/api", tags=["settings"])


# ── Schemas ──────────────────────────────────────────────

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

class SettingsUpdate(CamelModel):
    openai_key: str | None = None
    bot_name: str | None = None
    welcome_message: str | None = None
    accent_color: str | None = None
    language: str | None = None
    system_prompt: str | None = None
    target_url: str | None = None
    model: str | None = None
    crawler_settings: str | None = None
    chat_bg_color: str | None = None
    user_bubble_bg: str | None = None
    user_text_color: str | None = None
    bot_bubble_bg: str | None = None
    bot_text_color: str | None = None


# ── Helpers ───────────────────────────────────────────────

def mask_key(key: str) -> str:
    if not key:
        return ""
    return "••••••••" + key[-4:]


def settings_to_dict(s: SettingsModel, mask: bool = True) -> dict:
    return {
        "id": s.id,
        "openaiKey": mask_key(s.openai_key) if mask else s.openai_key,
        "botName": s.bot_name,
        "welcomeMessage": s.welcome_message,
        "accentColor": s.accent_color,
        "language": s.language,
        "systemPrompt": s.system_prompt,
        "targetUrl": s.target_url,
        "model": s.model,
        "crawlerSettings": s.crawler_settings,
        "chatBgColor": getattr(s, "chat_bg_color", "#f8f9fb") or "#f8f9fb",
        "userBubbleBg": getattr(s, "user_bubble_bg", "#01696f") or "#01696f",
        "userTextColor": getattr(s, "user_text_color", "#ffffff") or "#ffffff",
        "botBubbleBg": getattr(s, "bot_bubble_bg", "#ffffff") or "#ffffff",
        "botTextColor": getattr(s, "bot_text_color", "#222222") or "#222222",
    }


# ── Routes ────────────────────────────────────────────────

@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    s = db.query(SettingsModel).first()
    if not s:
        raise HTTPException(status_code=500, detail="Settings not found")
    return settings_to_dict(s)


@router.patch("/settings")
async def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    s = db.query(SettingsModel).first()
    if not s:
        raise HTTPException(status_code=500, detail="Settings not found")

    update_data = data.model_dump(exclude_none=True)

    if "openai_key" in update_data and update_data["openai_key"].startswith("••••"):
        update_data.pop("openai_key")

    if update_data.get("target_url", None) == "":
        update_data.pop("target_url")

    for field, value in update_data.items():
        setattr(s, field, value)

    db.commit()
    db.refresh(s)
    await sse_manager.broadcast("settings_updated", None)
    return settings_to_dict(s)
