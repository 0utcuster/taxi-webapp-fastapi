# app/services/taxi.py
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from ..models.taxi import TaxiTrip, TripStatus, TaxiBid, TaxiBidStatus, PriceMode
from ..models.user import User
from ..models.taxi import TaxiVehicle

# утилиты

def _trip_by_id(db: Session, trip_id: int) -> TaxiTrip | None:
    return db.get(TaxiTrip, trip_id)

def _user_by_id(db: Session, uid: int) -> User | None:
    return db.get(User, uid)

def _ensure_trip_owner(trip: TaxiTrip, user: User):
    if trip.passenger_id != user.id:
        raise PermissionError("Доступ только для владельца поездки")

def _ensure_assigned_driver(trip: TaxiTrip, user: User):
    if trip.assigned_driver_id != user.id:
        raise PermissionError("Доступ только для назначенного водителя")

# список открытых для ленты водителя (NEW + режимы, где ещё не назначен водитель)
def list_open_trips_for_driver(db: Session, limit: int = 50) -> list[dict]:
    trips = db.execute(
        select(TaxiTrip).where(
            TaxiTrip.status == TripStatus.NEW
        ).order_by(TaxiTrip.created_at.desc()).limit(limit)
    ).scalars().all()

    return [t.to_dict() for t in trips]

# мои поездки
def list_my_trips(db: Session, user: User, role: str, limit: int = 50) -> list[dict]:
    if role == "driver":
        trips = db.execute(
            select(TaxiTrip).where(
                TaxiTrip.assigned_driver_id == user.id,
                TaxiTrip.status.in_([TripStatus.ASSIGNED, TripStatus.ON_WAY, TripStatus.IN_PROGRESS]),
            ).order_by(TaxiTrip.created_at.desc()).limit(limit)
        ).scalars().all()
    else:
        trips = db.execute(
            select(TaxiTrip).where(
                TaxiTrip.passenger_id == user.id,
                TaxiTrip.status.in_([TripStatus.NEW, TripStatus.ASSIGNED, TripStatus.ON_WAY, TripStatus.IN_PROGRESS])
            ).order_by(TaxiTrip.created_at.desc()).limit(limit)
        ).scalars().all()

    out = []
    for t in trips:
        item = t.to_dict()
        # если назначен — подтянем водителя и авто
        if t.assigned_driver_id:
            drv = _user_by_id(db, t.assigned_driver_id)
            car = db.get(TaxiVehicle, t.assigned_vehicle_id) if t.assigned_vehicle_id else None
            item["driver"] = {
                "id": drv.id if drv else None,
                "name": (drv.name if drv and drv.name else (('@'+drv.username) if drv and drv.username else None)),
                "phone": getattr(drv, "phone", None),
                "vehicle": {
                    "make": car.make if car else None,
                    "model": car.model if car else None,
                    "color": car.color if car else None,
                    "plate": car.plate if car else None,
                    "seats": car.seats if car else None,
                    "photo_url": car.photo_url if car else None,
                } if car else None,
            }
        out.append(item)
    return out

# история
def list_history(db: Session, user: User, role: str, limit: int = 50) -> list[dict]:
    if role == "driver":
        trips = db.execute(
            select(TaxiTrip).where(
                TaxiTrip.assigned_driver_id == user.id,
                TaxiTrip.status.in_([TripStatus.COMPLETED, TripStatus.CANCELLED]),
            ).order_by(TaxiTrip.created_at.desc()).limit(limit)
        ).scalars().all()
    else:
        trips = db.execute(
            select(TaxiTrip).where(
                TaxiTrip.passenger_id == user.id,
                TaxiTrip.status.in_([TripStatus.COMPLETED, TripStatus.CANCELLED]),
            ).order_by(TaxiTrip.created_at.desc()).limit(limit)
        ).scalars().all()
    return [t.to_dict() for t in trips]

# водитель делает ставку
def driver_bid(db: Session, tg_user, trip_id: int, offered_price: int, comment: str | None) -> TaxiBid:
    # tg_user -> получаем user
    driver = db.execute(select(User).where(User.telegram_id == tg_user["id"])).scalar_one()
    trip = _trip_by_id(db, trip_id)
    if not trip:
        raise LookupError("Поездка не найдена")
    if trip.status != TripStatus.NEW:
        raise ValueError("На поездку уже назначен водитель или она неактивна")
    if offered_price <= 0:
        raise ValueError("Цена должна быть больше 0")

    bid = TaxiBid(
        trip_id=trip.id,
        driver_id=driver.id,
        driver_tg_id=driver.telegram_id,
        offered_price=offered_price,
        comment=comment,
        status=TaxiBidStatus.PENDING,
    )
    db.add(bid); db.commit(); db.refresh(bid)
    return bid

# клиент выбирает ставку → назначается водитель и цена фиксируется
def passenger_accept_bid(db: Session, tg_user, bid_id: int) -> TaxiTrip:
    user = db.execute(select(User).where(User.telegram_id == tg_user["id"])).scalar_one()
    bid = db.get(TaxiBid, bid_id)
    if not bid:
        raise LookupError("Ставка не найдена")
    trip = _trip_by_id(db, bid.trip_id)
    if not trip:
        raise LookupError("Поездка не найдена")
    _ensure_trip_owner(trip, user)
    if trip.status != TripStatus.NEW:
        raise ValueError("Поездка уже недоступна для назначения")

    # отметим ставку как принятую, остальные — отклонить
    db.execute(
        update(TaxiBid).where(
            TaxiBid.trip_id == trip.id,
            TaxiBid.id == bid.id
        ).values(status=TaxiBidStatus.ACCEPTED)
    )
    db.execute(
        update(TaxiBid).where(
            TaxiBid.trip_id == trip.id,
            TaxiBid.id != bid.id
        ).values(status=TaxiBidStatus.REJECTED)
    )

    # назначаем водителя
    trip.assigned_driver_id = bid.driver_id
    trip.assigned_driver_tg_id = bid.driver_tg_id
    trip.final_price = bid.offered_price
    trip.status = TripStatus.ASSIGNED
    db.commit(); db.refresh(trip)
    return trip

# водитель принимает фиксированную цену (режим client_sets)
def driver_accept_fixed_price(db: Session, tg_user, trip_id: int, vehicle_id: int | None, driver_price: int | None) -> TaxiTrip:
    driver = db.execute(select(User).where(User.telegram_id == tg_user["id"])).scalar_one()
    trip = _trip_by_id(db, trip_id)
    if not trip:
        raise LookupError("Поездка не найдена")
    if trip.status != TripStatus.NEW:
        raise ValueError("Поездка уже недоступна для назначения")
    if trip.price_mode != PriceMode.CLIENT_SETS:
        raise ValueError("Для этой поездки нужно предложить цену (ставка)")

    trip.assigned_driver_id = driver.id
    trip.assigned_driver_tg_id = driver.telegram_id
    trip.final_price = driver_price if (driver_price and driver_price > 0) else (trip.client_price or 0)
    trip.status = TripStatus.ASSIGNED
    db.commit(); db.refresh(trip)
    return trip

# отмена поездки
def cancel_trip(db: Session, tg_user, trip_id: int) -> TaxiTrip:
    user = db.execute(select(User).where(User.telegram_id == tg_user["id"])).scalar_one()
    trip = _trip_by_id(db, trip_id)
    if not trip:
        raise LookupError("Поездка не найдена")
    # отменить может владелец до начала исполнения
    _ensure_trip_owner(trip, user)
    if trip.status in [TripStatus.COMPLETED, TripStatus.CANCELLED]:
        raise ValueError("Поездка уже завершена/отменена")
    if trip.status in [TripStatus.ON_WAY, TripStatus.IN_PROGRESS]:
        raise ValueError("Нельзя отменить поездку после начала исполнения")

    trip.status = TripStatus.CANCELLED
    db.commit(); db.refresh(trip)
    return trip

# переходы статусов
_ALLOWED = {
    TripStatus.ASSIGNED:    [TripStatus.ON_WAY],
    TripStatus.ON_WAY:      [TripStatus.IN_PROGRESS],
    TripStatus.IN_PROGRESS: [TripStatus.COMPLETED],
}

def move_status(db: Session, tg_user, trip_id: int, new_status_str: str) -> TaxiTrip:
    user = db.execute(select(User).where(User.telegram_id == tg_user["id"])).scalar_one()
    trip = _trip_by_id(db, trip_id)
    if not trip:
        raise LookupError("Поездка не найдена")

    try:
        new_status = TripStatus(new_status_str)
    except Exception:
        raise ValueError("Недопустимый статус")

    if new_status == TripStatus.CANCELLED:
        # отменять может владелец (уже есть cancel_trip), здесь блокируем
        raise ValueError("Отменять поездку нужно через /cancel")

    # кто имеет право менять
    if trip.assigned_driver_id == user.id:
        # водитель может менять только свою поездку и только по карте переходов
        allowed = _ALLOWED.get(trip.status, [])
        if new_status not in allowed:
            raise ValueError(f"Недопустимый переход из {trip.status.value} в {new_status.value}")
    elif trip.passenger_id == user.id:
        # клиент менять стадии выполнения не может
        raise PermissionError("Клиент не может менять этот статус")
    else:
        raise PermissionError("Нет доступа")

    trip.status = new_status
    db.commit(); db.refresh(trip)
    return trip