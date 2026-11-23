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


# 3. Online Booking & Notifications
def create_online_booking(customer_user_id, selected_rooms, expected_checkin,
                          expected_checkout, guest_list=None):
    reg = get_current_regulation()
    now = datetime.now()

    if not validate_max_hold_days(now, expected_checkin, reg.max_hold_days):
        raise ValueError("Ngày nhận phòng không được vượt quá " + str(reg.max_hold_days) + " ngày kể từ ngày đặt!")

    stay_days = calculate_stay_days(expected_checkin, expected_checkout)
    total_estimated = 0
    for r in selected_rooms.values():
        total_estimated += r['base_price'] * stay_days

    deposit_amount = calculate_deposit(total_estimated, reg.deposit_rate)

    if not Customer.query.get(customer_user_id):
        db.session.add(Customer(user_id=customer_user_id, customer_type=CustomerType.DOMESTIC))
        db.session.flush()

    booking = Booking(
        booking_date=now,
        expected_checkin=expected_checkin,
        expected_checkout=expected_checkout,
        total_estimated=total_estimated,
        deposit_amount=deposit_amount,
        status=BookingStatus.PENDING_CHECKIN,
        customer_id=customer_user_id
    )
    db.session.add(booking)
    db.session.flush()

    for r in selected_rooms.values():
        room_obj = Room.query.get(int(r['id']))
        if room_obj and room_obj.status == RoomStatus.AVAILABLE:
            room_obj.status = RoomStatus.BOOKED
            room_total = r['base_price'] * stay_days
            detail = BookingDetail(
                booking_id=booking.id,
                room_id=room_obj.id,
                price_at_booking=r['base_price'],
                room_deposit=calculate_deposit(room_total, reg.deposit_rate)
            )
            db.session.add(detail)

    db.session.add(StayDetail(booking_id=booking.id, customer_id=customer_user_id))
    if guest_list:
        for g in guest_list:
            db.session.add(StayDetail(
                booking_id=booking.id,
                room_id=g.get('room_id'),
                customer_id=g['customer_id']
            ))

    db.session.commit()

    user = User.query.get(customer_user_id)
    if user:
        notifier = NotificationService()
        notifier.send_email_confirmation(user.email, booking, user.full_name)

        # 1. Detailed message for Manager via Telegram
        tele_msg = "ĐƠN ĐẶT PHÒNG MỚI #" + str(booking.id) + "\n"
        tele_msg += "Khách hàng: " + user.full_name + " (" + user.phone + ")\n"
        tele_msg += "Nhận phòng: " + expected_checkin.strftime('%d/%m/%Y') + "\n"
        tele_msg += "Tiền cọc (20%): " + "{:,.0f}".format(deposit_amount) + " VNĐ"
        notifier.send_telegram_notification(tele_msg)

        # 2. Concise check-in summary message for Customer
        room_nums = ", ".join(r['room_number'] for r in selected_rooms.values())
        notifier.send_customer_checkin_summary(booking, room_nums, user.full_name)

    return booking


def get_bookings_by_customer(customer_user_id):
    return Booking.query.filter_by(customer_id=customer_user_id).order_by(Booking.id.desc()).all()


# 4. Reception Check-in (Supports Room Replacement & 28-day Expiry Check)
def create_rental_from_booking(booking_id, staff_user_id, room_replacements=None):
    booking = Booking.query.get(booking_id)
    reg = get_current_regulation()
    now = datetime.now()

    if not booking or booking.status != BookingStatus.PENDING_CHECKIN:
        raise ValueError("Phiếu đặt phòng không tồn tại hoặc đã được xử lý!")

    if not validate_max_hold_days(booking.booking_date, now, reg.max_hold_days):
        booking.status = BookingStatus.EXPIRED_CANCELLED
        for d in booking.details:
            if d.room.status == RoomStatus.BOOKED:
                d.room.status = RoomStatus.AVAILABLE
        db.session.commit()
        raise ValueError("Phiếu đặt phòng đã quá hạn " + str(reg.max_hold_days) + " ngày và bị hủy (không hoàn cọc)!")

    booking.status = BookingStatus.CHECKED_IN
    rental = Rental(
        created_date=now,
        checkin_date=now,
        expected_checkout=booking.expected_checkout,
        deposit_deducted=booking.deposit_amount,
        status=RentalStatus.ACTIVE,
        booking_id=booking.id,
        staff_id=staff_user_id
    )
    db.session.add(rental)
    db.session.flush()

    replaced_notes = []
    for d in booking.details:
        target_room = d.room
        if room_replacements and str(d.room_id) in room_replacements:
            new_room_id = int(room_replacements[str(d.room_id)])
            new_room = Room.query.get(new_room_id)
            if new_room and new_room.status == RoomStatus.AVAILABLE:
                replaced_notes.append("Phòng " + target_room.room_number + " -> " + new_room.room_number)
                if target_room.status == RoomStatus.BOOKED:
                    target_room.status = RoomStatus.AVAILABLE
                target_room = new_room

        target_room.status = RoomStatus.OCCUPIED
        db.session.add(RentalDetail(rental_id=rental.id, room_id=target_room.id))

    for s in booking.stay_details:
        s.rental_id = rental.id

    db.session.commit()

    notifier = NotificationService()
    if now.date() < booking.expected_checkin.date():
        notifier.send_telegram_notification(
            "CHECK-IN SỚM: Phiếu đặt #" + str(booking.id) + " nhận phòng lúc " + now.strftime('%d/%m/%Y %H:%M')
        )
    if replaced_notes:
        notifier.send_telegram_notification(
            "ĐỔI PHÒNG LÚC CHECK-IN (Phiếu #" + str(booking.id) + "): " + ", ".join(replaced_notes)
        )

    return rental


def create_walkin_rental(staff_user_id, room_ids, expected_checkout, customer_ids):
    reg = get_current_regulation()
    if len(customer_ids) > reg.max_guests * len(room_ids):
        raise ValueError("Số lượng khách vượt quá quy định tối đa " + str(reg.max_guests) + " khách/phòng!")

    now = datetime.now()
    rental = Rental(
        created_date=now,
        checkin_date=now,
        expected_checkout=expected_checkout,
        deposit_deducted=0.0,
        status=RentalStatus.ACTIVE,
        staff_id=staff_user_id
    )
    db.session.add(rental)
    db.session.flush()

    for r_id in room_ids:
        room = Room.query.get(int(r_id))
        if room and room.status == RoomStatus.AVAILABLE:
            room.status = RoomStatus.OCCUPIED
            db.session.add(RentalDetail(rental_id=rental.id, room_id=room.id))

    first_room_id = int(room_ids) if room_ids else None
    for c_id in customer_ids:
        db.session.add(StayDetail(
            rental_id=rental.id,
            room_id=first_room_id,
            customer_id=int(c_id)
        ))

    db.session.commit()
    return rental


