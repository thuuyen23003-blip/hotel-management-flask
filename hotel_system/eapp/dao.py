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


# add customer registration with conditional avatar upload

def register_customer(full_name, identity_card, phone, username, password,
                      email=None, address=None, customer_type=CustomerType.DOMESTIC, avatar=None):
    hashed_password = hashlib.md5(password.strip().encode('utf-8')).hexdigest()

    u = User(
        full_name=full_name.strip(),
        identity_card=identity_card.strip(),
        phone=phone.strip(),
        email=email.strip() if email else None,
        address=address.strip() if address else None
    )
    db.session.add(u)
    db.session.flush()

    if avatar:
        res = cloudinary.uploader.upload(
            avatar,
            public_id="hotel_avatars/user_" + str(u.id),
            overwrite=True
        )
        u.avatar = res.get('secure_url')

    cus = Customer(user_id=u.id, customer_type=customer_type)
    acc = Account(
        username=username.strip(),
        password=hashed_password,
        role=AccountRole.CUSTOMER,
        user_id=u.id
    )
    db.session.add_all([cus, acc])
    db.session.commit()
    return u

# add online booking creation and notification alerts
def create_online_booking(customer_user_id, selected_rooms, expected_checkin, expected_checkout, guest_list=None):
    reg = get_current_regulation()
    now = datetime.now()

    if not validate_max_hold_days(now, expected_checkin, reg.max_hold_days):
        raise ValueError("Ngày nhận phòng không được vượt quá " + str(reg.max_hold_days) + " ngày kể từ ngày đặt!")

    stay_days = max(1, (expected_checkout.date() - expected_checkin.date()).days)
    total_estimated = 0
    for r in selected_rooms.values():
        total_estimated += r['base_price'] * stay_days

    deposit_amount = calculate_deposit(total_estimated, reg.deposit_rate)

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
            db.session.add(StayDetail(booking_id=booking.id, customer_id=g['customer_id']))

    db.session.commit()

    user = User.query.get(customer_user_id)
    if user:
        notifier = NotificationService()
        notifier.send_email_confirmation(user.email, booking)

        tele_msg = "ĐƠN ĐẶT PHÒNG MỚI #" + str(booking.id) + "\n"
        tele_msg += "Khách hàng: " + user.full_name + " (" + user.phone + ")\n"
        tele_msg += "Nhận phòng: " + expected_checkin.strftime('%d/%m/%Y') + "\n"
        tele_msg += "Tiền cọc (20%): " + "{:,.0f}".format(deposit_amount) + " VNĐ"
        notifier.send_telegram_notification(tele_msg)

    return booking

# add auto cancel expired bookings
def auto_cancel_expired_bookings():
    now = datetime.now()
    expired_list = Booking.query.filter(
        Booking.status == BookingStatus.PENDING_CHECKIN,
        Booking.expected_checkin < now
    ).all()

    for b in expired_list:
        b.status = BookingStatus.EXPIRED_CANCELLED
        for d in b.details:
            if d.room.status == RoomStatus.BOOKED:
                d.room.status = RoomStatus.AVAILABLE
    if expired_list:
        db.session.commit()

# add receptionist checkin rental creation
def create_rental_checkin(staff_user_id, room_ids, expected_checkout, guest_customer_ids, booking_id=None):
    reg = get_current_regulation()
    if len(guest_customer_ids) > reg.max_guests * len(room_ids):
        raise ValueError("Vượt quá quy định tối đa " + str(reg.max_guests) + " khách/phòng!")

    deposit_deducted = 0.0
    if booking_id:
        booking = Booking.query.get(int(booking_id))
        if booking and booking.status == BookingStatus.PENDING_CHECKIN:
            booking.status = BookingStatus.CHECKED_IN
            deposit_deducted = booking.deposit_amount

    rental = Rental(
        checkin_date=datetime.now(),
        expected_checkout=expected_checkout,
        deposit_deducted=deposit_deducted,
        status=RentalStatus.ACTIVE,
        booking_id=booking_id,
        staff_id=staff_user_id
    )
    db.session.add(rental)
    db.session.flush()

    for rid in room_ids:
        room_obj = Room.query.get(int(rid))
        if room_obj:
            room_obj.status = RoomStatus.OCCUPIED
            db.session.add(RentalDetail(rental_id=rental.id, room_id=room_obj.id))

    for cid in guest_customer_ids:
        db.session.add(StayDetail(rental_id=rental.id, customer_id=int(cid)))

    db.session.commit()
    return rental

# add checkout invoice calculation
def checkout_and_create_invoice(rental_id, staff_user_id, payment_method='Tiền mặt'):
    rental = Rental.query.get(int(rental_id))
    reg = get_current_regulation()
    now = datetime.now()

    guest_count = len(rental.stay_details)
    has_foreign = False
    for s in rental.stay_details:
        if s.customer.customer_type == CustomerType.FOREIGN:
            has_foreign = True
            break

    invoice = Invoice(
        payment_date=now,
        total_room_amount=0,
        deposit_deducted=rental.deposit_deducted,
        final_amount=0,
        payment_method=payment_method,
        rental_id=rental.id,
        staff_id=staff_user_id
    )
    db.session.add(invoice)
    db.session.flush()

    total_room_amount = 0
    for rd in rental.rental_details:
        rd.actual_checkout = now
        rd.room.status = RoomStatus.CLEANING

        stay_days = max(1, (now.date() - rental.checkin_date.date()).days)
        calc = calculate_room_checkout(
            base_price=rd.room.room_type.base_price,
            stay_days=stay_days,
            guest_count=guest_count,
            has_foreign_guest=has_foreign,
            regulation=reg
        )
        total_room_amount += calc['room_total']

        db.session.add(InvoiceDetail(
            invoice_id=invoice.id,
            room_id=rd.room.id,
            stay_days=calc['stay_days'],
            applied_price=rd.room.room_type.base_price,
            extra_guest_rate=calc['extra_guest_rate'],
            guest_factor=calc['guest_factor'],
            room_total=calc['room_total']
        ))

    invoice.total_room_amount = total_room_amount
    invoice.final_amount = max(0, total_room_amount - rental.deposit_deducted)
    rental.status = RentalStatus.PAID

    db.session.commit()
    return invoice

