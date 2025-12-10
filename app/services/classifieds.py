from __future__ import annotations
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.classifieds import Listing
from ..models.user import User
from ..services.users import ensure_user_from_tg

# Создать объявление (уходит в модерацию)
def create_listing(db: Session, tg_user: Dict[str, Any], payload: Dict[str, Any]) -> Listing:
    u: User = ensure_user_from_tg(db, tg_user)

    title = (payload.get("title") or "").strip()
    if not title:
        raise ValueError("Укажите заголовок")
    description = (payload.get("description") or "").strip() or None
    photo_url = (payload.get("photo_url") or "").strip() or None
    price_raw = payload.get("price")
    price = int(price_raw) if (price_raw not in (None, "")) else None
    if price is not None and price < 0:
        raise ValueError("Цена должна быть положительной")

    l = Listing(
        user_id=u.id,
        owner_tg_id=u.telegram_id,
        title=title,
        description=description,
        photo_url=photo_url,
        price=price,
        approved=False,
        rejected=False,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l

# Публичные (одобрено)
def list_public(db: Session, limit: int = 100) -> List[Listing]:
    return db.execute(
        select(Listing).where(Listing.approved.is_(True), Listing.rejected.is_(False))
        .order_by(Listing.id.desc()).limit(limit)
    ).scalars().all()

# Мои (любые)
def list_my(db: Session, tg_user) -> List[Listing]:
    u: User = ensure_user_from_tg(db, tg_user)
    return db.execute(
        select(Listing).where(Listing.user_id == u.id).order_by(Listing.id.desc())
    ).scalars().all()

# ---- Админ ----
def admin_list_pending(db: Session) -> List[Listing]:
    return db.execute(
        select(Listing).where(Listing.approved.is_(False), Listing.rejected.is_(False)).order_by(Listing.id.asc())
    ).scalars().all()

def admin_approve(db: Session, listing_id: int) -> Listing:
    l = db.get(Listing, listing_id)
    if not l: raise LookupError("Объявление не найдено")
    l.approved, l.rejected = True, False
    db.commit(); db.refresh(l)
    return l

def admin_reject(db: Session, listing_id: int) -> Listing:
    l = db.get(Listing, listing_id)
    if not l: raise LookupError("Объявление не найдено")
    l.approved, l.rejected = False, True
    db.commit(); db.refresh(l)
    return l