# app/deps.py
from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .db import get_db
from .auth.telegram import verify_webapp_init_data
from .config import settings
from .models.user import User
from .services.users import ensure_user_from_tg as _ensure_user_from_tg


# ------------------ Telegram WebApp session ------------------

def _save_tg_user_to_session(request: Request, data: dict) -> dict:
    u = data.get("user") or {}
    tg_user = {
        "id": u.get("id"),
        "first_name": u.get("first_name"),
        "last_name": u.get("last_name"),
        "username": u.get("username"),
        "photo_url": u.get("photo_url"),
    }
    request.session["tg_user"] = tg_user
    return tg_user


def get_current_tg_user(
    request: Request,
    x_tg_init_data: Optional[str] = Header(None, alias="X-Tg-Init-Data"),
) -> dict:
    # 1) уже есть в сессии
    sess = getattr(request, "session", None) or {}
    user = sess.get("tg_user")
    if user:
        return user

    # 2) пришло initData — проверим подпись и сохраним
    if x_tg_init_data:
        data = verify_webapp_init_data(x_tg_init_data, settings.BOT_TOKEN or "")
        if data and "user" in data:
            return _save_tg_user_to_session(request, data)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Open via Telegram WebApp (no session)",
    )


# ------------------ Users helpers ------------------

def ensure_user_from_tg(db: Session, tg_user: dict) -> User:
    return _ensure_user_from_tg(db, tg_user)


# ------------------ Admin guard ------------------

# список админов из ENV: ADMIN_TG_IDS="12345, 67890"
ADMIN_TG_IDS: set[int] = set()
_env_val = os.getenv("ADMIN_TG_IDS", "").replace(",", " ").split()
for _v in _env_val:
    _v = _v.strip()
    if _v.isdigit():
        ADMIN_TG_IDS.add(int(_v))


def ensure_is_admin(
    tg_user: dict = Depends(get_current_tg_user),
    db: Session = Depends(get_db),
) -> User:
    """
    Пропускает, если:
      - у пользователя user.is_admin == True, ИЛИ
      - его telegram_id содержится в ADMIN_TG_IDS (из переменной окружения).
    Иначе — 403.
    """
    user: User = ensure_user_from_tg(db, tg_user)

    is_admin_flag = bool(getattr(user, "is_admin", False))
    in_whitelist = getattr(user, "telegram_id", None) in ADMIN_TG_IDS

    if is_admin_flag or in_whitelist:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )