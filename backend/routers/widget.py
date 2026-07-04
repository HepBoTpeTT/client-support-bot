from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from config import settings as app_settings
from modules.database import get_db
from modules.models import Settings as SettingsModel

router = APIRouter(tags=["widget"])

@router.get("/api/widget-config")
def get_widget_config(db: Session = Depends(get_db)):
    s = db.query(SettingsModel).first()
    return {
        "bot_name":        s.bot_name        if s else "САПОРТУС",
        "accent_color":    s.accent_color    if s else "#01696f",
        "welcome_message": s.welcome_message if s else "Привет! Чем могу помочь?",
        "chat_bg_color":   s.chat_bg_color   if s else "#f8f9fb",
        "user_bubble_bg":  s.user_bubble_bg  if s else "#01696f",
        "user_text_color": s.user_text_color if s else "#ffffff",
        "bot_bubble_bg":   s.bot_bubble_bg   if s else "#ffffff",
        "bot_text_color":  s.bot_text_color  if s else "#222222",
    }

@router.get("/api/embed-code")
def get_embed_code(db: Session = Depends(get_db)):
    s = db.query(SettingsModel).first()
    base_url = app_settings.public_base_url.rstrip("/")

    js_snippet = (
        f'<!-- Site Assistant Widget : JS -->\n'
        f'<script\n'
        f'    src="{base_url}/widget-static/saportus-widget.js"\n'
        f'    data-base-url="{base_url}"\n'
        f'></script>'
    )

    iframe_snippet = (
        f'<!-- Site Assistant Widget : iframe -->\n'
        f'<iframe\n'
        f'    src="{base_url}/chat-widget-html?baseUrl={quote(base_url, safe="")}"\n'
        f'    style="border:none; background:transparent; max-width:450px; max-height:660px; '
        f'height:100vh; width:100vw; position:fixed; bottom:0; right:0;"\n'
        f'    title="{s.bot_name if s else "Помощник"}"\n'
        f'    onload="const f=this; const s=()=>{{f.contentWindow.postMessage({{type:\'RESIZE\',w:window.innerWidth}},\'*\')}}; '
        f'window.addEventListener(\'resize\',s); '
        f'const t=setInterval(()=>{{if(f.contentWindow){{s();clearInterval(t)}}}},200);">\n'
        f'</iframe>'
    )

    return {"jsSnippet": js_snippet, "iframeSnippet": iframe_snippet}
