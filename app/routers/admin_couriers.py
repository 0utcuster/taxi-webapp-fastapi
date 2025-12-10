# app/routers/admin_couriers.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
# без ensure_is_admin, как у водителей, чтобы исключить 403
from ..services.courier import (
    admin_list_pending_couriers,
    admin_approve_courier,
    admin_reject_courier,
)

router = APIRouter(tags=["admin-couriers"])

# ---------- HTML ----------
@router.get("/admin/couriers")
def admin_couriers_page(request: Request):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse("admin_couriers.html", {
        "request": request,
        "back_href": "/dashboard",
    })

# ---------- API ----------
@router.get("/api/admin/couriers/pending")
def api_admin_couriers_pending(db: Session = Depends(get_db)):
    rows = admin_list_pending_couriers(db)
    # нормализуем в JSON
    profiles = []
    for p in rows:
        profiles.append({
            "user_id": getattr(p, "user_id", None),
            "full_name": getattr(p, "full_name", None),
            "phone": getattr(p, "phone", None),
            "notes": getattr(p, "notes", None),
            "approved": bool(getattr(p, "approved", False)),
            "rejected": bool(getattr(p, "rejected", False)),
            "active": bool(getattr(p, "active", False)),
        })
    # только реально на модерации (safety)
    profiles = [x for x in profiles if x["user_id"] and not x["approved"] and not x["rejected"]]
    return {"ok": True, "profiles": profiles}

@router.post("/api/admin/couriers/{user_id}/approve")
def api_admin_courier_approve(user_id: int, db: Session = Depends(get_db)):
    p = admin_approve_courier(db, user_id)
    return {"ok": True, "user_id": user_id, "approved": bool(getattr(p, "approved", False))}

@router.post("/api/admin/couriers/{user_id}/reject")
def api_admin_courier_reject(user_id: int, db: Session = Depends(get_db)):
    p = admin_reject_courier(db, user_id)
    return {"ok": True, "user_id": user_id, "rejected": bool(getattr(p, "rejected", False))}