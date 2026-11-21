import hashlib
from datetime import datetime
import cloudinary.uploader
from sqlalchemy import func
from eapp import app, db
from eapp.models import (
    User, Account, Customer, Staff, Manager,
    RoomType, Room, Regulation,
    Booking, BookingDetail, Rental, RentalDetail, StayDetail,
    Invoice, InvoiceDetail,
    AccountRole, RoomStatus, BookingStatus, RentalStatus, CustomerType
)
from eapp.utils import (
    calculate_deposit, validate_max_hold_days,
    calculate_room_checkout, NotificationService
)

# add load room types and regulation queries
def load_room_types():
    return RoomType.query.all()

def get_current_regulation():
    return Regulation.query.first()

# add room search filtering and pagination count
def load_rooms(kw=None, room_type_id=None, status=None, page=1):
    query = Room.query

    if kw:
        query = query.filter(Room.room_number.contains(kw))

    if room_type_id:
        query = query.filter(Room.room_type_id == int(room_type_id))

    if status:
        query = query.filter(Room.status == status)

    page_size = app.config['PAGE_SIZE']
    start = (page - 1) * page_size
    return query.slice(start, start + page_size).all()


def count_rooms(kw=None, room_type_id=None, status=None):
    query = Room.query
    if kw:
        query = query.filter(Room.room_number.contains(kw))
    if room_type_id:
        query = query.filter(Room.room_type_id == int(room_type_id))
    if status:
        query = query.filter(Room.status == status)
    return query.count()

# add account authentication and user loader
def authenticate(username, password):
    password = hashlib.md5(password.strip().encode('utf-8')).hexdigest()
    return Account.query.filter(
        Account.username.__eq__(username.strip()),
        Account.password.__eq__(password),
        Account.active == True
    ).first()


def get_account_by_id(account_id):
    return Account.query.get(account_id)


