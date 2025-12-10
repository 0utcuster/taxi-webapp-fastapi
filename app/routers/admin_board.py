from __future__ import annotations

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db import get_db
from ..models.classifieds import Listing  # <-- фикс: используем Listing

router = APIRouter(tags=["board-admin"])

# ---------- HTML (без проверки админа, как просил) ----------
@router.get("/board/moderation")
def board_moderation_page(request: Request):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse("admin_board.html", {"request": request, "back_href": "/dashboard"})

# ---------- API (без ensure_is_admin) ----------
@router.get("/api/board/moderation/pending")
def api_board_pending(db: Session = Depends(get_db), limit: int = 200):
    rows = db.execute(
        select(Listing).where(Listing.approved.is_(False), Listing.rejected.is_(False)).order_by(Listing.id.asc()).limit(limit)
    ).scalars().all()
    items = []
    for it in rows:
        items.append({
            "id": it.id,
            "title": it.title,
            "description": it.description,
            "price": it.price,
            "photo_url": it.photo_url,
            "phone": it.phone,
            "created_at": (it.created_at.isoformat() if it.created_at else None),
        })
    return {"ok": True, "items": items}

@router.post("/api/board/moderation/{listing_id}/approve")
def api_board_approve(listing_id: int, db: Session = Depends(get_db)):
    it = db.get(Listing, listing_id)
    if not it:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    it.approved = True
    it.rejected = False
    db.commit()
    return {"ok": True, "id": it.id, "approved": True}

@router.post("/api/board/moderation/{listing_id}/reject")
def api_board_reject(listing_id: int, db: Session = Depends(get_db)):
    it = db.get(Listing, listing_id)
    if not it:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    it.approved = False
    it.rejected = True
    db.commit()
    return {"ok": True, "id": it.id, "rejected": True}