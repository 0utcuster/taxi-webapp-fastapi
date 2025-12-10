from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import date

from ..models.user import User
from ..models.taxi import TaxiVehicle
from ..models.driver import DriverProfile  # модель профиля водителя
from ..services.users import ensure_user_from_tg as _ensure_user_from_tg


def ensure_user_from_tg(db: Session, tg_user) -> User:
    return _ensure_user_from_tg(db, tg_user)


def get_or_create_profile(db: Session, tg_user) -> DriverProfile:
    u = ensure_user_from_tg(db, tg_user)
    p = db.execute(select(DriverProfile).where(DriverProfile.user_id == u.id)).scalar_one_or_none()
    if not p:
        p = DriverProfile(user_id=u.id, approved=False, rejected=False, active=False)
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


def submit_profile(db: Session, tg_user, payload: dict) -> DriverProfile:
    """
    Любая правка — снова на модерацию (approved=False, rejected=False).
    """
    u = ensure_user_from_tg(db, tg_user)
    p = get_or_create_profile(db, tg_user)

    p.full_name = (payload.get("full_name") or "").strip() or None
    p.phone = (payload.get("phone") or "").strip() or None
    p.license_number = (payload.get("license_number") or "").strip() or None
    lic_to = (payload.get("license_valid_to") or "").strip()
    p.license_valid_to = date.fromisoformat(lic_to) if lic_to else None
    p.notes = (payload.get("notes") or "").strip() or None

    p.approved = False
    p.rejected = False
    db.commit()
    db.refresh(p)
    return p


def upsert_vehicle(db: Session, tg_user, payload: dict) -> TaxiVehicle:
    """
    Любая правка — verified=False (снова на проверку авто).
    """
    u = ensure_user_from_tg(db, tg_user)
    v = db.execute(select(TaxiVehicle).where(TaxiVehicle.driver_id == u.id)).scalar_one_or_none()
    if not v:
        v = TaxiVehicle(driver_id=u.id)
        db.add(v)
        db.commit()
        db.refresh(v)

    v.make = (payload.get("make") or "").strip() or None
    v.model = (payload.get("model") or "").strip() or None
    v.color = (payload.get("color") or "").strip() or None
    v.plate = (payload.get("plate") or "").strip() or None
    seats = payload.get("seats")
    try:
        v.seats = int(seats) if seats not in (None, "") else None
    except Exception:
        v.seats = None
    v.photo_url = (payload.get("photo_url") or "").strip() or None

    v.verified = False
    db.commit()
    db.refresh(v)
    return v


def _has_vehicle_verified(db: Session, user_id: int) -> bool:
    v = db.execute(select(TaxiVehicle).where(TaxiVehicle.driver_id == user_id)).scalar_one_or_none()
    return bool(v and v.verified)


def ensure_driver_allowed(db: Session, tg_user, need_active: bool = True) -> DriverProfile:
    """
    Требования для работы водителем:
      - профиль approved=True
      - авто verified=True
      - если need_active=True, то profile.active=True
    """
    u = ensure_user_from_tg(db, tg_user)
    p = get_or_create_profile(db, tg_user)

    if not p.approved:
        raise PermissionError("Профиль водителя ещё не одобрен администратором.")
    if not _has_vehicle_verified(db, u.id):
        raise PermissionError("Автомобиль ещё не верифицирован администратором.")
    if need_active and not p.active:
        raise PermissionError("Водитель выключен. Включите видимость в ленте.")
    return p


def set_active(db: Session, tg_user, value: bool) -> DriverProfile:
    """
    Включить/выключить видимость. Включить можно только при одобренном профиле и верифицированном авто.
    """
    u = ensure_user_from_tg(db, tg_user)
    p = get_or_create_profile(db, tg_user)

    if value:
        if not p.approved:
            raise PermissionError("Нельзя включить: профиль не одобрен.")
        if not _has_vehicle_verified(db, u.id):
            raise PermissionError("Нельзя включить: авто не верифицировано.")
        p.active = True
    else:
        p.active = False

    db.commit()
    db.refresh(p)
    return p


# -------- Админ --------

def admin_list_pending(db: Session) -> dict:
    """
    Профили и авто, ожидающие модерации/верификации.
    """
    profiles = db.execute(
        select(DriverProfile).where(DriverProfile.approved.is_(False), DriverProfile.rejected.is_(False))
    ).scalars().all()
    vehicles = db.execute(
        select(TaxiVehicle).where(TaxiVehicle.verified.is_(False))
    ).scalars().all()
    return {"profiles": profiles, "vehicles": vehicles}


def admin_approve_profile(db: Session, user_id: int) -> DriverProfile:
    p = db.execute(select(DriverProfile).where(DriverProfile.user_id == user_id)).scalar_one_or_none()
    if not p:
        raise LookupError("Профиль не найден")
    p.approved = True
    p.rejected = False
    db.commit()
    db.refresh(p)
    return p


def admin_reject_profile(db: Session, user_id: int) -> DriverProfile:
    p = db.execute(select(DriverProfile).where(DriverProfile.user_id == user_id)).scalar_one_or_none()
    if not p:
        raise LookupError("Профиль не найден")
    p.approved = False
    p.rejected = True
    p.active = False
    db.commit()
    db.refresh(p)
    return p


def admin_verify_vehicle(db: Session, user_id: int) -> TaxiVehicle:
    v = db.execute(select(TaxiVehicle).where(TaxiVehicle.driver_id == user_id)).scalar_one_or_none()
    if not v:
        raise LookupError("Автомобиль не найден")
    v.verified = True
    db.commit()
    db.refresh(v)
    return v


def admin_unverify_vehicle(db: Session, user_id: int) -> TaxiVehicle:
    v = db.execute(select(TaxiVehicle).where(TaxiVehicle.driver_id == user_id)).scalar_one_or_none()
    if not v:
        raise LookupError("Автомобиль не найден")
    v.verified = False
    db.commit()
    db.refresh(v)
    return v


# --- АЛИАСЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ ---
# Чтобы старый импорт из admin_drivers.py `from ..services.driver import admin_approve, admin_reject`
# продолжал работать без переписывания.
def admin_approve(db: Session, user_id: int) -> DriverProfile:
    return admin_approve_profile(db, user_id)


def admin_reject(db: Session, user_id: int) -> DriverProfile:
    return admin_reject_profile(db, user_id)