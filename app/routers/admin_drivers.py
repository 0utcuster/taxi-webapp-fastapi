# app/routers/admin_drivers.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.driver import (
    admin_list_pending,
    admin_approve_profile,
    admin_reject_profile,
    admin_verify_vehicle,
    admin_unverify_vehicle,
)
# Страница админки: /admin/drivers
router = APIRouter(tags=["admin-drivers"])

# ---------- HTML-страница ----------
@router.get("/admin/drivers")
def admin_drivers_page(request: Request):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse("admin_drivers.html", {"request": request, "back_href": "/dashboard"})

# ---------- API ----------
@router.get("/api/admin/drivers/pending")
def api_admin_pending(db: Session = Depends(get_db)):
    data = admin_list_pending(db)
    # Преобразуем в сериализуемый вид
    profiles = [{
        "user_id": p.user_id,
        "full_name": p.full_name,
        "phone": p.phone,
        "license_number": p.license_number,
        "license_valid_to": (p.license_valid_to.isoformat() if p.license_valid_to else None),
        "notes": p.notes,
        "approved": p.approved,
        "rejected": p.rejected,
        "active": p.active,
    } for p in data["profiles"]]

    vehicles = [{
        "driver_id": v.driver_id,
        "make": v.make,
        "model": v.model,
        "color": v.color,
        "plate": v.plate,
        "seats": v.seats,
        "photo_url": v.photo_url,
        "verified": v.verified,
    } for v in data["vehicles"]]

    return {"ok": True, "profiles": profiles, "vehicles": vehicles}

@router.post("/api/admin/drivers/{user_id}/approve_profile")
def api_admin_approve_profile(user_id: int, db: Session = Depends(get_db)):
    p = admin_approve_profile(db, user_id)
    return {"ok": True, "user_id": user_id, "approved": p.approved}

@router.post("/api/admin/drivers/{user_id}/reject_profile")
def api_admin_reject_profile(user_id: int, db: Session = Depends(get_db)):
    p = admin_reject_profile(db, user_id)
    return {"ok": True, "user_id": user_id, "approved": p.approved, "rejected": p.rejected, "active": p.active}

@router.post("/api/admin/drivers/{user_id}/verify_vehicle")
def api_admin_verify_vehicle(user_id: int, db: Session = Depends(get_db)):
    v = admin_verify_vehicle(db, user_id)
    return {"ok": True, "user_id": user_id, "verified": v.verified}

@router.post("/api/admin/drivers/{user_id}/unverify_vehicle")
def api_admin_unverify_vehicle(user_id: int, db: Session = Depends(get_db)):
    v = admin_unverify_vehicle(db, user_id)
    return {"ok": True, "user_id": user_id, "verified": v.verified}

# Сводное действие: одобрить профиль + верифицировать авто (если есть)
@router.post("/api/admin/drivers/{user_id}/approve_all")
def api_admin_approve_all(user_id: int, db: Session = Depends(get_db)):
    p = admin_approve_profile(db, user_id)
    # Попробуем верифицировать авто; если его нет — вернём флаг, что авто отсутствует
    vehicle_verified = False
    try:
        v = admin_verify_vehicle(db, user_id)
        vehicle_verified = bool(v.verified)
    except LookupError:
        vehicle_verified = False
    return {"ok": True, "user_id": user_id, "profile_approved": p.approved, "vehicle_verified": vehicle_verified}

# ---------- Совместимость со старыми URL (если фронт их использует) ----------
@router.get("/api/admin/pending")
def api_admin_pending_compat(db: Session = Depends(get_db)):
    return api_admin_pending(db)

@router.post("/api/admin/approve_profile")
def api_admin_approve_profile_compat(user_id: int, db: Session = Depends(get_db)):
    return api_admin_approve_profile(user_id, db)

@router.post("/api/admin/reject_profile")
def api_admin_reject_profile_compat(user_id: int, db: Session = Depends(get_db)):
    return api_admin_reject_profile(user_id, db)

@router.post("/api/admin/verify_vehicle")
def api_admin_verify_vehicle_compat(user_id: int, db: Session = Depends(get_db)):
    return api_admin_verify_vehicle(user_id, db)

@router.post("/api/admin/unverify_vehicle")
def api_admin_unverify_vehicle_compat(user_id: int, db: Session = Depends(get_db)):
    return api_admin_unverify_vehicle(user_id, db)

@router.post("/api/admin/approve_all")
def api_admin_approve_all_compat(user_id: int, db: Session = Depends(get_db)):
    return api_admin_approve_all(user_id, db)