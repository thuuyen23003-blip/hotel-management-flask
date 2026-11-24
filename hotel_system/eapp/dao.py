import hashlib
from datetime import datetime, timedelta
from sqlalchemy import func, extract
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


def get_busy_room_ids(checkin_date, checkout_date):
    all_rooms = Room.query.all()
    busy_ids = []
    for r in all_rooms:
        if not is_room_free(r.id, checkin_date, checkout_date):
            busy_ids.append(r.id)
    return busy_ids


def load_rooms(kw=None, room_type_id=None, checkin_date=None, checkout_date=None, page=1):
    query = Room.query.filter(Room.status != RoomStatus.CLEANING)

    if kw:
        clean_kw = kw.lower().replace('phòng', '').replace('phong', '').strip()
        query = query.filter(Room.room_number.contains(clean_kw))

    if room_type_id:
        query = query.filter(Room.room_type_id == int(room_type_id))

    if checkin_date and checkout_date:
        busy_ids = get_busy_room_ids(checkin_date, checkout_date)
        if busy_ids:
            query = query.filter(~Room.id.in_(busy_ids))

    page_size = app.config['PAGE_SIZE']
    start = (page - 1) * page_size
    return query.order_by(Room.room_number.asc()).slice(start, start + page_size).all()


def count_rooms(kw=None, room_type_id=None, checkin_date=None, checkout_date=None):
    query = Room.query.filter(Room.status != RoomStatus.CLEANING)

    if kw:
        clean_kw = kw.lower().replace('phòng', '').replace('phong', '').strip()
        query = query.filter(Room.room_number.contains(clean_kw))

    if room_type_id:
        query = query.filter(Room.room_type_id == int(room_type_id))

    if checkin_date and checkout_date:
        busy_ids = get_busy_room_ids(checkin_date, checkout_date)
        if busy_ids:
            query = query.filter(~Room.id.in_(busy_ids))

    return query.count()


def get_current_regulation():
    return Regulation.query.first()


# Phòng có trống trong khoảng ngày [checkin, checkout) không?
# Phòng KHÔNG trống nếu trùng ngày với phiếu đặt đang chờ nhận hoặc phiếu thuê đang ở
def is_room_free(room_id, checkin, checkout, ignore_booking_id=None):
    booking_query = (db.session.query(BookingDetail)
                     .join(Booking, Booking.id == BookingDetail.booking_id)
                     .filter(BookingDetail.room_id == room_id,
                             Booking.status == BookingStatus.PENDING_CHECKIN,
                             Booking.expected_checkin < checkout,
                             Booking.expected_checkout > checkin))
    if ignore_booking_id:
        booking_query = booking_query.filter(Booking.id != ignore_booking_id)
    if booking_query.first():
        return False

    rental_query = (db.session.query(RentalDetail)
                    .join(Rental, Rental.id == RentalDetail.rental_id)
                    .filter(RentalDetail.room_id == room_id,
                            Rental.status == RentalStatus.ACTIVE,
                            Rental.checkin_date < checkout,
                            Rental.expected_checkout > checkin))
    return rental_query.first() is None


# Id các phòng có phiếu đặt rơi vào ngày hôm nay (để hiện "Đã đặt" trên sơ đồ phòng)
def get_room_ids_booked_today():
    today = datetime.now().date()
    start = datetime(today.year, today.month, today.day)
    end = start + timedelta(days=1)
    rows = (db.session.query(BookingDetail.room_id)
            .join(Booking, Booking.id == BookingDetail.booking_id)
            .filter(Booking.status == BookingStatus.PENDING_CHECKIN,
                    Booking.expected_checkin < end,
                    Booking.expected_checkout > start).all())
    return [r[0] for r in rows]


def load_customer_types():
    return CustomerType.query.all()


# Tra cứu phiếu đặt phòng đang chờ nhận, có thể tìm theo họ tên khách
def load_pending_bookings(kw=None):
    query = Booking.query.filter(Booking.status == BookingStatus.PENDING_CHECKIN)
    if kw:
        query = (query.join(Customer, Customer.user_id == Booking.customer_id)
                 .join(User, User.id == Customer.user_id)
                 .filter(User.full_name.contains(kw)))
    return query.all()


# Tìm khách theo CMND, nếu chưa có thì tạo khách mới (khách không cần tài khoản)
def get_or_create_customer(full_name, identity_card, customer_type_id, address=None):
    user = User.query.filter(User.identity_card == identity_card).first()
    if not user:
        user = User(full_name=full_name, identity_card=identity_card, phone='', address=address)
        db.session.add(user)
        db.session.flush()

    customer = Customer.query.get(user.id)
    if not customer:
        customer = Customer(user_id=user.id, customer_type_id=customer_type_id)
        db.session.add(customer)
        db.session.flush()

    active_stay = (db.session.query(StayDetail)
                   .join(Rental, Rental.id == StayDetail.rental_id)
                   .filter(StayDetail.customer_id == customer.user_id,
                           Rental.status == RentalStatus.ACTIVE).first())
    if active_stay:
        raise ValueError(
            "Khách hàng " + user.full_name + " (CCCD: " + identity_card + ") hiện đang lưu trú tại một phòng khác!")

    return customer


# Chia đều khách vào các phòng: khách 1 -> phòng 1, khách 2 -> phòng 2, khách 3 -> phòng 1 ...
def assign_guests_to_rooms(rental, rooms):
    stays = StayDetail.query.filter_by(rental_id=rental.id).order_by(StayDetail.id).all()
    for i in range(len(stays)):
        stays[i].room_id = rooms[i % len(rooms)].id


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
                      customer_type_id=None):
    hashed_pw = hashlib.md5(password.strip().encode('utf-8')).hexdigest()

    user = User(
        full_name=full_name.strip(),
        identity_card=identity_card.strip(),
        phone=phone.strip(),
        email=email.strip() if email else None,
        address=address.strip() if address else None,
        avatar=avatar if avatar else '/static/images/default-avatar.jpg'
    )
    db.session.add(user)
    db.session.flush()

    customer = Customer(user_id=user.id, customer_type_id=customer_type_id)
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

    # Mỗi phòng phải còn trống trong khoảng ngày đã chọn (phòng không bị khóa từ lúc đặt)
    for r in selected_rooms.values():
        if not is_room_free(int(r['id']), expected_checkin, expected_checkout):
            raise ValueError(
                "Phòng " + str(r['room_number']) + " đã có người đặt hoặc đang thuê trong khoảng ngày này!")

    stay_days = calculate_stay_days(expected_checkin, expected_checkout)
    total_estimated = 0
    for r in selected_rooms.values():
        total_estimated += r['base_price'] * stay_days

    deposit_amount = calculate_deposit(total_estimated, reg.deposit_rate)

    if not Customer.query.get(customer_user_id):
        db.session.add(Customer(user_id=customer_user_id, customer_type_id=CustomerType.query.first().id))
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
        room_total = r['base_price'] * stay_days
        detail = BookingDetail(
            booking_id=booking.id,
            room_id=int(r['id']),
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
def create_rental_from_booking(booking_id, staff_user_id, room_replacements=None, guests=None):
    booking = Booking.query.get(booking_id)
    reg = get_current_regulation()
    now = datetime.now()

    if not booking or booking.status != BookingStatus.PENDING_CHECKIN:
        raise ValueError("Phiếu đặt phòng không tồn tại hoặc đã được xử lý!")

    if not validate_max_hold_days(booking.booking_date, now, reg.max_hold_days):
        booking.status = BookingStatus.EXPIRED_CANCELLED
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

    rooms = []  # các phòng thực tế của phiếu thuê (sau khi đổi phòng nếu có)
    replaced_notes = []
    for d in booking.details:
        target_room = d.room
        if room_replacements and str(d.room_id) in room_replacements:
            new_room_id = int(room_replacements[str(d.room_id)])
            new_room = Room.query.get(new_room_id)
            # Phòng mới phải đang trống và không bị ai đặt trong thời gian khách ở
            if (new_room and new_room.status == RoomStatus.AVAILABLE
                    and is_room_free(new_room.id, now, booking.expected_checkout, booking.id)):
                replaced_notes.append("Phòng " + target_room.room_number + " -> " + new_room.room_number)
                target_room = new_room

        if target_room.status != RoomStatus.AVAILABLE:
            raise ValueError(
                "Phòng " + target_room.room_number + " chưa sẵn sàng (đang thuê hoặc đang dọn), vui lòng đổi sang phòng trống!")

        target_room.status = RoomStatus.OCCUPIED
        rooms.append(target_room)
        db.session.add(RentalDetail(rental_id=rental.id, room_id=target_room.id))

    # Khách đã khai trong phiếu đặt (người đặt) chuyển sang phiếu thuê
    guest_ids = []
    for s in booking.stay_details:
        s.rental_id = rental.id
        guest_ids.append(s.customer_id)

    # Khách nhập thêm lúc nhận phòng (bảng khách trong phiếu thuê)
    if guests:
        for g in guests:
            customer = get_or_create_customer(**g)
            if customer.user_id not in guest_ids:
                guest_ids.append(customer.user_id)
                db.session.add(StayDetail(booking_id=booking.id, rental_id=rental.id,
                                          customer_id=customer.user_id))

    if len(guest_ids) < len(rooms):
        db.session.rollback()
        raise ValueError("Mỗi phòng thuê phải có ít nhất 1 khách lưu trú!")

    # Mỗi phòng ở tối đa max_guests khách
    if len(guest_ids) > reg.max_guests * len(rooms):
        db.session.rollback()
        raise ValueError("Số lượng khách vượt quá quy định tối đa " + str(reg.max_guests) + " khách/phòng!")

    db.session.flush()
    assign_guests_to_rooms(rental, rooms)
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


def create_walkin_rental(staff_user_id, room_ids, expected_checkout, guests):
    reg = get_current_regulation()
    now = datetime.now()

    if not room_ids:
        raise ValueError("Vui lòng chọn ít nhất 1 phòng!")
    if not guests:
        raise ValueError("Vui lòng nhập thông tin ít nhất 1 khách!")
    if expected_checkout.date() <= now.date():
        raise ValueError("Ngày trả phòng phải sau ngày hôm nay!")
    if len(guests) < len(room_ids):
        raise ValueError("Mỗi phòng thuê phải có ít nhất 1 khách lưu trú!")
    if len(guests) > reg.max_guests * len(room_ids):
        raise ValueError("Số lượng khách vượt quá quy định tối đa " + str(reg.max_guests) + " khách/phòng!")

    rooms = []
    for r_id in room_ids:
        room = Room.query.get(int(r_id))
        if not room or room.status != RoomStatus.AVAILABLE or not is_room_free(room.id, now, expected_checkout):
            raise ValueError("Có phòng không còn trống hoặc đã có người đặt trong thời gian thuê!")
        rooms.append(room)

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

    for room in rooms:
        room.status = RoomStatus.OCCUPIED
        db.session.add(RentalDetail(rental_id=rental.id, room_id=room.id))

    guest_ids = []
    for g in guests:
        customer = get_or_create_customer(**g)
        if customer.user_id not in guest_ids:
            guest_ids.append(customer.user_id)
            db.session.add(StayDetail(rental_id=rental.id, customer_id=customer.user_id))

    db.session.flush()
    assign_guests_to_rooms(rental, rooms)
    db.session.commit()
    return rental


# Nhân viên lập phiếu đặt phòng trực tiếp tại quầy (khách đến gặp nhân viên để đặt phòng)
# guests[0] là người đặt phòng, các dòng sau là khách ở cùng
def create_booking_at_counter(room_ids, expected_checkin, expected_checkout, guests):
    reg = get_current_regulation()

    if not room_ids:
        raise ValueError("Vui lòng chọn ít nhất 1 phòng!")
    if not guests:
        raise ValueError("Vui lòng nhập thông tin người đặt phòng!")
    if expected_checkout.date() <= expected_checkin.date():
        raise ValueError("Ngày trả phòng phải sau ngày nhận phòng!")
    if len(guests) > reg.max_guests * len(room_ids):
        raise ValueError("Số lượng khách vượt quá quy định tối đa " + str(reg.max_guests) + " khách/phòng!")

    selected_rooms = {}
    for r_id in room_ids:
        room = Room.query.get(int(r_id))
        if not room:
            raise ValueError("Không tìm thấy phòng được chọn!")
        selected_rooms[str(room.id)] = {
            'id': room.id,
            'room_number': room.room_number,
            'base_price': room.room_type.base_price
        }

    booker = get_or_create_customer(**guests[0])

    guest_list = []
    for g in guests[1:]:
        customer = get_or_create_customer(**g)
        if customer.user_id != booker.user_id:
            guest_list.append({'customer_id': customer.user_id})

    return create_online_booking(booker.user_id, selected_rooms, expected_checkin, expected_checkout, guest_list)


# 5. Checkout, Pre-payment, Invoice Creation & Electronic Invoice Email
# Tính tiền phòng của 1 phiếu thuê. Dùng chung cho hóa đơn và số tiền gửi sang MoMo
# để hai con số luôn giống nhau. Trả về (tổng tiền phòng, danh sách chi tiết từng phòng)
def calculate_rental_bill(rental, is_prepaid):
    reg = get_current_regulation()
    end_date = rental.expected_checkout if is_prepaid else datetime.now()
    stay_days = calculate_stay_days(rental.checkin_date, end_date)

    total_room_amount = 0.0
    lines = []
    for rd in rental.rental_details:
        # Khách đang ở phòng này
        room_stays = [st for st in rental.stay_details if st.room_id == rd.room_id]
        guest_count = max(1, len(room_stays))

        # Hệ số của phòng = hệ số lớn nhất trong các loại khách của phòng (vd có khách nước ngoài -> 1.5)
        coefficients = [st.customer.customer_type.coefficient for st in room_stays]
        guest_factor = max(coefficients) if coefficients else 1.0

        calc = calculate_room_checkout(
            base_price=rd.room.room_type.base_price,
            stay_days=stay_days,
            guest_count=guest_count,
            guest_factor=guest_factor,
            regulation=reg
        )
        total_room_amount += calc['room_total']
        lines.append({'room_id': rd.room_id, 'applied_price': rd.room.room_type.base_price, 'calc': calc})

    return total_room_amount, lines


def checkout_and_create_invoice(rental_id, staff_user_id, payment_method="Tiền mặt", is_prepaid=False):
    rental = Rental.query.get(rental_id)
    now = datetime.now()

    if not rental or rental.status != RentalStatus.ACTIVE:
        raise ValueError("Phiếu thuê phòng không tồn tại hoặc đã hoàn tất trả phòng!")

    # Case 1: Already pre-paid earlier -> Now guest is checking out (only update room status & time)
    if rental.invoice and not is_prepaid:
        for rd in rental.rental_details:
            rd.actual_checkout = now
            rd.room.status = RoomStatus.CLEANING
        rental.status = RentalStatus.PAID
        db.session.commit()
        return rental.invoice

    if rental.invoice and is_prepaid:
        raise ValueError("Phiếu thuê phòng này đã được thanh toán trước rồi!")

    # Case 2: Calculate room charges and create invoice
    all_stays = rental.stay_details
    total_room_amount, lines = calculate_rental_bill(rental, is_prepaid)

    invoice = Invoice(
        payment_date=now,
        total_room_amount=total_room_amount,
        deposit_deducted=rental.deposit_deducted,
        final_amount=max(0.0, total_room_amount - rental.deposit_deducted),
        payment_method=payment_method,
        rental_id=rental.id,
        staff_id=staff_user_id
    )
    db.session.add(invoice)
    db.session.flush()

    for line in lines:
        calc = line['calc']
        db.session.add(InvoiceDetail(
            invoice_id=invoice.id,
            room_id=line['room_id'],
            stay_days=calc['stay_days'],
            applied_price=line['applied_price'],
            extra_guest_rate=calc['extra_guest_rate'],
            guest_factor=calc['guest_factor'],
            room_total=calc['room_total']
        ))

    # Trả phòng thật sự (không phải thanh toán trước): ghi giờ trả, phòng chuyển sang đang dọn
    if not is_prepaid:
        for rd in rental.rental_details:
            rd.actual_checkout = now
            rd.room.status = RoomStatus.CLEANING
        rental.status = RentalStatus.PAID

    db.session.commit()

    primary_user = None
    if rental.booking and rental.booking.customer:
        primary_user = rental.booking.customer.user
    elif all_stays:
        primary_user = all_stays[0].customer.user

    notifier = NotificationService()
    if primary_user and primary_user.email:
        notifier.send_invoice_email(primary_user.email, invoice, primary_user.full_name)

    action_label = "THANH TOÁN TRƯỚC HÓA ĐƠN #" if is_prepaid else "THANH TOÁN HÓA ĐƠN #"
    tele_msg = action_label + str(invoice.id) + "\n"
    tele_msg += "Tổng tiền phòng: " + "{:,.0f}".format(invoice.total_room_amount) + " VNĐ\n"
    tele_msg += "Thực thu: " + "{:,.0f}".format(invoice.final_amount) + " VNĐ (" + payment_method + ")"
    notifier.send_telegram_notification(tele_msg)

    return invoice


# 6. Admin Statistics Queries (Matches Exam Report Tables with Count & Percentage)
def stats_rooms_by_type():
    return (db.session.query(RoomType.id, RoomType.name, func.count(Room.id))
            .outerjoin(Room, Room.room_type_id == RoomType.id)
            .group_by(RoomType.id).all())


# Doanh thu từng loại phòng trong tháng được chọn
def stats_revenue_by_room_type(month, year):
    # Chỉ lấy các hóa đơn thuộc tháng/năm được chọn
    rows = (db.session.query(RoomType.id,
                             func.sum(InvoiceDetail.room_total),
                             func.count(InvoiceDetail.id))
            .join(Room, Room.room_type_id == RoomType.id)
            .join(InvoiceDetail, InvoiceDetail.room_id == Room.id)
            .join(Invoice, Invoice.id == InvoiceDetail.invoice_id)
            .filter(extract('month', Invoice.payment_date) == month,
                    extract('year', Invoice.payment_date) == year)
            .group_by(RoomType.id).all())

    # Đưa vào dict: id loại phòng -> (doanh thu, số lượt thuê)
    data = {}
    for r in rows:
        data[r[0]] = (r[1], r[2])

    # Loại phòng không có hóa đơn trong tháng thì doanh thu = 0
    grand_total = 0
    for v in data.values():
        grand_total += v[0]

    result = []
    for rt in RoomType.query.all():
        revenue, count = data.get(rt.id, (0, 0))
        pct = round(revenue / grand_total * 100, 1) if grand_total > 0 else 0.0
        result.append((rt.name, revenue, count, pct))
    return result


# Số ngày thuê của từng phòng trong tháng được chọn
def stats_occupancy_by_room(month, year):
    rows = (db.session.query(InvoiceDetail.room_id, func.sum(InvoiceDetail.stay_days))
            .join(Invoice, Invoice.id == InvoiceDetail.invoice_id)
            .filter(extract('month', Invoice.payment_date) == month,
                    extract('year', Invoice.payment_date) == year)
            .group_by(InvoiceDetail.room_id).all())

    data = {}
    for r in rows:
        data[r[0]] = r[1]

    total_all_days = 0
    for days in data.values():
        total_all_days += days

    result = []
    for room in Room.query.order_by(Room.room_number).all():
        days = data.get(room.id, 0)
        pct = round(days / total_all_days * 100, 1) if total_all_days > 0 else 0.0
        result.append((room.room_number, days, pct))
    return result
