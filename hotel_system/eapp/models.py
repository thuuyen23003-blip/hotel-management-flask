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
    phone = Column(String(20), nullable=False)
    email = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    avatar = Column(String(255), default='/static/images/default-avatar.png')

    account = relationship('Account', backref='user', uselist=False, lazy=True)
    customer = relationship('Customer', backref='user', uselist=False, lazy=True)
    staff = relationship('Staff', backref='user', uselist=False, lazy=True)
    manager = relationship('Manager', backref='user', uselist=False, lazy=True)

    def __str__(self):
        return self.full_name

# 3. Roles:

class Account(BaseModel, UserMixin):
    __tablename__ = 'account'
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(100), nullable=False)
    role = Column(Enum(AccountRole), default=AccountRole.CUSTOMER, nullable=False)
    active = Column(Boolean, default=True)
    user_id = Column(Integer, ForeignKey('user.id'), unique=True, nullable=False)

    @property
    def user_role(self):
        return self.role

class Customer(db.Model):
    __tablename__ = 'customer'
    user_id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    customer_type = Column(Enum(CustomerType), default=CustomerType.DOMESTIC, nullable=False)

    bookings = relationship('Booking', backref='customer', lazy=True)
    stay_details = relationship('StayDetail', backref='customer', lazy=True)

class Staff(db.Model):
    __tablename__ = 'staff'
    user_id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    position = Column(String(100), default='Receptionist', nullable=False)

    rentals = relationship('Rental', backref='staff', lazy=True)
    invoices = relationship('Invoice', backref='staff', lazy=True)

class Manager(db.Model):
    __tablename__ = 'manager'
    user_id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    appointed_date = Column(Date, default=date.today, nullable=False)

# 4. Rooms:

class RoomType(BaseModel):
    __tablename__ = 'room_type'
    name = Column(String(50), unique=True, nullable=False)
    base_price = Column(Float, nullable=False)
    description = Column(String(255), nullable=True)
    image = Column(String(255), default='/static/images/default-room.png')

    rooms = relationship('Room', backref='room_type', lazy=True)

    def __str__(self):
        return self.name

class Room(BaseModel):
    __tablename__ = 'room'
    room_number = Column(String(10), unique=True, nullable=False)
    status = Column(Enum(RoomStatus), default=RoomStatus.AVAILABLE, nullable=False)
    room_type_id = Column(Integer, ForeignKey('room_type.id'), nullable=False)

    def __str__(self):
        return f"Room {self.room_number}"

