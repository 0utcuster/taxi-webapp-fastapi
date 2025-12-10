# app/routers/ui.py
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

# Надёжно укажем абсолютный путь к templates/, чтобы не ловить TemplateNotFound
TEMPLATES_DIR = Path(__file__).resolve().parents[1].parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/", include_in_schema=False)
def index():
    # Если нужен лендинг — верните TemplateResponse("index.html", {...})
    return RedirectResponse("/dashboard", status_code=307)

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    blocks = [
        {"icon": "🚕", "title": "Такси", "desc": "Создать поездку / принять заказ", "href": "/taxi"},
        {"icon": "📦", "title": "Доставка", "desc": "Заказать / выполнить доставку", "href": "/delivery"},
        {"icon": "📢", "title": "Объявления", "desc": "Куплю / Продам / Услуги", "href": "/ads"},
        {"icon": "ℹ️", "title": "Инфо", "desc": "Экстренные номера, автобусы, режимы", "href": "/info"},
    ]
    return templates.TemplateResponse("dashboard.html", {"request": request, "blocks": blocks})

@router.get("/profile", response_class=HTMLResponse)
def profile(request: Request):
    demo_user = {
        "first_name": "Demo",
        "last_name": "User",
        "username": "demo_user",
        "photo_url": "https://cdn-icons-png.flaticon.com/512/1946/1946429.png",
    }
    return templates.TemplateResponse("profile.html", {"request": request, "user": demo_user})

@router.get("/logout", include_in_schema=False)
def logout():
    resp = RedirectResponse("/dashboard", status_code=307)
    resp.delete_cookie("access_token")
    return resp

@router.get("/api/me")
def me(request: Request):
    return {"ok": True, "user": request.session.get("tg_user")}