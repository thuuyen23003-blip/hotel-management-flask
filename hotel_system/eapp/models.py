from flask_login import UserMixin
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Enum, Date, DateTime
from sqlalchemy.orm import relationship
from eapp import db, app
from enum import Enum as PyEnum
from datetime import datetime, date
import hashlib


class BaseModel(db.Model):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True)

class AccountRole(PyEnum):
    CUSTOMER = 1
    STAFF = 2
    MANAGER = 3


class RoomStatus(PyEnum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    OCCUPIED = "OCCUPIED"
    CLEANING = "CLEANING"


class BookingStatus(PyEnum):
    PENDING_CHECKIN = "PENDING_CHECKIN"
    CHECKED_IN = "CHECKED_IN"
    EXPIRED_CANCELLED = "EXPIRED_CANCELLED"
    CANCELLED = "CANCELLED"


class RentalStatus(PyEnum):
    ACTIVE = "ACTIVE"
    PAID = "PAID"


class CustomerType(PyEnum):
    DOMESTIC = "DOMESTIC"
    FOREIGN = "FOREIGN"


