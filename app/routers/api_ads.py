from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..deps import get_current_tg_user
from ..models.ad import Ad
from ..models.user import User

router = APIRouter(prefix="/api/ads", tags=["ads"])

@router.post("")
def create_ad(payload: dict, tg_user=Depends(get_current_tg_user), db: Session = Depends(get_db)):
    title = payload.get("title")
    if not title:
        raise HTTPException(400, "title required")
    u = db.execute(select(User).where(User.tg_id==tg_user["id"])).scalar_one_or_none()
    if not u:
        u = User(tg_id=tg_user["id"], first_name=tg_user.get("first_name"),
                 last_name=tg_user.get("last_name"), username=tg_user.get("username"),
                 photo_url=tg_user.get("photo_url"))
        db.add(u); db.flush()
    ad = Ad(author_id=u.id, title=title, description=payload.get("description"), image_url=payload.get("image_url"), category=payload.get("category"))
    db.add(ad); db.commit(); db.refresh(ad)
    return {"ok": True, "ad_id": ad.id}

@router.get("")
def list_ads(db: Session = Depends(get_db)):
    rows = db.execute(select(Ad).order_by(Ad.id.desc())).scalars().all()
    return {"ok": True, "items": [
        {"id": x.id, "title": x.title, "desc": x.description, "img": x.image_url, "cat": x.category} for x in rows
    ]}