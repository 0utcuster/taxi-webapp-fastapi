from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/info", response_class=HTMLResponse)
def info_page(request: Request):
    return templates.TemplateResponse("info.html", {"request": request})

# taxi.py
@router.get("/taxi", response_class=HTMLResponse)
def taxi_page(request: Request):
    return templates.TemplateResponse("taxi.html", {"request": request, "back_href": "/dashboard"})

# delivery.py / ads.py / info.py / profile.py — аналогично