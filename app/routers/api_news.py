# app/routers/api_news.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..deps import get_current_tg_user
from ..models.news import NewsPost
from ..models.user import User

router = APIRouter(prefix="/api/news", tags=["news"])

@router.get("")
def list_news(db: Session = Depends(get_db)):
    rows = db.execute(
        select(NewsPost).order_by(NewsPost.pinned.desc(), NewsPost.id.desc()).limit(100)
    ).scalars().all()
    return {"ok": True, "items": [
        {"id": n.id, "title": n.title, "body": n.body, "img": n.image_url, "pinned": n.pinned,
         "author": n.author_name, "created_at": n.created_at.isoformat()} for n in rows
    ]}

@router.post("")
def add_news(payload: dict, tg_user=Depends(get_current_tg_user), db: Session = Depends(get_db)):
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title required")

    u = db.execute(select(User).where(User.tg_id == tg_user["id"])).scalar_one_or_none()
    if not u:
        u = User(
            tg_id=tg_user["id"],
            first_name=tg_user.get("first_name"),
            last_name=tg_user.get("last_name"),
            username=tg_user.get("username"),
            photo_url=tg_user.get("photo_url"),
        )
        db.add(u); db.flush()

    display_name = " ".join(filter(None, [tg_user.get("first_name"), tg_user.get("last_name")])) or \
                   (f"@{tg_user.get('username')}" if tg_user.get("username") else f"ID {tg_user.get('id')}")

    post = NewsPost(
        author_id=u.id,
        author_tg_id=tg_user["id"],
        author_name=display_name,
        title=title,
        body=payload.get("body") or None,
        image_url=payload.get("image_url") or None,
        pinned=bool(payload.get("pinned", False)),
    )
    db.add(post); db.commit(); db.refresh(post)
    return {"ok": True, "id": post.id}