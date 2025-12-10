# app/routers/api_chat.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db import get_db
from ..deps import get_current_tg_user
from ..models.chat import ChatMessage
from ..models.user import User

router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.get("/messages")
def list_messages(
    after_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    if after_id:
        q = select(ChatMessage).where(ChatMessage.id > after_id).order_by(ChatMessage.id.asc()).limit(limit)
        rows = db.execute(q).scalars().all()
        return {"ok": True, "items": [
            {"id": m.id, "name": m.author_name, "text": m.text, "created_at": m.created_at.isoformat()} for m in rows
        ]}
    q = select(ChatMessage).order_by(ChatMessage.id.desc()).limit(limit)
    rows = list(reversed(db.execute(q).scalars().all()))
    return {"ok": True, "items": [
        {"id": m.id, "name": m.author_name, "text": m.text, "created_at": m.created_at.isoformat()} for m in rows
    ]}

@router.post("/messages")
def send_message(payload: dict, tg_user=Depends(get_current_tg_user), db: Session = Depends(get_db)):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text required")

    from ..services.users import ensure_user_from_tg
    u = ensure_user_from_tg(db, tg_user)
    display_name = u.display_name

    msg = ChatMessage(author_id=u.id, author_tg_id=tg_user["id"], author_name=display_name, text=text)
    db.add(msg); db.commit(); db.refresh(msg)
    return {"ok": True, "id": msg.id}