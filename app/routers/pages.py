from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")

@router.get("/delivery", include_in_schema=False)
def delivery_page(request: Request):
    return templates.TemplateResponse("delivery.html", {"request": request})

@router.get("/board")
def board_page(request: Request):
    return templates.TemplateResponse("board.html", {"request": request, "back_href": "/dashboard"})

@router.get("/news", include_in_schema=False)
def news_page(request: Request):
    return templates.TemplateResponse("news.html", {"request": request})