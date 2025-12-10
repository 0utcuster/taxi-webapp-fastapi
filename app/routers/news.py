# app/routers/news.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..deps import get_current_tg_user
from ..models.news import NewsPost
from ..services.users import ensure_user_from_tg

router = APIRouter(prefix="/news", tags=["news"])

@router.get("")
def news_page(request: Request):
    # отдаём страницу с новостями (если у тебя есть шаблон news.html)
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse("news.html", {"request": request, "back_href": "/dashboard"})

# API: список новостей
@router.get("/api")
def list_news(db: Session = Depends(get_db)):
    rows = db.execute(
        select(NewsPost).order_by(NewsPost.pinned.desc(), NewsPost.id.desc()).limit(100)
    ).scalars().all()
    return {"ok": True, "items": [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "img": n.image_url,
            "pinned": n.pinned,
            "author": n.author_name,
            "created_at": (n.created_at.isoformat() if n.created_at else None),
        } for n in rows
    ]}

# API: добавление новости
@router.post("/api")
def add_news(payload: dict, tg_user=Depends(get_current_tg_user), db: Session = Depends(get_db)):
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title required")
    body = (payload.get("body") or "").strip() or None
    image_url = (payload.get("image_url") or "").strip() or None
    pinned = bool(payload.get("pinned", False))

    u = ensure_user_from_tg(db, tg_user)
    display_name = u.display_name

    post = NewsPost(
        author_id=u.id,
        author_tg_id=int(tg_user["id"]),
        author_name=display_name,
        title=title,
        body=body,
        image_url=image_url,
        pinned=pinned,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"ok": True, "id": post.id}