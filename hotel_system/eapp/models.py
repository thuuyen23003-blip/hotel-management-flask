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
    image = Column(String(255), default='/static/images/default-room.png')
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

# 8. Invoices:

class Invoice(BaseModel):
    __tablename__ = 'invoice'
    payment_date = Column(DateTime, default=datetime.now)
    total_room_amount = Column(Float, nullable=False)
    deposit_deducted = Column(Float, default=0.0)
    final_amount = Column(Float, nullable=False)
    payment_method = Column(String(50), nullable=False)
    rental_id = Column(Integer, ForeignKey('rental.id'), unique=True, nullable=False)
    staff_id = Column(Integer, ForeignKey('staff.user_id'), nullable=False)

    details = relationship('InvoiceDetail', backref='invoice', lazy=True)

class InvoiceDetail(BaseModel):
    __tablename__ = 'invoice_detail'
    invoice_id = Column(Integer, ForeignKey('invoice.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id'), nullable=False)
    stay_days = Column(Integer, nullable=False)
    applied_price = Column(Float, nullable=False)
    extra_guest_rate = Column(Float, default=0.0)
    guest_factor = Column(Float, default=1.0)
    room_total = Column(Float, nullable=False)

    room = relationship('Room', lazy=True)

# 9. Seed data:

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Regulation.query.first():
            db.session.add(Regulation(
                max_guests=3,
                extra_guest_rate=0.25,
                foreign_guest_factor=1.5,
                max_hold_days=28,
                deposit_rate=0.20
            ))

            # 1. Create 4 standard hotel room types
            rt1 = RoomType(name='Standard', base_price=500000, description='Phòng tiêu chuẩn đầy đủ tiện nghi cơ bản (22m²)')
            rt2 = RoomType(name='Superior', base_price=700000, description='Phòng nâng cấp có cửa sổ lớn thoáng mát (30m²)')
            rt3 = RoomType(name='Deluxe', base_price=1000000, description='Phòng cao cấp tầng cao, tầm nhìn đẹp (38m²)')
            rt4 = RoomType(name='Family Room', base_price=1300000, description='Phòng gia đình rộng rãi bố trí 2 giường lớn (48m²)')
            db.session.add_all([rt1, rt2, rt3, rt4])
            db.session.commit()

            # 2. Create 16 rooms across 4 floors (4 rooms per floor)
            rooms = []
            for i in range(1, 5):
                rooms.append(Room(room_number=f'10{i}', room_type_id=rt1.id))
                rooms.append(Room(room_number=f'20{i}', room_type_id=rt2.id))
                rooms.append(Room(room_number=f'30{i}', room_type_id=rt3.id))
                rooms.append(Room(room_number=f'40{i}', room_type_id=rt4.id))
            db.session.add_all(rooms)

            # 3. Create 6 sample accounts (1 Manager, 2 Staffs, 3 Customers)
            pw = hashlib.md5('123456'.encode('utf-8')).hexdigest()

            u_mgr = User(full_name='Tran Vo Thi Thu Uyen', identity_card='079303000001', phone='0901234561', email='manager@hotel.vn', address='Ho Chi Minh City')
            u_stf1 = User(full_name='Nguyen Van Le Tan', identity_card='079303000002', phone='0901234562', email='staff1@hotel.vn', address='Ho Chi Minh City')
            u_stf2 = User(full_name='Pham Thi Thu Ngan', identity_card='079303000003', phone='0901234563', email='staff2@hotel.vn', address='Ho Chi Minh City')
            u_cus1 = User(full_name='Le Minh Khach', identity_card='079303000004', phone='0901234564', email='customer1@gmail.com', address='Hanoi')
            u_cus2 = User(full_name='Tran Thi Mai', identity_card='079303000005', phone='0901234565', email='customer2@gmail.com', address='Da Nang')
            u_for = User(full_name='Johnathan Smith', identity_card='P12345678', phone='0901234566', email='john.smith@gmail.com', address='New York, USA')

            db.session.add_all([u_mgr, u_stf1, u_stf2, u_cus1, u_cus2, u_for])
            db.session.commit()

            db.session.add_all([
                Manager(user_id=u_mgr.id),
                Staff(user_id=u_stf1.id, position='Morning Receptionist'),
                Staff(user_id=u_stf2.id, position='Evening Receptionist'),
                Customer(user_id=u_cus1.id, customer_type=CustomerType.DOMESTIC),
                Customer(user_id=u_cus2.id, customer_type=CustomerType.DOMESTIC),
                Customer(user_id=u_for.id, customer_type=CustomerType.FOREIGN),

                Account(username='manager', password=pw, role=AccountRole.MANAGER, user_id=u_mgr.id),
                Account(username='staff1', password=pw, role=AccountRole.STAFF, user_id=u_stf1.id),
                Account(username='staff2', password=pw, role=AccountRole.STAFF, user_id=u_stf2.id),
                Account(username='customer1', password=pw, role=AccountRole.CUSTOMER, user_id=u_cus1.id),
                Account(username='customer2', password=pw, role=AccountRole.CUSTOMER, user_id=u_cus2.id),
                Account(username='foreign_guest', password=pw, role=AccountRole.CUSTOMER, user_id=u_for.id)
            ])
            db.session.commit()
            print("Successfully initialized 15 tables, 4 standard room types, 16 rooms, and 6 accounts!")








