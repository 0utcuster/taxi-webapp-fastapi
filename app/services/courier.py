from __future__ import annotations

from typing import Dict, Any, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.courier import CourierProfile
from ..models.user import User
from ..services.users import ensure_user_from_tg as _ensure_user_from_tg


# ---- общие хелперы ----

def ensure_user_from_tg(db: Session, tg_user: Dict[str, Any]) -> User:
    """Создаёт/возвращает User по данным Telegram WebApp (аналогично драйверам)."""
    return _ensure_user_from_tg(db, tg_user)


def _dedupe_profiles(db: Session, user_id: int) -> CourierProfile | None:
    """
    Если по ошибке есть несколько CourierProfile для одного user_id,
    оставляем самый новый (по id), остальные удаляем.
    """
    rows: List[CourierProfile] = (
        db.execute(
            select(CourierProfile)
            .where(CourierProfile.user_id == user_id)
            .order_by(CourierProfile.id.desc())
        ).scalars().all()
    )
    if not rows:
        return None
    keep = rows[0]
    extras = rows[1:]
    if extras:
        for e in extras:
            db.delete(e)
        db.commit()
    return keep


def get_or_create_profile(db: Session, tg_user: Dict[str, Any]) -> CourierProfile:
    """
    Возвращает профиль курьера; если нет — создаёт.
    Гарантирует 1 запись на одного user_id (дедупликация при необходимости).
    """
    u = ensure_user_from_tg(db, tg_user)

    # Берём первый (самый новый) профиль, если есть, без scalar_one_or_none (чтобы не падать от дублей)
    p = db.execute(
        select(CourierProfile)
        .where(CourierProfile.user_id == u.id)
        .order_by(CourierProfile.id.desc())
        .limit(1)
    ).scalars().first()

    if p:
        # На всякий случай подчистим возможные дубли
        _dedupe_profiles(db, u.id)
        return p

    # Создаём новый
    p = CourierProfile(
        user_id=u.id,
        full_name=None,
        phone=None,
        notes=None,
        approved=False,
        rejected=False,
        active=False,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def submit_profile(db: Session, tg_user: Dict[str, Any], payload: Dict[str, Any]) -> CourierProfile:
    """
    Обновление анкеты курьера (ФИО/телефон/заметки) и отправка на модерацию.
    При отправке статус всегда: approved=False, rejected=False, active=False.
    """
    p = get_or_create_profile(db, tg_user)

    full_name = (payload.get("full_name") or "").strip() or None
    phone     = (payload.get("phone") or "").strip() or None
    notes     = (payload.get("notes") or "").strip() or None

    p.full_name = full_name
    p.phone = phone
    p.notes = notes

    # новая заявка на модерацию
    p.approved = False
    p.rejected = False
    p.active = False

    db.commit()
    db.refresh(p)
    return p


def set_active(db: Session, tg_user: Dict[str, Any], value: bool) -> CourierProfile:
    """
    Включение/выключение видимости курьера в ленте.
    Разрешено только если профиль одобрен и не отклонён.
    """
    p = get_or_create_profile(db, tg_user)

    if not p.approved:
        raise PermissionError("Профиль ещё не одобрен администратором.")
    if p.rejected:
        raise PermissionError("Профиль отклонён администратором.")

    p.active = bool(value)
    db.commit()
    db.refresh(p)
    return p


def ensure_courier_allowed(db: Session, tg_user: Dict[str, Any], need_active: bool = False) -> CourierProfile:
    """
    Гейт для курьерских действий: профиль должен быть одобрен (и не отклонён).
    Если need_active=True — курьер должен быть активен.
    """
    p = get_or_create_profile(db, tg_user)

    if not p.approved:
        raise PermissionError("Профиль курьера ещё не одобрен.")
    if p.rejected:
        raise PermissionError("Профиль курьера отклонён.")
    if need_active and not p.active:
        raise PermissionError("Включите статус 'Активен' в профиле курьера.")

    return p


# ---- админские действия ----

def admin_list_pending_couriers(db: Session) -> list[CourierProfile]:
    """
    Список профилей курьеров на модерации (approved=False и rejected=False).
    """
    rows = db.execute(
        select(CourierProfile).where(
            CourierProfile.approved.is_(False),
            CourierProfile.rejected.is_(False),
        ).order_by(CourierProfile.id.desc())
    ).scalars().all()
    return rows


def admin_approve_courier(db: Session, user_id: int) -> CourierProfile:
    """
    Одобрить профиль: approved=True, rejected=False. Active не трогаем (по умолчанию False).
    """
    p = db.execute(
        select(CourierProfile).where(CourierProfile.user_id == user_id)
    ).scalars().first()
    if not p:
        raise LookupError("Профиль курьера не найден")

    p.approved = True
    p.rejected = False
    db.commit()
    db.refresh(p)
    return p


def admin_reject_courier(db: Session, user_id: int) -> CourierProfile:
    """
    Отклонить профиль: approved=False, rejected=True, active=False.
    """
    p = db.execute(
        select(CourierProfile).where(CourierProfile.user_id == user_id)
    ).scalars().first()
    if not p:
        raise LookupError("Профиль курьера не найден")

    p.approved = False
    p.rejected = True
    p.active = False
    db.commit()
    db.refresh(p)
    return p