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


def load_room_types():
    return RoomType.query.all()


def get_current_regulation():
    return Regulation.query.first()
