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

# 5. Regulations:

class Regulation(BaseModel):
    __tablename__ = 'regulation'
    max_guests = Column(Integer, nullable=False)
    extra_guest_rate = Column(Float, nullable=False)
    foreign_guest_factor = Column(Float, nullable=False)
    max_hold_days = Column(Integer, nullable=False)
    deposit_rate = Column(Float, nullable=False)

# 6. Bookings:

class Booking(BaseModel):
    __tablename__ = 'booking'
    booking_date = Column(DateTime, default=datetime.now)
    expected_checkin = Column(DateTime, nullable=False)
    expected_checkout = Column(DateTime, nullable=False)
    total_estimated = Column(Float, nullable=False)
    deposit_amount = Column(Float, nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING_CHECKIN)
    customer_id = Column(Integer, ForeignKey('customer.user_id'), nullable=False)

    details = relationship('BookingDetail', backref='booking', lazy=True)
    rental = relationship('Rental', backref='booking', uselist=False, lazy=True)

class BookingDetail(BaseModel):
    __tablename__ = 'booking_detail'
    booking_id = Column(Integer, ForeignKey('booking.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id'), nullable=False)
    price_at_booking = Column(Float, nullable=False)
    room_deposit = Column(Float, nullable=False)

    room = relationship('Room', lazy=True)

# 7. Rentals:

class Rental(BaseModel):
    __tablename__ = 'rental'
    created_date = Column(DateTime, default=datetime.now)
    checkin_date = Column(DateTime, nullable=False)
    expected_checkout = Column(DateTime, nullable=False)
    deposit_deducted = Column(Float, default=0.0)
    status = Column(Enum(RentalStatus), default=RentalStatus.ACTIVE)
    booking_id = Column(Integer, ForeignKey('booking.id'), nullable=True)
    staff_id = Column(Integer, ForeignKey('staff.user_id'), nullable=False)

    rental_details = relationship('RentalDetail', backref='rental', lazy=True)
    stay_details = relationship('StayDetail', backref='rental', lazy=True)
    invoice = relationship('Invoice', backref='rental', uselist=False, lazy=True)

class RentalDetail(BaseModel):
    __tablename__ = 'rental_detail'
    rental_id = Column(Integer, ForeignKey('rental.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id'), nullable=False)
    actual_checkout = Column(DateTime, nullable=True)

    room = relationship('Room', lazy=True)

class StayDetail(BaseModel):
    __tablename__ = 'stay_detail'
    rental_id = Column(Integer, ForeignKey('rental.id'), nullable=True)
    booking_id = Column(Integer, ForeignKey('booking.id'), nullable=True)
    customer_id = Column(Integer, ForeignKey('customer.user_id'), nullable=False)










