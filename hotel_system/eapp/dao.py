import hashlib
from datetime import datetime
from sqlalchemy import func
from eapp import app, db
from eapp.models import (
    User, Account, Customer, RoomType, Room, Regulation,
    Booking, BookingDetail, Rental, RentalDetail, StayDetail,
    Invoice, InvoiceDetail, AccountRole, RoomStatus,
    BookingStatus, RentalStatus, CustomerType
)
from eapp.utils import (
    calculate_deposit, validate_max_hold_days,
    calculate_stay_days, calculate_room_checkout
)
from eapp.services import NotificationService


# 1. Room & RoomType Queries
def load_room_types():
    return RoomType.query.all()


def load_rooms(room_type_id=None, status=None, kw=None, page=1):
    query = Room.query

    if room_type_id:
        query = query.filter(Room.room_type_id == int(room_type_id))
    if status:
        query = query.filter(Room.status == RoomStatus[status])
    if kw:
        query = query.filter(Room.room_number.contains(kw))

    page_size = app.config['PAGE_SIZE']
    start = (page - 1) * page_size
    return query.order_by(Room.room_number).slice(start, start + page_size).all()


def count_rooms(room_type_id=None, status=None, kw=None):
    query = Room.query

    if room_type_id:
        query = query.filter(Room.room_type_id == int(room_type_id))
    if status:
        query = query.filter(Room.status == RoomStatus[status])
    if kw:
        query = query.filter(Room.room_number.contains(kw))

    return query.count()


def get_current_regulation():
    return Regulation.query.first()


def get_available_rooms_by_dates(checkin_date, checkout_date, room_type_id=None):
    booked_room_ids = (
        db.session.query(BookingDetail.room_id)
        .join(Booking, Booking.id == BookingDetail.booking_id)
        .filter(
            Booking.status == BookingStatus.PENDING_CHECKIN,
            Booking.expected_checkin < checkout_date,
            Booking.expected_checkout > checkin_date
        )
    )

    occupied_room_ids = (
        db.session.query(RentalDetail.room_id)
        .join(Rental, Rental.id == RentalDetail.rental_id)
        .filter(
            Rental.status == RentalStatus.ACTIVE,
            Rental.checkin_date < checkout_date,
            Rental.expected_checkout > checkin_date
        )
    )

    query = Room.query.filter(
        ~Room.id.in_(booked_room_ids),
        ~Room.id.in_(occupied_room_ids),
        Room.status != RoomStatus.CLEANING
    )

    if room_type_id:
        query = query.filter(Room.room_type_id == int(room_type_id))

    return query.order_by(Room.room_number).all()


# 2. Authentication & User Management
def auth_user(username, password, role=None):
    hashed_pw = hashlib.md5(password.strip().encode('utf-8')).hexdigest()
    query = Account.query.filter(
        Account.username == username.strip(),
        Account.password == hashed_pw,
        Account.active == True
    )
    if role:
        query = query.filter(Account.role == role)
    return query.first()


def get_account_by_id(account_id):
    return Account.query.get(account_id)


def register_customer(full_name, identity_card, phone, username, password,
                      email=None, address=None, avatar=None,
                      customer_type=CustomerType.DOMESTIC):
    hashed_pw = hashlib.md5(password.strip().encode('utf-8')).hexdigest()

    user = User(
        full_name=full_name.strip(),
        identity_card=identity_card.strip(),
        phone=phone.strip(),
        email=email.strip() if email else None,
        address=address.strip() if address else None,
        avatar=avatar if avatar else '/static/images/default-avatar.png'
    )
    db.session.add(user)
    db.session.flush()

    customer = Customer(user_id=user.id, customer_type=customer_type)
    account = Account(
        username=username.strip(),
        password=hashed_pw,
        role=AccountRole.CUSTOMER,
        user_id=user.id
    )
    db.session.add_all([customer, account])
    db.session.commit()
    return account

