import uuid
import math
from datetime import datetime
from flask import render_template, request, redirect, session, jsonify, url_for
from flask_login import login_user, logout_user, login_required, current_user
from eapp import app, db, login, dao
from eapp.models import (
    AccountRole, CustomerType, Booking, Rental, Customer,
    Room, RoomStatus, BookingStatus, RentalStatus, Invoice
)
from eapp.utils import summarize_selected_rooms
from eapp.services import MoMoService
import cloudinary.uploader


@login.user_loader
def load_user(account_id):
    return dao.get_account_by_id(account_id)


# 1. Home & Room Search
@app.route('/')
def index():
    room_type_id = request.args.get('room_type_id')
    status = request.args.get('status')
    kw = request.args.get('kw')
    page = int(request.args.get('page', 1))

    room_types = dao.load_room_types()
    rooms = dao.load_rooms(room_type_id=room_type_id, status=status, kw=kw, page=page)
    total = dao.count_rooms(room_type_id=room_type_id, status=status, kw=kw)

    return render_template('index.html',
                           room_types=room_types,
                           rooms=rooms,
                           pages=math.ceil(total / app.config['PAGE_SIZE']),
                           current_page=page)


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

            c_type = CustomerType.FOREIGN if request.form.get('customer_type') == 'FOREIGN' else CustomerType.DOMESTIC

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
                    customer_type=c_type
                )
                return redirect('/login')
            except Exception as ex:
                err_msg = "Lỗi đăng ký (Trùng tên đăng nhập hoặc CCCD): " + str(ex)

    return render_template('register.html', err_msg=err_msg)


@app.route('/logout')
def logout_view():
    logout_user()
    return redirect('/login')


# 3. Online Room Selection & Booking Flow (with MoMo Deposit)
@app.route('/api/select-room', methods=['POST'])
def add_selected_room():
    data = request.json
    room_id = str(data.get('id'))
    selected_rooms = session.get('selected_rooms', {})

    if room_id not in selected_rooms:
        selected_rooms[room_id] = {
            'id': room_id,
            'room_number': data.get('room_number'),
            'room_type': data.get('room_type'),
            'base_price': float(data.get('base_price'))
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
    return render_template('booking_list.html',
                           selected_rooms=selected_rooms,
                           summary=summary)


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
        stay_days = max(1, (expected_checkout.date() - expected_checkin.date()).days)
        total_est = sum(r['base_price'] * stay_days for r in selected_rooms.values())
        deposit = round(total_est * reg.deposit_rate, 0)

        session['pending_booking'] = {
            'expected_checkin': checkin_str,
            'expected_checkout': checkout_str
        }

        order_id = "BOOK_" + str(uuid.uuid4().hex[:10]).upper()
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
    result_code = request.args.get('resultCode')
    pending = session.get('pending_booking')
    selected_rooms = session.get('selected_rooms')

    if result_code == '0' and pending and selected_rooms:
        expected_checkin = datetime.strptime(pending['expected_checkin'], '%Y-%m-%d')
        expected_checkout = datetime.strptime(pending['expected_checkout'], '%Y-%m-%d')

        booking = dao.create_online_booking(
            customer_user_id=current_user.user_id,
            selected_rooms=selected_rooms,
            expected_checkin=expected_checkin,
            expected_checkout=expected_checkout
        )
        session['selected_rooms'] = {}
        session.pop('pending_booking', None)
        return redirect('/my-bookings?success_id=' + str(booking.id))

    return redirect('/booking-list?err=Thanh toán cọc MoMo thất bại hoặc đã bị hủy!')


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
        for d in booking.details:
            if d.room.status == RoomStatus.BOOKED:
                d.room.status = RoomStatus.AVAILABLE
        db.session.commit()
    return redirect('/my-bookings')


# 4. Reception Operations (Check-in, Room Replacement, Room Cleaning & Checkout)
@app.route('/reception')
@login_required
def reception_dashboard():
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')

    all_rooms = Room.query.order_by(Room.room_number).all()
    floors = sorted(list(set(r.room_number[0] for r in all_rooms if r.room_number)))
    available_rooms = Room.query.filter_by(status=RoomStatus.AVAILABLE).order_by(Room.room_number).all()
    pending_bookings = Booking.query.filter_by(status=BookingStatus.PENDING_CHECKIN).all()
    active_rentals = Rental.query.filter_by(status=RentalStatus.ACTIVE).all()
    customers = Customer.query.all()

    return render_template('reception.html',
                           rooms=all_rooms,
                           floors=floors,
                           available_rooms=available_rooms,
                           pending_bookings=pending_bookings,
                           active_rentals=active_rentals,
                           customers=customers)


@app.route('/reception/checkin', methods=['POST'])
@login_required
def reception_checkin():
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')

    checkin_type = request.form.get('checkin_type')
    try:
        if checkin_type == 'booking':
            booking_id = int(request.form.get('booking_id'))
            room_replacements = {}
            old_room_id = request.form.get('old_room_id')
            new_room_id = request.form.get('new_room_id')
            if old_room_id and new_room_id:
                room_replacements[str(old_room_id)] = int(new_room_id)

            dao.create_rental_from_booking(
                booking_id=booking_id,
                staff_user_id=current_user.user_id,
                room_replacements=room_replacements
            )
        else:
            room_ids = request.form.getlist('room_ids')
            customer_ids = request.form.getlist('customer_ids')
            checkout_str = request.form.get('expected_checkout')
            expected_checkout = datetime.strptime(checkout_str, '%Y-%m-%d')
            dao.create_walkin_rental(
                staff_user_id=current_user.user_id,
                room_ids=room_ids,
                expected_checkout=expected_checkout,
                customer_ids=customer_ids
            )
        return redirect('/reception?msg=Lập phiếu thuê phòng thành công!')
    except Exception as ex:
        return redirect('/reception?err=' + str(ex))


@app.route('/reception/clean-room/<int:room_id>', methods=['POST'])
@login_required
def clean_room(room_id):
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')
    room = Room.query.get(room_id)
    if room and room.status == RoomStatus.CLEANING:
        room.status = RoomStatus.AVAILABLE
        db.session.commit()
    return redirect('/reception?msg=Phòng ' + room.room_number + ' đã dọn xong và sẵn sàng đón khách!')


@app.route('/reception/checkout/<int:rental_id>', methods=['POST'])
@login_required
def reception_checkout(rental_id):
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')

    payment_method = request.form.get('payment_method', 'Tiền mặt')

    if payment_method == 'Chuyển khoản bằng MoMo':
        rental = Rental.query.get(rental_id)
        now = datetime.now()
        stay_days = max(1, (now.date() - rental.checkin_date.date()).days)

        total_est = sum(rd.room.room_type.base_price * stay_days for rd in rental.rental_details)
        final_amt = max(1000, round(total_est - rental.deposit_deducted, 0))

        order_id = "INV_" + str(rental_id) + "_" + str(uuid.uuid4().hex[:6]).upper()
        return_url = url_for('momo_checkout_return', rental_id=rental_id, _external=True)

        momo = MoMoService()
        res = momo.create_payment(
            order_id=order_id,
            amount=final_amt,
            order_info="Thanh toan tra phong #" + str(rental_id) + " - Aurelia Hotel & Suites",
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
            payment_method=payment_method
        )
        return render_template('invoice.html', invoice=invoice, copy_type='customer')
    except Exception as ex:
        return redirect('/reception?err=' + str(ex))


@app.route('/momo-checkout-return/<int:rental_id>')
@login_required
def momo_checkout_return(rental_id):
    result_code = request.args.get('resultCode')
    if result_code == '0':
        invoice = dao.checkout_and_create_invoice(
            rental_id=rental_id,
            staff_user_id=current_user.user_id,
            payment_method="Chuyển khoản bằng MoMo"
        )
        return render_template('invoice.html', invoice=invoice, copy_type='customer')
    return redirect('/reception?err=Giao dịch thanh toán MoMo không thành công!')


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


if __name__ == '__main__':
    from eapp import admin
    app.run(debug=True)
