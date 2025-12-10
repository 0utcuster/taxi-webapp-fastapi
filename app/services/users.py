from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.user import User

def ensure_user_from_tg(db: Session, tg_user: dict) -> User:
    tgid = int(tg_user.get("id"))
    username = tg_user.get("username")
    first = tg_user.get("first_name") or ""
    last = tg_user.get("last_name") or ""
    name = (first + " " + last).strip() or None

    # Сначала ищем по telegram_id, потом по tg_id (на всякий случай)
    u = db.execute(select(User).where(User.telegram_id == tgid)).scalar_one_or_none()
    if not u:
        u = db.execute(select(User).where(User.tg_id == tgid)).scalar_one_or_none()

    if u:
        # мягкий апдейт видимых полей
        changed = False
        if username and u.username != username:
            u.username = username; changed = True
        if name and u.name != name:
            u.name = name; changed = True
        if u.tg_id != tgid:  # синхронизируем зеркало
            u.tg_id = tgid; changed = True
        if changed:
            db.add(u); db.commit(); db.refresh(u)
        return u

    # создаём нового
    u = User(
        telegram_id=tgid,  # NOT NULL в твоей БД
        tg_id=tgid,        # дублируем для совместимости с кодом
        username=username,
        name=name,
        role="user",
        is_active=True,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u