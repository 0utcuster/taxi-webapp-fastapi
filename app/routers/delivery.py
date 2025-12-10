from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from ..db import Base
from ..db import get_db
from ..deps import get_current_tg_user
from ..realtime import hub

from ..models.user import User
from ..models.delivery import (
    DeliveryOrder, DeliveryBid, DeliveryStatus, DeliveryPriceMode, DeliveryBidStatus
)
from ..services.courier import (
    ensure_user_from_tg,
    get_or_create_profile, submit_profile, set_active, ensure_courier_allowed
)

import httpx
from sqlalchemy import select

from ..config import settings
from ..models.user import User
from ..models.courier import CourierProfile

router = APIRouter(tags=["delivery"])


# ---------- UI ----------
@router.get("/delivery")
def delivery_page(request: Request):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse("delivery.html", {"request": request, "back_href": "/dashboard"})


# ---------- Courier Onboarding API ----------
@router.get("/api/delivery/courier/me")
def api_courier_me(tg_user=Depends(get_current_tg_user), db: Session = Depends(get_db)):
    p = get_or_create_profile(db, tg_user)
    def _dt(x):
        if isinstance(x, (dt.date, dt.datetime)):
            return x.isoformat()
        return x
    return {
        "ok": True,
        "profile": {
            "id": p.id,
            "approved": p.approved,
            "rejected": p.rejected,
            "active": p.active,
            "full_name": p.full_name,
            "phone": p.phone,
            "notes": p.notes,
            "created_at": _dt(p.created_at),
        }
    }


@router.post("/api/delivery/courier/profile")
def api_courier_profile(
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db)
):
    try:
        p = submit_profile(db, tg_user, payload)
        background_tasks.add_task(hub.publish, "courier_profile_updated", {"user_id": p.user_id})
        return {"ok": True, "profile_id": p.id, "approved": p.approved}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/delivery/courier/active")
def api_courier_active(
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db)
):
    try:
        value = bool(payload.get("active"))
        p = set_active(db, tg_user, value)
        background_tasks.add_task(hub.publish, "courier_active_changed", {"user_id": p.user_id, "active": p.active})
        return {"ok": True, "active": p.active}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------- Orders / Bids API ----------

def _order_to_public(o: DeliveryOrder, courier: User | None = None):
    def _dt(x):
        if isinstance(x, (dt.date, dt.datetime)):
            return x.isoformat()
        return x

    out = {
        "id": o.id,
        "status": (o.status.value if isinstance(o.status, DeliveryStatus) else str(o.status)).lower(),
        "price_mode": (o.price_mode.value if isinstance(o.price_mode, DeliveryPriceMode) else str(o.price_mode)).lower(),
        "client_price": o.client_price,
        "final_price": o.final_price,
        "title": o.title,
        "details": o.details,
        "from_place": o.from_place,
        "to": {"street": o.to_street, "house": o.to_house, "comment": o.to_comment},
        "created_at": _dt(o.created_at),
        "updated_at": _dt(o.updated_at),
    }
    if o.assigned_courier_id:
        out["courier"] = {
            "id": o.assigned_courier_id,
            "tg_id": o.assigned_courier_tg_id,
        }
    return out


async def notify_delivery_new_order(tg_ids: list[int], text: str) -> None:
    """
    Шлёт текстовое уведомление всем chat_id в tg_ids.
    Безопасно молчит, если нет токена или список пустой.
    """
    token = settings.BOT_TOKEN
    if not token or not tg_ids:
        if not token:
            print("[WARN] Не указан BOT_TOKEN — уведомления о доставке не отправлены")
        return

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=8.0) as client:
        for chat_id in tg_ids:
            try:
                await client.post(api_url, json={"chat_id": chat_id, "text": text})
            except Exception as e:
                print(f"[WARN] sendMessage(delivery) failed for {chat_id}: {e}")

@router.post("/api/delivery/orders")
def api_create_order(
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db)
):
    u = ensure_user_from_tg(db, tg_user)

    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Укажите короткое описание заказа (title).")

    mode_raw = (payload.get("price_mode") or "client_sets").lower()
    mode = DeliveryPriceMode.CLIENT_SETS if mode_raw == "client_sets" else DeliveryPriceMode.COURIER_BIDS

    client_price = payload.get("client_price")
    client_price = int(client_price) if (client_price not in (None, "")) else None
    if mode == DeliveryPriceMode.CLIENT_SETS and (client_price is None or client_price <= 0):
        raise HTTPException(status_code=400, detail="Укажите корректную цену для фиксированного заказа.")

    o = DeliveryOrder(
        customer_id=u.id,
        customer_tg_id=u.telegram_id,
        title=title,
        details=(payload.get("details") or None),
        from_place=(payload.get("from_place") or None),
        to_street=(payload.get("to_street") or None),
        to_house=(payload.get("to_house") or None),
        to_comment=(payload.get("to_comment") or None),
        price_mode=mode,
        client_price=client_price,
        status=DeliveryStatus.NEW,
    )
    db.add(o)
    db.commit()
    db.refresh(o)

    # --- realtime событие для фронта ---
    background_tasks.add_task(hub.publish, "delivery_order_created", {"order_id": o.id})

    # --- подготовка Telegram-уведомления, как в такси ---
    is_fixed = (o.price_mode == DeliveryPriceMode.CLIENT_SETS)
    price_part = f" • {o.client_price} ₽" if (is_fixed and o.client_price) else ""
    to_line = ""
    if o.to_street or o.to_house:
        to_line = f"\nДоставить: {(o.to_street or '')} {(o.to_house or '')}".strip()

    text = (
        "📦 Новый заказ (доставка)\n"
        f"{o.title}{price_part}"
        f"{to_line}\n"
        "Открой Mini App, чтобы посмотреть детали."
    )

    # активные и одобренные курьеры, исключая автора (на случай совпадения)
    tg_ids = db.execute(
        select(User.telegram_id)
        .join(CourierProfile, CourierProfile.user_id == User.id)
        .where(CourierProfile.approved.is_(True))
        .where(CourierProfile.active.is_(True))
    ).scalars().all()
    tg_ids = [int(tg) for tg in tg_ids if tg and int(tg) != int(u.telegram_id or 0)]

    # фоновая отправка TG-уведомлений
    background_tasks.add_task(notify_delivery_new_order, tg_ids, text)

    return {"ok": True, "order": _order_to_public(o)}


@router.get("/api/delivery/orders")
def api_list_orders(
    role: Literal["customer", "courier", "feed"] = Query("customer"),
    limit: int = Query(50, le=200),
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    items = []

    try:
        if role == "customer":
            rows = db.execute(
                select(DeliveryOrder)
                .where(DeliveryOrder.customer_id == u.id)
                .order_by(DeliveryOrder.id.desc())
                .limit(limit)
            ).scalars().all()
            for o in rows:
                items.append(_order_to_public(o))

        elif role == "courier":
            ensure_courier_allowed(db, tg_user, need_active=True)
            rows = db.execute(
                select(DeliveryOrder)
                .where(DeliveryOrder.assigned_courier_id == u.id)
                .order_by(DeliveryOrder.id.desc())
                .limit(limit)
            ).scalars().all()
            for o in rows:
                items.append(_order_to_public(o))

        else:  # feed
            ensure_courier_allowed(db, tg_user, need_active=True)
            rows = db.execute(
                select(DeliveryOrder)
                .where(DeliveryOrder.status == DeliveryStatus.NEW)
                .order_by(DeliveryOrder.id.desc())
                .limit(limit)
            ).scalars().all()
            items = [_order_to_public(o) for o in rows]

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return {"ok": True, "items": items}


# Курьер делает ставку (для COURIER_BIDS)
@router.post("/api/delivery/orders/{order_id}/bids")
def api_courier_bid(
    order_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    ensure_courier_allowed(db, tg_user, need_active=True)
    u = ensure_user_from_tg(db, tg_user)
    o = db.get(DeliveryOrder, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if o.price_mode != DeliveryPriceMode.COURIER_BIDS:
        raise HTTPException(status_code=400, detail="Для этого заказа ставки не принимаются")
    if o.status != DeliveryStatus.NEW:
        raise HTTPException(status_code=400, detail="Ставки принимаются только для новых заказов")

    price = payload.get("offered_price")
    price = int(price) if price not in (None, "") else None
    if not price or price <= 0:
        raise HTTPException(status_code=400, detail="Укажите корректную цену")

    existing = db.execute(select(DeliveryBid).where(
        DeliveryBid.order_id == o.id,
        DeliveryBid.driver_id == u.id,
        DeliveryBid.status == DeliveryBidStatus.PENDING
    )).scalar_one_or_none()

    if existing:
        existing.offered_price = price
        db.commit()
        bid = existing
    else:
        bid = DeliveryBid(
            order_id=o.id, driver_id=u.id, driver_tg_id=u.telegram_id,
            offered_price=price, status=DeliveryBidStatus.PENDING
        )
        db.add(bid)
        db.commit()
        db.refresh(bid)

    background_tasks.add_task(hub.publish, "delivery_bid_created", {"order_id": o.id})
    return {"ok": True, "bid_id": bid.id}


# Клиент принимает ставку (назначение курьера)
@router.post("/api/delivery/bids/{bid_id}/accept")
def api_customer_accept_bid(
    bid_id: int,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    b = db.get(DeliveryBid, bid_id)
    if not b:
        raise HTTPException(status_code=404, detail="Ставка не найдена")
    o = db.get(DeliveryOrder, b.order_id)
    if not o or o.customer_id != u.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    if o.status != DeliveryStatus.NEW:
        raise HTTPException(status_code=400, detail="Нельзя принять ставку: заказ не новый")

    o.assigned_courier_id = b.driver_id
    o.assigned_courier_tg_id = b.driver_tg_id
    o.final_price = b.offered_price
    o.status = DeliveryStatus.ASSIGNED

    b.status = DeliveryBidStatus.ACCEPTED
    db.execute(
        DeliveryBid.__table__.update()
        .where(and_(DeliveryBid.order_id == o.id, DeliveryBid.id != b.id, DeliveryBid.status == DeliveryBidStatus.PENDING))
        .values(status=DeliveryBidStatus.REJECTED)
    )
    db.commit()
    db.refresh(o)

    background_tasks.add_task(hub.publish, "delivery_order_assigned", {"order_id": o.id, "courier_id": o.assigned_courier_id})
    return {"ok": True, "order_id": o.id, "status": o.status.value.lower(), "final_price": o.final_price}


# Курьер «берёт» фиксированный заказ (CLIENT_SETS)
@router.post("/api/delivery/orders/{order_id}/accept")
def api_courier_accept_fixed(
    order_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    ensure_courier_allowed(db, tg_user, need_active=True)
    u = ensure_user_from_tg(db, tg_user)
    o = db.get(DeliveryOrder, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if o.status != DeliveryStatus.NEW:
        raise HTTPException(status_code=400, detail="Заказ уже недоступен")
    if o.price_mode != DeliveryPriceMode.CLIENT_SETS:
        raise HTTPException(status_code=400, detail="Для этого заказа требуется ставка и одобрение клиента")
    if not o.client_price or o.client_price <= 0:
        raise HTTPException(status_code=400, detail="Фикс-цена не указана.")

    o.assigned_courier_id = u.id
    o.assigned_courier_tg_id = u.telegram_id
    o.final_price = o.client_price
    o.status = DeliveryStatus.ASSIGNED
    db.commit()
    db.refresh(o)

    background_tasks.add_task(hub.publish, "delivery_order_assigned", {"order_id": o.id, "courier_id": o.assigned_courier_id})
    return {"ok": True, "id": o.id, "status": o.status.value.lower()}


# Отмена клиентом
@router.post("/api/delivery/orders/{order_id}/cancel")
def api_cancel_delivery_order(
    order_id: int,
    background_tasks: BackgroundTasks,
    tg_user = Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    # 1) Автор — из Telegram WebApp
    u = ensure_user_from_tg(db, tg_user)

    # 2) Заказ существует?
    o = db.get(DeliveryOrder, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # 3) Это его заказ?
    if o.customer_id != u.id:
        raise HTTPException(status_code=403, detail="Можно отменять только свои заказы")

    # 4) Уже завершён/отменён?
    if o.status in (DeliveryStatus.COMPLETED, DeliveryStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Заказ уже завершён")

    # 5) Отменяем
    o.status = DeliveryStatus.CANCELLED
    db.commit()
    db.refresh(o)

    # 6) Событие в SSE, чтобы фронт и лента курьеров обновились
    background_tasks.add_task(
        hub.publish,
        "delivery_order_updated",
        {"order_id": o.id, "status": o.status.value.lower()},
    )

    return {"ok": True, "id": o.id, "status": o.status.value.lower()}


_ALLOWED_TRANSITIONS = {
    DeliveryStatus.ASSIGNED: {DeliveryStatus.ON_WAY, DeliveryStatus.IN_PROGRESS, DeliveryStatus.CANCELLED},
    DeliveryStatus.ON_WAY: {DeliveryStatus.IN_PROGRESS, DeliveryStatus.CANCELLED},
    DeliveryStatus.IN_PROGRESS: {DeliveryStatus.COMPLETED, DeliveryStatus.CANCELLED},
}

@router.post("/api/delivery/orders/{order_id}/status")
def api_move_status(
    order_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    o = db.get(DeliveryOrder, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if o.assigned_courier_id != u.id:
        raise HTTPException(status_code=403, detail="Можно менять статус только назначенного вам заказа")

    raw = (payload.get("status") or "").lower().strip()
    map_in = {
        "on_way": DeliveryStatus.ON_WAY,
        "in_progress": DeliveryStatus.IN_PROGRESS,
        "completed": DeliveryStatus.COMPLETED,
        "cancelled": DeliveryStatus.CANCELLED,
    }
    if raw not in map_in:
        raise HTTPException(status_code=400, detail="Неизвестный статус")
    to_status = map_in[raw]

    allowed = _ALLOWED_TRANSITIONS.get(o.status, set())
    if to_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый переход из {o.status.value.lower()} в {to_status.value.lower()}"
        )

    o.status = to_status
    db.commit()
    db.refresh(o)

    background_tasks.add_task(hub.publish, "delivery_order_updated", {"order_id": o.id, "status": o.status.value.lower()})
    return {"ok": True, "id": o.id, "status": o.status.value.lower()}


# ---------- Real-time stream (SSE) ----------
@router.get("/api/delivery/stream")
def delivery_stream():
    async def gen():
        yield ": ok\n\n"
        async for msg in hub.subscribe():
            yield msg
    return StreamingResponse(gen(), media_type="text/event-stream")