from pathlib import Path
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db import get_db
from ..models.user import User
from ..models.trip import Trip
from ..models.delivery import DeliveryOrder
from ..models.ad import Ad
from ..admin.security import require_admin


router = APIRouter(prefix="/admin", tags=["admin"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1].parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("", response_class=HTMLResponse)
def admin_home(request: Request, _: bool = Depends(require_admin)):
    return templates.TemplateResponse("admin/home.html", {"request": request})

@router.get("/users", response_class=HTMLResponse)
def admin_users(request: Request, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
    return templates.TemplateResponse("admin/users.html", {"request": request, "users": rows})

@router.get("/trips", response_class=HTMLResponse)
def admin_trips(request: Request, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(Trip).order_by(Trip.id.desc())).scalars().all()
    return templates.TemplateResponse("admin/trips.html", {"request": request, "items": rows})



@router.get("/ads", response_class=HTMLResponse)
def admin_ads(request: Request, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(Ad).order_by(Ad.id.desc())).scalars().all()
    return templates.TemplateResponse("admin/ads.html", {"request": request, "items": rows})