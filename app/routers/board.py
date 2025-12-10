from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db import get_db
from ..deps import get_current_tg_user
from ..models.user import User
from ..models.classifieds import Listing  # <-- фикс: используем Listing

router = APIRouter(tags=["board"])

# ---------- HTML ----------
@router.get("/board")
def board_page(request: Request):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse("board.html", {"request": request, "back_href": "/dashboard"})

# ---------- helpers ----------
def ensure_user_from_tg(db: Session, tg_user: dict) -> User:
    # если у тебя уже есть такая функция в services.users — можешь импортнуть её.
    # здесь — компактная версия
    tg_id = int(tg_user.get("id"))
    u = db.execute(select(User).where(User.telegram_id == tg_id)).scalar_one_or_none()
    if u:
        return u
    u = User(telegram_id=tg_id, username=tg_user.get("username"), name=tg_user.get("first_name"))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

# ---------- API ----------
@router.get("/api/board/listings")
def api_board_public(db: Session = Depends(get_db), limit: int = 100):
    rows = db.execute(
        select(Listing).where(Listing.approved.is_(True), Listing.rejected.is_(False)).order_by(Listing.id.desc()).limit(limit)
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
            "created_at": (it.created_at.isoformat() if it.created_at else None)
        })
    return {"ok": True, "items": items}

@router.get("/api/board/my")
def api_board_my(tg_user=Depends(get_current_tg_user), db: Session = Depends(get_db)):
    u = ensure_user_from_tg(db, tg_user)
    rows = db.execute(
        select(Listing).where(Listing.user_id == u.id).order_by(Listing.id.desc())
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
            "approved": it.approved,
            "rejected": it.rejected,
        })
    return {"ok": True, "items": items}

@router.post("/api/board/listings")
def api_board_create(
    payload: dict,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)

    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Укажите заголовок")

    price = payload.get("price")
    price = int(price) if price not in (None, "") else None

    phone = (payload.get("phone") or "").strip() or None

    it = Listing(
        user_id=u.id,
        owner_tg_id=str(u.telegram_id) if u.telegram_id else None,
        title=title,
        description=(payload.get("description") or None),
        price=price,
        photo_url=(payload.get("photo_url") or None),
        phone=phone,
        approved=False,
        rejected=False,
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return {"ok": True, "id": it.id}

@router.delete("/api/board/listings/{listing_id}")
def api_board_delete(
    listing_id: int,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    it = db.get(Listing, listing_id)
    if not it:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    if it.user_id != u.id:
        raise HTTPException(status_code=403, detail="Можно удалять только свои объявления")

    db.delete(it)
    db.commit()
    return {"ok": True, "deleted": listing_id}