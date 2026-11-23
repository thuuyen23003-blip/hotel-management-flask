import enum
import hashlib
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from eapp import app, db


# 1. Enumerations
class AccountRole(enum.Enum):
    CUSTOMER = "Khách hàng"
    STAFF = "Nhân viên"
    MANAGER = "Quản lý"


class CustomerType(enum.Enum):
    DOMESTIC = "Nội địa"
    FOREIGN = "Nước ngoài"


class RoomStatus(enum.Enum):
    AVAILABLE = "Trống"
    BOOKED = "Đã đặt"
    OCCUPIED = "Đang thuê"
    CLEANING = "Đang dọn"


class BookingStatus(enum.Enum):
    PENDING_CHECKIN = "Chờ nhận phòng"
    CHECKED_IN = "Đã nhận phòng"
    CANCELLED = "Đã hủy"
    EXPIRED_CANCELLED = "Hủy do quá hạn"


class RentalStatus(enum.Enum):
    ACTIVE = "Đang thuê"
    PAID = "Đã thanh toán"


# 2. User, Account & Role Inheritance (Joined Table Inheritance)
class User(db.Model):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(100), nullable=False)
    identity_card = Column(String(20), nullable=False, unique=True)
    phone = Column(String(15), nullable=False)
    email = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    avatar = Column(String(255), default='/static/images/default-avatar.png')

    account = relationship('Account', backref='user', uselist=False, cascade='all, delete-orphan')
    customer = relationship('Customer', backref='user', uselist=False, cascade='all, delete-orphan')
    staff = relationship('Staff', backref='user', uselist=False, cascade='all, delete-orphan')

    def __str__(self):
        return self.full_name


class Account(db.Model, UserMixin):
    __tablename__ = 'account'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    password = Column(String(100), nullable=False)
    role = Column(Enum(AccountRole), default=AccountRole.CUSTOMER, nullable=False)
    active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=datetime.now)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False, unique=True)

    def __str__(self):
        return self.username


class Customer(db.Model):
    __tablename__ = 'customer'

    user_id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    customer_type = Column(Enum(CustomerType), default=CustomerType.DOMESTIC, nullable=False)

    bookings = relationship('Booking', backref='customer', lazy=True)
    stay_details = relationship('StayDetail', backref='customer', lazy=True)

    def __str__(self):
        return self.user.full_name if self.user else str(self.user_id)


class Staff(db.Model):
    __tablename__ = 'staff'

    user_id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    position = Column(String(50), nullable=False)

    rentals = relationship('Rental', backref='staff', lazy=True)
    invoices = relationship('Invoice', backref='staff', lazy=True)
    manager = relationship('Manager', backref='staff', uselist=False, cascade='all, delete-orphan')

    def __str__(self):
        return self.user.full_name if self.user else str(self.user_id)


class Manager(db.Model):
    __tablename__ = 'manager'

    staff_id = Column(Integer, ForeignKey('staff.user_id'), primary_key=True)
    department = Column(String(100), default="Quản lý điều hành")


# 3. RoomType, Room & Regulation
class RoomType(db.Model):
    __tablename__ = 'room_type'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    base_price = Column(Float, nullable=False)
    description = Column(String(255), nullable=True)
    image = Column(String(255), default='/static/images/default-room.jpg')

    rooms = relationship('Room', backref='room_type', lazy=True)

    def __str__(self):
        return self.name


class Room(db.Model):
    __tablename__ = 'room'

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_number = Column(String(10), nullable=False, unique=True)
    status = Column(Enum(RoomStatus), default=RoomStatus.AVAILABLE, nullable=False)
    note = Column(String(255), nullable=True)
    room_type_id = Column(Integer, ForeignKey('room_type.id'), nullable=False)

    booking_details = relationship('BookingDetail', backref='room', lazy=True)
    rental_details = relationship('RentalDetail', backref='room', lazy=True)
    invoice_details = relationship('InvoiceDetail', backref='room', lazy=True)
    stay_details = relationship('StayDetail', backref='room', lazy=True)

    def __str__(self):
        return "Phòng " + self.room_number


class Regulation(db.Model):
    __tablename__ = 'regulation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    max_guests = Column(Integer, default=3, nullable=False)
    extra_guest_rate = Column(Float, default=0.25, nullable=False)
    foreign_guest_factor = Column(Float, default=1.5, nullable=False)
    deposit_rate = Column(Float, default=0.2, nullable=False)
    max_hold_days = Column(Integer, default=28, nullable=False)
    updated_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# 4. Booking & BookingDetail
class Booking(db.Model):
    __tablename__ = 'booking'

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_date = Column(DateTime, default=datetime.now, nullable=False)
    expected_checkin = Column(DateTime, nullable=False)
    expected_checkout = Column(DateTime, nullable=False)
    total_estimated = Column(Float, default=0.0, nullable=False)
    deposit_amount = Column(Float, default=0.0, nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING_CHECKIN, nullable=False)
    customer_id = Column(Integer, ForeignKey('customer.user_id'), nullable=False)

    details = relationship('BookingDetail', backref='booking', lazy=True, cascade='all, delete-orphan')
    stay_details = relationship('StayDetail', backref='booking', lazy=True)
    rental = relationship('Rental', backref='booking', uselist=False)


class BookingDetail(db.Model):
    __tablename__ = 'booking_detail'

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey('booking.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id'), nullable=False)
    price_at_booking = Column(Float, nullable=False)
    room_deposit = Column(Float, nullable=False)

