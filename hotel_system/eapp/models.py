import enum
import hashlib
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from eapp import app, db


# 1. Enumerations
class AccountRole(enum.Enum):
    CUSTOMER = "Khách hàng"
    STAFF = "Nhân viên"
    MANAGER = "Quản lý"


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
    avatar = Column(String(255), default='/static/images/default-avatar.jpg')

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


# Loại khách (Nội địa, Nước ngoài...) và hệ số nhân giá phòng - quản lý được trong trang Admin
class CustomerType(db.Model):
    __tablename__ = 'customer_type'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    coefficient = Column(Float, default=1.0, nullable=False)

    customers = relationship('Customer', backref='customer_type', lazy=True)

    def __str__(self):
        return self.name


class Customer(db.Model):
    __tablename__ = 'customer'

    user_id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    customer_type_id = Column(Integer, ForeignKey('customer_type.id'), nullable=False)

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

    # Đơn giá của phòng = đơn giá của loại phòng
    @property
    def price(self):
        return self.room_type.base_price

    def __str__(self):
        return "Phòng " + self.room_number


class Regulation(db.Model):
    __tablename__ = 'regulation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    max_guests = Column(Integer, default=3, nullable=False)
    extra_guest_rate = Column(Float, default=0.25, nullable=False)
    deposit_rate = Column(Float, default=0.2, nullable=False)
    max_hold_days = Column(Integer, default=28, nullable=False)
    updated_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    manager_id = Column(Integer, ForeignKey('manager.staff_id'), nullable=True)

    manager = relationship('Manager', backref='regulations')


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
    __table_args__ = (UniqueConstraint('booking_id', 'room_id', name='uq_booking_room'),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey('booking.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id'), nullable=False)
    price_at_booking = Column(Float, nullable=False)
    room_deposit = Column(Float, nullable=False)


# 5. Rental, RentalDetail & StayDetail
class Rental(db.Model):
    __tablename__ = 'rental'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_date = Column(DateTime, default=datetime.now, nullable=False)
    checkin_date = Column(DateTime, default=datetime.now, nullable=False)
    expected_checkout = Column(DateTime, nullable=False)
    deposit_deducted = Column(Float, default=0.0, nullable=False)
    status = Column(Enum(RentalStatus), default=RentalStatus.ACTIVE, nullable=False)

    booking_id = Column(Integer, ForeignKey('booking.id'), nullable=True, unique=True)
    staff_id = Column(Integer, ForeignKey('staff.user_id'), nullable=False)

    rental_details = relationship('RentalDetail', backref='rental', lazy=True, cascade='all, delete-orphan')
    stay_details = relationship('StayDetail', backref='rental', lazy=True)
    invoice = relationship('Invoice', backref='rental', uselist=False)


class RentalDetail(db.Model):
    __tablename__ = 'rental_detail'
    __table_args__ = (UniqueConstraint('rental_id', 'room_id', name='uq_rental_room'),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    rental_id = Column(Integer, ForeignKey('rental.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id'), nullable=False)
    actual_checkout = Column(DateTime, nullable=True)


class StayDetail(db.Model):
    __tablename__ = 'stay_detail'

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey('booking.id'), nullable=True)
    rental_id = Column(Integer, ForeignKey('rental.id'), nullable=True)
    room_id = Column(Integer, ForeignKey('room.id'), nullable=True)
    customer_id = Column(Integer, ForeignKey('customer.user_id'), nullable=False)


# 6. Invoice & InvoiceDetail
class Invoice(db.Model):
    __tablename__ = 'invoice'

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_date = Column(DateTime, default=datetime.now, nullable=False)
    total_room_amount = Column(Float, nullable=False)
    deposit_deducted = Column(Float, default=0.0, nullable=False)
    final_amount = Column(Float, nullable=False)
    payment_method = Column(String(50), default="Tiền mặt", nullable=False)

    rental_id = Column(Integer, ForeignKey('rental.id'), nullable=False, unique=True)
    staff_id = Column(Integer, ForeignKey('staff.user_id'), nullable=False)

    details = relationship('InvoiceDetail', backref='invoice', lazy=True, cascade='all, delete-orphan')


class InvoiceDetail(db.Model):
    __tablename__ = 'invoice_detail'
    __table_args__ = (UniqueConstraint('invoice_id', 'room_id', name='uq_invoice_room'),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('invoice.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id'), nullable=False)
    stay_days = Column(Integer, nullable=False)
    applied_price = Column(Float, nullable=False)
    extra_guest_rate = Column(Float, default=0.0, nullable=False)
    guest_factor = Column(Float, default=1.0, nullable=False)
    room_total = Column(Float, nullable=False)


# 7. Seed Initial Database & Aurelia Hotel & Suites Sample Data
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        if not CustomerType.query.first():
            db.session.add_all([
                CustomerType(name="Nội địa", coefficient=1.0),
                CustomerType(name="Nước ngoài", coefficient=1.5)
            ])
            db.session.commit()

        if not Account.query.first():
            pw_hash = hashlib.md5("123456".encode('utf-8')).hexdigest()

            u_mgr = User(full_name="Trần Võ Thị Thu Uyên", identity_card="079303000001", phone="0901000001",
                         email="manager@aureliahotel.vn")
            u_stf = User(full_name="Lễ Tân Aurelia", identity_card="079303000002", phone="0901000002",
                         email="reception@aureliahotel.vn")
            u_cus = User(full_name="Nguyễn Minh Anh", identity_card="079303000003", phone="0901000003",
                         email="khachhang@gmail.com")
            db.session.add_all([u_mgr, u_stf, u_cus])
            db.session.flush()

            stf_mgr = Staff(user_id=u_mgr.id, position="Quản lý khách sạn")
            stf_rec = Staff(user_id=u_stf.id, position="Nhân viên lễ tân")
            cus_dom = Customer(user_id=u_cus.id, customer_type_id=CustomerType.query.first().id)
            db.session.add_all([stf_mgr, stf_rec, cus_dom])
            db.session.flush()

            mgr = Manager(staff_id=u_mgr.id, department="Ban Giám Đốc Aurelia")
            acc_mgr = Account(username="admin", password=pw_hash, role=AccountRole.MANAGER, user_id=u_mgr.id)
            acc_stf = Account(username="staff", password=pw_hash, role=AccountRole.STAFF, user_id=u_stf.id)
            acc_cus = Account(username="customer", password=pw_hash, role=AccountRole.CUSTOMER, user_id=u_cus.id)
            db.session.add_all([mgr, acc_mgr, acc_stf, acc_cus])
            db.session.flush()

            if not Regulation.query.first():
                reg = Regulation(
                    max_guests=3,
                    extra_guest_rate=0.25,
                    deposit_rate=0.2,
                    max_hold_days=28,
                    manager_id=mgr.staff_id
                )
                db.session.add(reg)

        if not RoomType.query.first():
            rt1 = RoomType(name="Standard Single", base_price=500000,
                           description="Phòng tiêu chuẩn 1 giường đơn, đầy đủ tiện nghi.")
            rt2 = RoomType(name="Superior Double", base_price=800000,
                           description="Phòng hạng trung 1 giường đôi rộng rãi, ban công thoáng mát.")
            rt3 = RoomType(name="Deluxe Twin", base_price=1200000,
                           description="Phòng cao cấp 2 giường lớn, view hướng phố.")
            rt4 = RoomType(name="Aurelia Suite VIP", base_price=2500000,
                           description="Phòng hạng sang diện tích lớn, phòng khách riêng biệt.")
            db.session.add_all([rt1, rt2, rt3, rt4])
            db.session.flush()

            sample_rooms = [
                Room(room_number="101", room_type_id=rt1.id),
                Room(room_number="102", room_type_id=rt1.id),
                Room(room_number="103", room_type_id=rt1.id),
                Room(room_number="104", room_type_id=rt1.id),
                Room(room_number="201", room_type_id=rt2.id),
                Room(room_number="202", room_type_id=rt2.id),
                Room(room_number="203", room_type_id=rt2.id),
                Room(room_number="204", room_type_id=rt2.id),
                Room(room_number="301", room_type_id=rt3.id),
                Room(room_number="302", room_type_id=rt3.id),
                Room(room_number="303", room_type_id=rt3.id),
                Room(room_number="304", room_type_id=rt3.id),
                Room(room_number="401", room_type_id=rt4.id),
                Room(room_number="402", room_type_id=rt4.id),
                Room(room_number="403", room_type_id=rt4.id),
                Room(room_number="404", room_type_id=rt4.id)
            ]
            db.session.add_all(sample_rooms)

        db.session.commit()
        print("Database Aurelia Hotel & Suites initialized successfully!")
