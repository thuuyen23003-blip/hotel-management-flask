import uuid
import math
from datetime import datetime, timedelta
from flask import render_template, request, redirect, session, jsonify, url_for
from flask_login import login_user, logout_user, login_required, current_user
from eapp import app, db, login, dao
from eapp.models import (
    AccountRole, Booking, Rental,
    Room, RoomStatus, BookingStatus, RentalStatus, Invoice, Regulation, RoomType, CustomerType
)
from eapp.utils import summarize_selected_rooms, validate_max_hold_days
from eapp.services import MoMoService
import cloudinary.uploader


@login.user_loader
def load_user(account_id):
    return dao.get_account_by_id(account_id)


# 1. Home & Room Search

@app.context_processor
def inject_common_data():
    selected_rooms = session.get('selected_rooms', {})
    return {
        'selected_summary': summarize_selected_rooms(selected_rooms)
    }


@app.route('/')
def index():
    kw = request.args.get('kw', '').strip()
    room_type_id = request.args.get('room_type_id', '')
    guests = int(request.args.get('guests', 2))
    page = int(request.args.get('page', 1))

    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    checkin_str = request.args.get('checkin', today.strftime('%Y-%m-%d'))
    checkout_str = request.args.get('checkout', tomorrow.strftime('%Y-%m-%d'))

    err_msg = None
    try:
        checkin_dt = datetime.strptime(checkin_str, '%Y-%m-%d')
        checkout_dt = datetime.strptime(checkout_str, '%Y-%m-%d')
        if checkout_dt <= checkin_dt:
            err_msg = "Ngày trả phòng phải sau ngày nhận phòng ít nhất 1 đêm!"
            checkout_dt = checkin_dt + timedelta(days=1)
            checkout_str = checkout_dt.strftime('%Y-%m-%d')

    except ValueError:
        checkin_dt = datetime.combine(today, datetime.min.time())
        checkout_dt = datetime.combine(tomorrow, datetime.min.time())
        checkin_str = today.strftime('%Y-%m-%d')
        checkout_str = tomorrow.strftime('%Y-%m-%d')

    session['search_checkin'] = checkin_str
    session['search_checkout'] = checkout_str

    rooms = dao.load_rooms(kw=kw, room_type_id=room_type_id,
                           checkin_date=checkin_dt, checkout_date=checkout_dt, page=page)

    total_rooms = dao.count_rooms(kw=kw, room_type_id=room_type_id,
                                  checkin_date=checkin_dt, checkout_date=checkout_dt)
    pages = math.ceil(total_rooms / app.config['PAGE_SIZE'])

    reg = Regulation.query.first()
    max_guests = reg.max_guests if reg else 3

    return render_template(
        'index.html',
        rooms=rooms,
        room_types=RoomType.query.all(),
        kw=kw,
        room_type_id=room_type_id,
        checkin=checkin_str,
        checkout=checkout_str,
        guests=guests,
        max_guests=max_guests,
        today_str=today.strftime('%Y-%m-%d'),
        pages=pages,
        current_page=page,
        err_msg=err_msg
    )


# 2. Authentication (Login, Register, Logout)
@app.route('/login', methods=['GET', 'POST'])
def login_view():
    err_msg = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        account = dao.auth_user(username=username, password=password)
        if account:
            login_user(account)
            next_page = request.args.get('next')
            if account.role == AccountRole.MANAGER:
                return redirect(next_page or '/admin')
            elif account.role == AccountRole.STAFF:
                return redirect(next_page or '/reception')
            return redirect(next_page or '/')
        else:
            err_msg = "Tên đăng nhập hoặc mật khẩu không chính xác!"

    return render_template('login.html', err_msg=err_msg)


@app.route('/register', methods=['GET', 'POST'])
def register_view():
    err_msg = None
    customer_types = dao.load_customer_types()
    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if password != confirm:
            err_msg = "Mật khẩu xác nhận không khớp!"
        else:
            avatar_url = None
            avatar_file = request.files.get('avatar')
            if avatar_file:
                res = cloudinary.uploader.upload(avatar_file)
                avatar_url = res.get('secure_url')

            try:
                dao.register_customer(
                    full_name=request.form.get('full_name'),
                    identity_card=request.form.get('identity_card'),
                    phone=request.form.get('phone'),
                    username=request.form.get('username'),
                    password=password,
                    email=request.form.get('email'),
                    address=request.form.get('address'),
                    avatar=avatar_url,
                    customer_type_id=int(request.form.get('customer_type_id'))
                )
                next_page = request.args.get('next')
                if next_page:
                    return redirect('/login?next=' + next_page)
                return redirect('/login')

            except Exception as ex:
                err_msg = "Lỗi đăng ký (Trùng tên đăng nhập hoặc CCCD): " + str(ex)

    return render_template('register.html', err_msg=err_msg, customer_types=customer_types)


@app.route('/logout')
def logout_view():
    logout_user()
    return redirect('/login')


# 3. Online Room Selection & Booking Flow (with MoMo Deposit)
@app.route('/api/select-room', methods=['POST'])
def add_selected_room():
    data = request.json
    room = db.session.get(Room, int(data.get('id')))

    if not room:
        return jsonify({'err_msg': 'Không tìm thấy phòng!'}), 404

    room_id = str(room.id)
    selected_rooms = session.get('selected_rooms', {})

    if room_id not in selected_rooms:
        selected_rooms[room_id] = {
            'id': room_id,
            'room_number': room.room_number,
            'room_type': room.room_type.name,
            'base_price': room.room_type.base_price
        }
    session['selected_rooms'] = selected_rooms
    return jsonify(summarize_selected_rooms(selected_rooms))


@app.route('/api/remove-room/<room_id>', methods=['DELETE'])
def remove_selected_room(room_id):
    selected_rooms = session.get('selected_rooms', {})
    if room_id in selected_rooms:
        del selected_rooms[room_id]
    session['selected_rooms'] = selected_rooms
    return jsonify(summarize_selected_rooms(selected_rooms))


@app.route('/booking-list')
def booking_list():
    selected_rooms = session.get('selected_rooms', {})
    summary = summarize_selected_rooms(selected_rooms)
    regulation = dao.get_current_regulation()

    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    default_checkin = session.get('search_checkin', today.strftime('%Y-%m-%d'))
    default_checkout = session.get('search_checkout', tomorrow.strftime('%Y-%m-%d'))

    return render_template('booking_list.html',
                           selected_rooms=selected_rooms,
                           selected_summary=summary,
                           regulation=regulation,
                           default_checkin=default_checkin,
                           default_checkout=default_checkout,
                           today_str=today.strftime('%Y-%m-%d'))


@app.route('/api/confirm-booking', methods=['POST'])
@login_required
def confirm_booking():
    selected_rooms = session.get('selected_rooms')
    if not selected_rooms:
        return jsonify({'status': 400, 'err_msg': 'Danh sách phòng trống!'})

    data = request.json
    checkin_str = data.get('expected_checkin')
    checkout_str = data.get('expected_checkout')

    try:
        expected_checkin = datetime.strptime(checkin_str, '%Y-%m-%d')
        expected_checkout = datetime.strptime(checkout_str, '%Y-%m-%d')

        reg = dao.get_current_regulation()
        now = datetime.now()

        # Kiểm tra TRƯỚC khi tạo link thanh toán MoMo (tránh khách trả cọc rồi mới báo lỗi)
        if expected_checkout.date() <= expected_checkin.date():
            return jsonify({'status': 400, 'err_msg': 'Ngày trả phòng phải sau ngày nhận phòng!'})
        if not validate_max_hold_days(now, expected_checkin, reg.max_hold_days):
            return jsonify({'status': 400, 'err_msg': 'Ngày nhận phòng phải từ hôm nay và không quá ' +
                                                      str(reg.max_hold_days) + ' ngày kể từ ngày đặt!'})

        # Phòng phải còn trống trong khoảng ngày này (không trùng phiếu đặt hoặc phiếu thuê khác)
        for r in selected_rooms.values():
            if not dao.is_room_free(int(r['id']), expected_checkin, expected_checkout):
                return jsonify({'status': 400, 'err_msg': 'Phòng ' + str(r['room_number']) +
                                                          ' đã có người đặt hoặc đang thuê trong khoảng ngày này!'})

        stay_days = max(1, (expected_checkout.date() - expected_checkin.date()).days)
        total_est = sum(r['base_price'] * stay_days for r in selected_rooms.values())
        deposit = round(total_est * reg.deposit_rate, 0)

        order_id = "BOOK_" + str(uuid.uuid4().hex[:10]).upper()

        # Lưu lại đơn đang chờ thanh toán (kèm danh sách phòng và số tiền) để đối chiếu khi MoMo trả về
        session['pending_booking'] = {
            'expected_checkin': checkin_str,
            'expected_checkout': checkout_str,
            'order_id': order_id,
            'amount': deposit,
            'selected_rooms': selected_rooms
        }
        return_url = url_for('momo_booking_return', _external=True)
        notify_url = return_url

        momo = MoMoService()
        res = momo.create_payment(
            order_id=order_id,
            amount=deposit,
            order_info="Dat coc 20% phong Aurelia Hotel & Suites",
            return_url=return_url,
            notify_url=notify_url
        )

        if res.get('resultCode') == 0:
            return jsonify({'status': 200, 'pay_url': res.get('payUrl')})
        else:
            return jsonify({'status': 400, 'err_msg': 'Lỗi MoMo: ' + str(res.get('message'))})
    except Exception as ex:
        return jsonify({'status': 400, 'err_msg': str(ex)})


@app.route('/momo-booking-return')
@login_required
def momo_booking_return():
    pending = session.get('pending_booking')

    # Chỉ tạo phiếu đặt khi: MoMo báo thành công, chữ ký đúng, và đúng đơn hàng + số tiền đã tạo lúc trước
    paid_ok = False
    if pending and request.args.get('resultCode') == '0':
        if (MoMoService().verify_signature(request.args)
                and request.args.get('orderId') == pending['order_id']
                and request.args.get('amount') == str(int(pending['amount']))):
            paid_ok = True

    if paid_ok:
        expected_checkin = datetime.strptime(pending['expected_checkin'], '%Y-%m-%d')
        expected_checkout = datetime.strptime(pending['expected_checkout'], '%Y-%m-%d')
        try:
            booking = dao.create_online_booking(
                customer_user_id=current_user.user_id,
                selected_rooms=pending['selected_rooms'],
                expected_checkin=expected_checkin,
                expected_checkout=expected_checkout
            )
        except Exception as ex:
            db.session.rollback()
            return redirect(
                '/booking-list?err=' + str(ex) + ' (Nếu đã thanh toán cọc, vui lòng liên hệ khách sạn để được hỗ trợ)')

        session['selected_rooms'] = {}
        session.pop('pending_booking', None)
        return redirect('/my-bookings?success_id=' + str(booking.id))

    return redirect('/booking-list?err=Thanh toán cọc MoMo thất bại, bị hủy hoặc không hợp lệ!')


@app.route('/my-bookings')
@login_required
def my_bookings():
    bookings = dao.get_bookings_by_customer(current_user.user_id)
    return render_template('my_bookings.html', bookings=bookings)


@app.route('/cancel-booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get(booking_id)
    if booking and booking.customer_id == current_user.user_id and booking.status == BookingStatus.PENDING_CHECKIN:
        booking.status = BookingStatus.CANCELLED
        db.session.commit()
    return redirect('/my-bookings')


# 4. Reception Operations (Check-in, Room Replacement, Room Cleaning & Checkout)
# Đọc bảng khách (họ tên, loại khách, CMND, địa chỉ) từ form, bỏ qua các dòng để trống
def get_guests_from_form():
    names = request.form.getlist('guest_name')
    types = request.form.getlist('guest_type')
    cccds = request.form.getlist('guest_cccd')
    addresses = request.form.getlist('guest_address')

    guests = []
    for i in range(len(names)):
        name = names[i].strip()
        cccd = cccds[i].strip()
        addr = addresses[i].strip()

        if not name and not cccd and not addr:
            continue
        if not name:
            raise ValueError("Dòng số " + str(i + 1) + ": Vui lòng nhập họ tên khách hàng!")
        if not name.replace(" ", "").isalpha() or len(name) < 2:
            raise ValueError("Dòng số " + str(i + 1) + ": Họ tên khách hàng chỉ được chứa chữ cái!")
        ct = CustomerType.query.get(int(types[i]))
        is_foreign = ct and ('nước ngoài' in ct.name.lower())
        if is_foreign:
            if not cccd.isalnum() or len(cccd) < 6 or len(cccd) > 12:
                raise ValueError(
                    "Dòng số " + str(i + 1) + ": Số Hộ chiếu khách nước ngoài phải từ 6 đến 12 ký tự chữ hoặc số!")
        else:
            if not cccd.isdigit() or len(cccd) != 12:
                raise ValueError("Dòng số " + str(i + 1) + ": Số CCCD khách nội địa phải gồm đúng 12 chữ số!")

        guests.append({
            'full_name': name,
            'identity_card': cccd,
            'customer_type_id': int(types[i]),
            'address': addr
        })
    return guests



@app.route('/reception')
@login_required
def reception_dashboard():
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')

    kw = request.args.get('kw')  # tìm phiếu đặt theo họ tên khách

    all_rooms = Room.query.order_by(Room.room_number).all()
    floors = sorted(list(set(r.room_number[0] for r in all_rooms if r.room_number)))
    available_rooms = Room.query.filter_by(status=RoomStatus.AVAILABLE).order_by(Room.room_number).all()
    pending_bookings = dao.load_pending_bookings(kw)
    active_rentals = Rental.query.filter_by(status=RentalStatus.ACTIVE).all()

    return render_template('reception.html',
                           rooms=all_rooms,
                           floors=floors,
                           available_rooms=available_rooms,
                           pending_bookings=pending_bookings,
                           active_rentals=active_rentals,
                           customer_types=dao.load_customer_types(),
                           booked_today=dao.get_room_ids_booked_today(),
                           kw=kw)


@app.route('/reception/checkin', methods=['POST'])
@login_required
def reception_checkin():
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')

    checkin_type = request.form.get('checkin_type')
    try:
        guests = get_guests_from_form()
        if checkin_type == 'booking':
            booking_id_str = request.form.get('booking_id')
            if not booking_id_str:
                raise ValueError("Vui lòng chọn một phiếu đặt phòng chờ nhận trước khi lập phiếu thuê!")
            booking_id = int(booking_id_str)
            room_replacements = {}
            old_room_id = request.form.get('old_room_id')
            new_room_id = request.form.get('new_room_id')
            if old_room_id and new_room_id:
                room_replacements[str(old_room_id)] = int(new_room_id)

            rental = dao.create_rental_from_booking(
                booking_id=booking_id,
                staff_user_id=current_user.user_id,
                room_replacements=room_replacements,
                guests=guests
            )
        else:
            room_ids = request.form.getlist('room_ids')
            checkout_str = request.form.get('expected_checkout')
            expected_checkout = datetime.strptime(checkout_str, '%Y-%m-%d')
            rental = dao.create_walkin_rental(
                staff_user_id=current_user.user_id,
                room_ids=room_ids,
                expected_checkout=expected_checkout,
                guests=guests
            )
        # Mở ngay phiếu thuê phòng để in cho khách ký nhận
        return redirect('/rental-slip/' + str(rental.id) + '?new=1')
    except Exception as ex:
        db.session.rollback()
        tab_name = 'walkin_checkin' if checkin_type == 'walkin' else 'booked_checkin'
        return redirect('/reception?tab=' + tab_name + '&err=' + str(ex))


# Nhân viên lập phiếu đặt phòng tại quầy
@app.route('/reception/booking', methods=['POST'])
@login_required
def reception_booking():
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')

    try:
        guests = get_guests_from_form()
        room_ids = request.form.getlist('room_ids')
        expected_checkin = datetime.strptime(request.form.get('expected_checkin'), '%Y-%m-%d')
        expected_checkout = datetime.strptime(request.form.get('expected_checkout'), '%Y-%m-%d')

        booking = dao.create_booking_at_counter(
            room_ids=room_ids,
            expected_checkin=expected_checkin,
            expected_checkout=expected_checkout,
            guests=guests
        )
        # Mở ngay phiếu đặt phòng để in cho khách
        return redirect('/booking-slip/' + str(booking.id) + '?new=1')
    except Exception as ex:
        db.session.rollback()
        return redirect('/reception?tab=counter_booking&err=' + str(ex))


@app.route('/reception/clean-room/<int:room_id>', methods=['POST'])
@login_required
def clean_room(room_id):
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')
    room = Room.query.get(room_id)
    if not room:
        return redirect('/reception?err=Không tìm thấy phòng!')
    if room.status == RoomStatus.CLEANING:
        room.status = RoomStatus.AVAILABLE
        db.session.commit()
    return redirect('/reception?msg=Phòng ' + room.room_number + ' đã dọn xong và sẵn sàng đón khách!')


# Phiếu đặt phòng: nhân viên xem được mọi phiếu, khách chỉ xem phiếu của mình
@app.route('/booking-slip/<int:booking_id>')
@login_required
def booking_slip(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    is_staff = current_user.role in [AccountRole.STAFF, AccountRole.MANAGER]
    if not is_staff and booking.customer_id != current_user.user_id:
        return redirect('/')

    return render_template('booking_slip.html',
                           booking=booking,
                           max_hold_days=dao.get_current_regulation().max_hold_days,
                           back_url='/reception' if is_staff else '/my-bookings')


# Phiếu thuê phòng: nhân viên in cho khách ký nhận
@app.route('/rental-slip/<int:rental_id>')
@login_required
def rental_slip(rental_id):
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')

    rental = Rental.query.get_or_404(rental_id)
    return render_template('rental_slip.html',
                           rental=rental,
                           max_guests=dao.get_current_regulation().max_guests)


@app.route('/reception/checkout/<int:rental_id>', methods=['POST'])
@login_required
def reception_checkout(rental_id):
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')

    payment_method = request.form.get('payment_method', 'Tiền mặt')
    action_type = request.form.get('action_type', 'checkout')
    is_prepaid = (action_type == 'prepay')

    rental = Rental.query.get(rental_id)
    if not rental:
        return redirect('/reception?err=Không tìm thấy phiếu thuê phòng!')

    if rental.invoice and not is_prepaid:
        dao.checkout_and_create_invoice(
            rental_id=rental_id,
            staff_user_id=current_user.user_id,
            is_prepaid=False
        )
        return redirect('/reception?msg=Đã hoàn tất trả phòng #' + str(rental_id) + '!')

    if payment_method == 'Chuyển khoản bằng MoMo':
        # Tính tiền bằng đúng hàm của hóa đơn (có phụ thu khách và hệ số loại khách)
        total_room_amount, lines = dao.calculate_rental_bill(rental, is_prepaid)
        final_amt = max(1000, round(total_room_amount - rental.deposit_deducted, 0))

        order_id = "INV_" + str(rental_id) + "_" + str(uuid.uuid4().hex[:6]).upper()
        return_url = url_for('momo_checkout_return', rental_id=rental_id, prepay='1' if is_prepaid else '0',
                             _external=True)

        momo = MoMoService()
        res = momo.create_payment(
            order_id=order_id,
            amount=final_amt,
            order_info="Thanh toan phong #" + str(rental_id) + " - Aurelia Hotel & Suites",
            return_url=return_url,
            notify_url=return_url
        )
        if res.get('resultCode') == 0:
            return redirect(res.get('payUrl'))
        else:
            return redirect('/reception?err=Lỗi tạo QR MoMo: ' + str(res.get('message')))

    try:
        invoice = dao.checkout_and_create_invoice(
            rental_id=rental_id,
            staff_user_id=current_user.user_id,
            payment_method=payment_method,
            is_prepaid=is_prepaid
        )
        return render_template('invoice.html', invoice=invoice, copy_type='customer')
    except Exception as ex:
        return redirect('/reception?err=' + str(ex))


@app.route('/invoice/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')
    invoice = Invoice.query.get_or_404(invoice_id)
    copy_type = request.args.get('copy', 'customer')
    if copy_type == 'manager' and current_user.role != AccountRole.MANAGER:
        copy_type = 'customer'
    return render_template('invoice.html', invoice=invoice, copy_type=copy_type)


@app.route('/momo-checkout-return/<int:rental_id>')
@login_required
def momo_checkout_return(rental_id):
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')
    is_prepaid = (request.args.get('prepay') == '1')
    rental = Rental.query.get(rental_id)

    # Chỉ lập hóa đơn khi: MoMo báo thành công, chữ ký đúng, đúng phiếu thuê và đúng số tiền cần thanh toán
    paid_ok = False
    if rental and request.args.get('resultCode') == '0':
        total_room_amount, lines = dao.calculate_rental_bill(rental, is_prepaid)
        expected_amount = max(1000, round(total_room_amount - rental.deposit_deducted, 0))
        if (MoMoService().verify_signature(request.args)
                and request.args.get('orderId', '').startswith('INV_' + str(rental_id) + '_')
                and request.args.get('amount') == str(int(expected_amount))):
            paid_ok = True

    if paid_ok:
        try:
            invoice = dao.checkout_and_create_invoice(
                rental_id=rental_id,
                staff_user_id=current_user.user_id,
                payment_method="Chuyển khoản bằng MoMo",
                is_prepaid=is_prepaid
            )
            return render_template('invoice.html', invoice=invoice, copy_type='customer')
        except Exception as ex:
            db.session.rollback()
            return redirect('/reception?err=' + str(ex))
    return redirect('/reception?err=Giao dịch thanh toán MoMo không thành công hoặc không hợp lệ!')


if __name__ == '__main__':
    from eapp import admin

    app.run(debug=True)
