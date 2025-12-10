# app/admin/security.py
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import get_current_tg_user
from ..services.users import ensure_user_from_tg
from ..config import settings

def _parse_admin_ids() -> set[int]:
    ids: set[int] = set()
    # новое поле: несколько через запятую
    if settings.ADMIN_TG_IDS:
        for part in settings.ADMIN_TG_IDS.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                ids.add(int(part))
            except ValueError:
                pass
    # старое поле: одиночный id (на всякий случай поддержим)
    if settings.ADMIN_TG_ID:
        try:
            ids.add(int(settings.ADMIN_TG_ID))
        except ValueError:
            pass
    return ids

_ADMIN_IDS = _parse_admin_ids()

def is_admin_user(user) -> bool:
    """
    Админ — если:
    1) его Telegram ID есть в ADMIN_TG_IDS/ADMIN_TG_ID
    2) или в users.role == 'admin'
    """
    tg_ids = {getattr(user, "telegram_id", None), getattr(user, "tg_id", None)}
    if any((tid in _ADMIN_IDS) for tid in tg_ids if tid is not None):
        return True
    role = (getattr(user, "role", "") or "").lower()
    if role == "admin":
        return True
    return False

def require_admin(
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    if not is_admin_user(u):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return True