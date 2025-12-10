from __future__ import annotations
import os, json, asyncio
import httpx

from ..config import settings

BOT_TOKEN = settings.BOT_TOKEN or os.getenv("BOT_TOKEN") or ""
API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None

async def send_tg_message(chat_id: int, text: str):
    if not API or not chat_id:
        print("[WARN] TG notify skipped (no token or chat_id)")
        return
    async with httpx.AsyncClient(timeout=10) as c:
        try:
            await c.post(API, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
        except Exception as e:
            print(f"[WARN] TG notify error: {e}")