from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    """
    Отображает страницу профиля пользователя.
    На странице показаны имя и аватарка, полученные из Telegram WebApp.
    """
    context = {
        "request": request,
        "back_href": "/dashboard",  # кнопка "Назад" ведёт на главную
    }
    return templates.TemplateResponse("profile.html", context)