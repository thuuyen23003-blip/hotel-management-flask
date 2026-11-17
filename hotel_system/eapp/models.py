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

# 1. Enumerations:

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

# 2. Users:

class User(BaseModel, UserMixin):
    __tablename__ = 'user'
    full_name = Column(String(100), nullable=False)
    identity_card = Column(String(20), unique=True, nullable=False)
    phone = Column(String(15), nullable=False)
    email = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    avatar = Column(String(255), default='/static/images/default-avatar.png')

    account = relationship('Account', backref='user', uselist=False, lazy=True)
    customer = relationship('Customer', backref='user', uselist=False, lazy=True)
    staff = relationship('Staff', backref='user', uselist=False, lazy=True)
    manager = relationship('Manager', backref='user', uselist=False, lazy=True)

    def __str__(self):
        return self.full_name

