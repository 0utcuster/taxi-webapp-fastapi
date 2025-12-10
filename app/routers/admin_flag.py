# app/routers/admin_flag.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import get_current_tg_user
from ..services.users import ensure_user_from_tg
from ..admin.security import is_admin_user

router = APIRouter(tags=["meta"])

@router.get("/api/is_admin")
def api_is_admin(tg_user=Depends(get_current_tg_user), db: Session = Depends(get_db)):
    u = ensure_user_from_tg(db, tg_user)
    return {"ok": True, "is_admin": bool(is_admin_user(u))}