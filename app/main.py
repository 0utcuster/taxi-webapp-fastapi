# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import engine
from .models.base import Base

# Роутеры (существующие файлы)
from .routers import (
    ui as ui_router,
    profile as profile_router,
    webapp as webapp_router,

    taxi as taxi_router,
    delivery as delivery_router,     # здесь уже есть API курьеров
    api_ads as ads_router,
    info as info_router,

    api_chat as api_chat_router,
    api_news as api_news_router,
    chat as chat_page_router,
    news as news_page_router,

    admin as admin_router,
    admin_drivers as admin_drivers_router,
    pages as pages_router,
    admin_flag as admin_flag_router,
)

# Админка курьеров (отдельный файл app/routers/admin_couriers.py)
from .routers.admin_couriers import router as admin_couriers_router
from .routers import board as board_router

from .routers import admin_board as admin_board_router





app = FastAPI(title="Village WebApp")

# --- CORS ---
allowed_origins = (
    [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
    if getattr(settings, "ALLOWED_ORIGINS", None)
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Сессии ---
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie=getattr(settings, "COOKIE_NAME", "__Host-village"),
    same_site=(settings.COOKIE_SAMESITE or "none"),
    https_only=True,
)

# --- Статика ---
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Подключение роутеров ---
app.include_router(ui_router.router)
app.include_router(profile_router.router)
app.include_router(webapp_router.router)

app.include_router(taxi_router.router)
app.include_router(delivery_router.router)     # курьеры и доставка тут
app.include_router(ads_router.router)
app.include_router(info_router.router)

app.include_router(api_chat_router.router)
app.include_router(api_news_router.router)
app.include_router(chat_page_router.router)
app.include_router(news_page_router.router)

app.include_router(admin_router.router)
app.include_router(admin_drivers_router.router)
app.include_router(admin_flag_router.router)
app.include_router(pages_router.router)

app.include_router(admin_couriers_router)     # админка курьеров


app.include_router(board_router.router)        # /board, /api/board/...
app.include_router(admin_board_router.router)

# --- Инициализация БД ---
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)