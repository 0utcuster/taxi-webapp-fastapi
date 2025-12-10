# app/routers/taxi.py
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import (
    APIRouter, Depends, HTTPException, Query, Request, status, BackgroundTasks
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from ..db import get_db
from ..deps import get_current_tg_user
from ..realtime import hub

from ..models.user import User
from ..models.taxi import (
    TaxiTrip, TaxiVehicle, TripStatus, PriceMode,
    TaxiBid, TaxiBidStatus
)
from ..services.driver import (
    ensure_user_from_tg,
    get_or_create_profile, submit_profile, upsert_vehicle, set_active, ensure_driver_allowed
)

import httpx
from ..config import settings
from ..models.driver import DriverProfile 

router = APIRouter(tags=["taxi"])


# ---------- UI ----------
@router.get("/taxi")
def taxi_page(request: Request):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse("taxi.html", {"request": request, "back_href": "/dashboard"})


# ---------- Driver Onboarding API ----------
@router.get("/api/taxi/driver/me")
def api_driver_me(tg_user=Depends(get_current_tg_user), db: Session = Depends(get_db)):
    u = ensure_user_from_tg(db, tg_user)
    p = get_or_create_profile(db, tg_user)
    v = db.execute(select(TaxiVehicle).where(TaxiVehicle.driver_id == u.id)).scalar_one_or_none()

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
            "license_number": p.license_number,
            "license_valid_to": _dt(p.license_valid_to),
            "notes": p.notes,
        },
        "vehicle": (
            {
                "id": v.id,
                "make": v.make,
                "model": v.model,
                "color": v.color,
                "plate": v.plate,
                "seats": v.seats,
                "photo_url": v.photo_url,
                "verified": v.verified,
                "active": v.active,
            } if v else None
        )
    }


@router.post("/api/taxi/driver/profile")
def api_driver_profile(
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db)
):
    try:
        p = submit_profile(db, tg_user, payload)
        # уведомим всех водителей (их ленту это не затронет, но личные экраны освежатся)
        background_tasks.add_task(hub.publish, "driver_profile_updated", {"user_id": p.user_id})
        return {"ok": True, "profile_id": p.id, "approved": p.approved}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/taxi/driver/vehicle")
def api_driver_vehicle(
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db)
):
    try:
        v = upsert_vehicle(db, tg_user, payload)
        background_tasks.add_task(hub.publish, "driver_vehicle_updated", {"user_id": v.driver_id})
        return {"ok": True, "vehicle_id": v.id}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/taxi/driver/active")
def api_driver_active(
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db)
):
    """
    Водитель включает/выключает видимость (approved+vehicle verified обязательны, чтобы включить).
    """
    try:
        value = bool(payload.get("active"))
        p = set_active(db, tg_user, value)
        background_tasks.add_task(hub.publish, "driver_active_changed", {"user_id": p.user_id, "active": p.active})
        return {"ok": True, "active": p.active}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------- Trips / Bids API ----------

def _trip_to_public(tr: TaxiTrip, driver: User | None = None, vehicle: TaxiVehicle | None = None):
    def _dt(x):
        if isinstance(x, (dt.date, dt.datetime)):
            return x.isoformat()
        return x

    out = {
        "id": tr.id,
        "status": (tr.status.value if isinstance(tr.status, TripStatus) else str(tr.status)).lower(),
        "price_mode": (tr.price_mode.value if isinstance(tr.price_mode, PriceMode) else str(tr.price_mode)).lower(),
        "client_price": tr.client_price,
        "final_price": tr.final_price,
        "from": {"street": tr.from_street, "house": tr.from_house, "comment": tr.from_comment},
        "to": {"street": tr.to_street, "house": tr.to_house, "comment": tr.to_comment},
        "created_at": _dt(tr.created_at),
        "updated_at": _dt(tr.updated_at),
    }
    if tr.assigned_driver_id:
        out["driver"] = {
            "id": tr.assigned_driver_id,
            "tg_id": tr.assigned_driver_tg_id,
            "name": (
                driver.name if driver and getattr(driver, "name", None)
                else (driver.username if driver else None)
            ),
            "username": (driver.username if driver else None),
            "photo_url": (driver.photo_url if (driver and getattr(driver, "photo_url", None)) else None),
        }
    if vehicle:
        out["vehicle"] = {
            "make": vehicle.make, "model": vehicle.model, "color": vehicle.color,
            "plate": vehicle.plate, "seats": vehicle.seats, "photo_url": vehicle.photo_url
        }
    return out


@router.post("/api/taxi/trips")
def api_create_trip(
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db)
):
    """
    Создание поездки.
    - client_sets: цена обязательна.
    - driver_bids: цену ставит водитель.
    - Ограничение: у клиента не более 1 активной поездки (NEW/ASSIGNED/ON_WAY/IN_PROGRESS).
    """
    u = ensure_user_from_tg(db, tg_user)

    active = db.execute(
        select(TaxiTrip.id).where(
            TaxiTrip.passenger_id == u.id,
            TaxiTrip.status.in_((TripStatus.NEW, TripStatus.ASSIGNED, TripStatus.ON_WAY, TripStatus.IN_PROGRESS))
        ).limit(1)
    ).scalar_one_or_none()
    if active:
        raise HTTPException(status_code=409, detail="У вас уже есть активная поездка.")

    from_street = (payload.get("from_street") or "").strip()
    to_street = (payload.get("to_street") or "").strip()
    if not from_street or not to_street:
        raise HTTPException(status_code=400, detail="Укажите улицы отправления и назначения.")

    mode_raw = (payload.get("price_mode") or "client_sets").lower()
    mode = PriceMode.CLIENT_SETS if mode_raw == "client_sets" else PriceMode.DRIVER_BIDS

    client_price = payload.get("client_price")
    client_price = int(client_price) if (client_price not in (None, "")) else None

    if mode == PriceMode.CLIENT_SETS and (client_price is None or client_price <= 0):
        raise HTTPException(status_code=400, detail="Укажите корректную цену для фиксированного заказа.")

    trip = TaxiTrip(
        passenger_id=u.id,
        passenger_tg_id=u.telegram_id,
        from_street=from_street,
        from_house=(payload.get("from_house") or None),
        from_comment=(payload.get("from_comment") or None),
        to_street=to_street,
        to_house=(payload.get("to_house") or None),
        to_comment=(payload.get("to_comment") or None),
        price_mode=mode,
        client_price=client_price,
        status=TripStatus.NEW,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)

    # соберём список активных водителей (одобрен + активен)
    try:
        active_driver_tg_ids = db.execute(
            select(User.telegram_id)
            .join(DriverProfile, DriverProfile.user_id == User.id)
            .where(DriverProfile.approved.is_(True))
            .where(DriverProfile.active.is_(True))
        ).scalars().all()
        active_driver_tg_ids = [int(x) for x in active_driver_tg_ids if x]
    except Exception as e:
        print(f"[WARN] get active drivers failed: {e}")
        active_driver_tg_ids = []

    # ре-тайм в браузеры
    background_tasks.add_task(hub.publish, "trip_created", {"trip_id": trip.id})
    # уведомления в Telegram
    background_tasks.add_task(_notify_drivers_about_new_trip, active_driver_tg_ids, trip)

    return {"ok": True, "trip": _trip_to_public(trip)}


async def _notify_drivers_about_new_trip(tg_ids: list[int], trip: TaxiTrip):
    token = settings.BOT_TOKEN
    if not token:
        print("[WARN] Не указан BOT_TOKEN — уведомления не отправлены")
        return
    if not tg_ids:
        return

    text = (
        "🚕 Новый заказ\n"
        f"От: {trip.from_street or ''} {trip.from_house or ''}\n"
        f"До: {trip.to_street or ''} {trip.to_house or ''}\n"
        f"Режим: {'фикс' if str(trip.price_mode).endswith('CLIENT_SETS') else 'ставки'}"
        f"{f' • {trip.client_price} ₽' if trip.client_price else ''}\n"
        "Открой Mini App, чтобы посмотреть детали."
    ).strip()

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=8.0) as client:
        for chat_id in tg_ids:
            try:
                await client.post(url, json={"chat_id": chat_id, "text": text})
            except Exception as e:
                print(f"[WARN] sendMessage failed for {chat_id}: {e}")


@router.get("/api/taxi/trips")
def api_list_trips(
    role: Literal["client", "driver", "feed"] = Query("client"),
    limit: int = Query(50, le=200),
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    items = []

    try:
        if role == "client":
            rows = db.execute(
                select(TaxiTrip)
                .where(TaxiTrip.passenger_id == u.id)
                .order_by(TaxiTrip.id.desc())
                .limit(limit)
            ).scalars().all()
            for t in rows:
                drv = db.get(User, t.assigned_driver_id) if t.assigned_driver_id else None
                veh = db.get(TaxiVehicle, t.assigned_vehicle_id) if t.assigned_vehicle_id else None
                items.append(_trip_to_public(t, drv, veh))

        elif role == "driver":
            ensure_driver_allowed(db, tg_user, need_active=True)
            rows = db.execute(
                select(TaxiTrip)
                .where(TaxiTrip.assigned_driver_id == u.id)
                .order_by(TaxiTrip.id.desc())
                .limit(limit)
            ).scalars().all()
            for t in rows:
                veh = db.get(TaxiVehicle, t.assigned_vehicle_id) if t.assigned_vehicle_id else None
                items.append(_trip_to_public(t, driver=u, vehicle=veh))

        else:  # feed
            ensure_driver_allowed(db, tg_user, need_active=True)
            rows = db.execute(
                select(TaxiTrip)
                .where(TaxiTrip.status == TripStatus.NEW)
                .order_by(TaxiTrip.id.desc())
                .limit(limit)
            ).scalars().all()
            items = [_trip_to_public(t) for t in rows]

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return {"ok": True, "items": items}


# Водитель делает ставку (для driver_bids)
@router.post("/api/taxi/trips/{trip_id}/bids")
def api_driver_bid(
    trip_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    ensure_driver_allowed(db, tg_user, need_active=True)
    u = ensure_user_from_tg(db, tg_user)
    t = db.get(TaxiTrip, trip_id)
    if not t:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if t.price_mode != PriceMode.DRIVER_BIDS:
        raise HTTPException(status_code=400, detail="Для этой поездки ставки не принимаются")
    if t.status != TripStatus.NEW:
        raise HTTPException(status_code=400, detail="Ставки принимаются только для новых заявок")

    price = payload.get("offered_price")
    price = int(price) if price not in (None, "") else None
    if not price or price <= 0:
        raise HTTPException(status_code=400, detail="Укажите корректную цену")

    existing = db.execute(select(TaxiBid).where(
        TaxiBid.trip_id == t.id,
        TaxiBid.driver_id == u.id,
        TaxiBid.status == TaxiBidStatus.PENDING
    )).scalar_one_or_none()

    if existing:
        existing.offered_price = price
        db.commit()
        bid = existing
    else:
        bid = TaxiBid(
            trip_id=t.id, driver_id=u.id, driver_tg_id=u.telegram_id,
            offered_price=price, status=TaxiBidStatus.PENDING
        )
        db.add(bid)
        db.commit()
        db.refresh(bid)

    background_tasks.add_task(hub.publish, "bid_created", {"trip_id": t.id})
    return {"ok": True, "bid_id": bid.id}


# Клиент видит ставки по своей поездке
@router.get("/api/taxi/trips/{trip_id}/bids")
def api_list_bids_for_trip(
    trip_id: int,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    t = db.get(TaxiTrip, trip_id)
    if not t:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if t.passenger_id != u.id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    rows = db.execute(select(TaxiBid, User).join(User, User.id == TaxiBid.driver_id).where(
        TaxiBid.trip_id == t.id, TaxiBid.status == TaxiBidStatus.PENDING
    ).order_by(TaxiBid.id.desc())).all()

    items = []
    for b, drv in rows:
        items.append({
            "bid_id": b.id,
            "price": b.offered_price,
            "driver": {
                "id": drv.id,
                "name": drv.name or drv.username or (f"TG {drv.telegram_id}"),
                "username": drv.username,
                "photo_url": getattr(drv, "photo_url", None),
            }
        })
    return {"ok": True, "items": items}


# Клиент принимает ставку (назначение водителя)
@router.post("/api/taxi/bids/{bid_id}/accept")
def api_passenger_accept_bid(
    bid_id: int,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    b = db.get(TaxiBid, bid_id)
    if not b:
        raise HTTPException(status_code=404, detail="Ставка не найдена")
    t = db.get(TaxiTrip, b.trip_id)
    if not t or t.passenger_id != u.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    if t.status != TripStatus.NEW:
        raise HTTPException(status_code=400, detail="Нельзя принять ставку: поездка не новая")

    t.assigned_driver_id = b.driver_id
    t.assigned_driver_tg_id = b.driver_tg_id
    veh = db.execute(select(TaxiVehicle).where(TaxiVehicle.driver_id == b.driver_id)).scalar_one_or_none()
    t.assigned_vehicle_id = veh.id if veh else None
    t.final_price = b.offered_price
    t.status = TripStatus.ASSIGNED

    b.status = TaxiBidStatus.ACCEPTED
    db.execute(
        TaxiBid.__table__.update()
        .where(and_(TaxiBid.trip_id == t.id, TaxiBid.id != b.id, TaxiBid.status == TaxiBidStatus.PENDING))
        .values(status=TaxiBidStatus.REJECTED)
    )
    db.commit()
    db.refresh(t)

    background_tasks.add_task(hub.publish, "trip_assigned", {"trip_id": t.id, "driver_id": t.assigned_driver_id})
    return {"ok": True, "trip_id": t.id, "status": t.status.value.lower(), "final_price": t.final_price}


# Водитель «берёт» фиксированный заказ (client_sets)
@router.post("/api/taxi/trips/{trip_id}/accept")
def api_driver_accept_fixed(
    trip_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    ensure_driver_allowed(db, tg_user, need_active=True)
    u = ensure_user_from_tg(db, tg_user)
    t = db.get(TaxiTrip, trip_id)
    if not t:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if t.status != TripStatus.NEW:
        raise HTTPException(status_code=400, detail="Заказ уже недоступен")
    if t.price_mode != PriceMode.CLIENT_SETS:
        raise HTTPException(status_code=400, detail="Для этого заказа требуется ставка и одобрение клиента")
    if not t.client_price or t.client_price <= 0:
        raise HTTPException(status_code=400, detail="Фикс-цена не указана. Нельзя взять без цены — только через ставки.")

    t.assigned_driver_id = u.id
    t.assigned_driver_tg_id = u.telegram_id
    veh = db.execute(select(TaxiVehicle).where(TaxiVehicle.driver_id == u.id)).scalar_one_or_none()
    t.assigned_vehicle_id = veh.id if veh else None
    t.final_price = t.client_price
    t.status = TripStatus.ASSIGNED
    db.commit()
    db.refresh(t)

    background_tasks.add_task(hub.publish, "trip_assigned", {"trip_id": t.id, "driver_id": t.assigned_driver_id})
    return {"ok": True, "id": t.id, "status": t.status.value.lower()}


# Отмена клиентом
@router.post("/api/taxi/trips/{trip_id}/cancel")
def api_cancel_trip(
    trip_id: int,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    t = db.get(TaxiTrip, trip_id)
    if not t:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if t.passenger_id != u.id:
        raise HTTPException(status_code=403, detail="Можно отменять только свои поездки")
    if t.status in (TripStatus.COMPLETED, TripStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Поездка уже завершена")
    t.status = TripStatus.CANCELLED
    db.commit()
    db.refresh(t)

    background_tasks.add_task(hub.publish, "trip_updated", {"trip_id": t.id, "status": t.status.value.lower()})
    return {"ok": True, "id": t.id, "status": t.status.value.lower()}


# Разрешённые переходы статусов
_ALLOWED_TRANSITIONS = {
    TripStatus.ASSIGNED: {TripStatus.ON_WAY, TripStatus.IN_PROGRESS, TripStatus.CANCELLED},
    TripStatus.ON_WAY: {TripStatus.IN_PROGRESS, TripStatus.CANCELLED},
    TripStatus.IN_PROGRESS: {TripStatus.COMPLETED, TripStatus.CANCELLED},
}

@router.post("/api/taxi/trips/{trip_id}/status")
def api_move_status(
    trip_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    t = db.get(TaxiTrip, trip_id)
    if not t:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if t.assigned_driver_id != u.id:
        raise HTTPException(status_code=403, detail="Можно менять статус только назначенной вам поездки")

    raw = (payload.get("status") or "").lower().strip()
    map_in = {
        "on_way": TripStatus.ON_WAY,
        "in_progress": TripStatus.IN_PROGRESS,
        "completed": TripStatus.COMPLETED,
        "cancelled": TripStatus.CANCELLED,
    }
    if raw not in map_in:
        raise HTTPException(status_code=400, detail="Неизвестный статус")
    to_status = map_in[raw]

    allowed = _ALLOWED_TRANSITIONS.get(t.status, set())
    if to_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый переход из {t.status.value.lower()} в {to_status.value.lower()}"
        )

    t.status = to_status
    db.commit()
    db.refresh(t)

    background_tasks.add_task(hub.publish, "trip_updated", {"trip_id": t.id, "status": t.status.value.lower()})
    return {"ok": True, "id": t.id, "status": t.status.value.lower()}


# Клиент запрашивает подробности о водителе и автомобиле
@router.get("/api/taxi/trips/{trip_id}/driver")
def api_trip_driver_info(
    trip_id: int,
    tg_user=Depends(get_current_tg_user),
    db: Session = Depends(get_db),
):
    u = ensure_user_from_tg(db, tg_user)
    t = db.get(TaxiTrip, trip_id)
    if not t:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if t.passenger_id != u.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    driver = db.get(User, t.assigned_driver_id) if t.assigned_driver_id else None
    vehicle = db.get(TaxiVehicle, t.assigned_vehicle_id) if t.assigned_vehicle_id else None
    if not driver:
        raise HTTPException(status_code=404, detail="Водитель ещё не назначен")

    return {
        "ok": True,
        "driver": {
            "id": driver.id,
            "name": driver.name or driver.username or f"TG {driver.telegram_id}",
            "username": driver.username,
            "photo_url": getattr(driver, "photo_url", None),
        },
        "vehicle": (
            {
                "make": vehicle.make,
                "model": vehicle.model,
                "color": vehicle.color,
                "plate": vehicle.plate,
                "seats": vehicle.seats,
                "photo_url": vehicle.photo_url,
            } if vehicle else None
        ),
    }


# ---------- Real-time stream (SSE) ----------
@router.get("/api/taxi/stream")
def taxi_stream():
    async def gen():
        # первый «комментарий» держит канал открытым даже за Cloudflare/прокси
        yield ": ok\n\n"
        async for msg in hub.subscribe():
            # msg уже в формате "event:xxx\ndata: {...}\n\n"
            yield msg
    return StreamingResponse(gen(), media_type="text/event-stream")