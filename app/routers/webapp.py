# app/routers/webapp.py
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import JSONResponse
from ..auth.telegram import verify_webapp_init_data
from ..config import settings

router = APIRouter(tags=["webapp"])

@router.post("/api/tg/session")
def tg_session(request: Request, init_data: str = Form(...)):
    """
    Принимает Telegram.WebApp.initData, проверяет подпись и сохраняет профиль в сессию.
    """
    data = verify_webapp_init_data(init_data, settings.BOT_TOKEN or "")
    if not data or "user" not in data:
        raise HTTPException(status_code=400, detail="invalid initData")

    u = data["user"] or {}
    request.session["tg_user"] = {
        "id": u.get("id"),
        "first_name": u.get("first_name"),
        "last_name": u.get("last_name"),
        "username": u.get("username"),
        "photo_url": u.get("photo_url"),
    }
    # важно: ответ без кэша
    resp = JSONResponse({"ok": True})
    resp.headers["Cache-Control"] = "no-store"
    return resp

@router.get("/api/me")
def me(request: Request):
    return {"ok": True, "user": request.session.get("tg_user"), "has_cookie": bool(request.cookies)}