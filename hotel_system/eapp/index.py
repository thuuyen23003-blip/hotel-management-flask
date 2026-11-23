import math
from datetime import datetime
from flask import render_template, request, redirect, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from eapp import app, dao, login, utils
from eapp.models import AccountRole, CustomerType, Booking, Rental, Customer
from eapp.utils import MoMoService

# update index room listing and authentication routes
@app.route('/')
def index():
    dao.auto_cancel_expired_bookings()
    kw = request.args.get('kw')
    room_type_id = request.args.get('room_type_id')
    status = request.args.get('status')
    page = int(request.args.get('page', 1))

    rooms = dao.load_rooms(kw=kw, room_type_id=room_type_id, status=status, page=page)
    total = dao.count_rooms(kw=kw, room_type_id=room_type_id, status=status)
    page_size = app.config['PAGE_SIZE']

    return render_template('index.html',
                           rooms=rooms,
                           pages=math.ceil(total / page_size))

@app.route('/login')
def login_view():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_process():
    username = request.form.get('username')
    password = request.form.get('password')

    acc = dao.authenticate(username=username, password=password)
    if acc:
        login_user(user=acc)
        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        if acc.role == AccountRole.MANAGER:
            return redirect('/admin')
        if acc.role == AccountRole.STAFF:
            return redirect('/reception')
        return redirect('/')

    return render_template('login.html', err_msg='Tên đăng nhập hoặc mật khẩu không đúng!')

@app.route('/logout')
def logout_process():
    logout_user()
    return redirect('/login')

# update customer registration route
@app.route('/register')
def register_view():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register_process():
    password = request.form.get('password')
    confirm = request.form.get('confirm')

    if not password or not confirm or password != confirm:
        return render_template('register.html', err_msg='Mật khẩu xác nhận không khớp!')

    try:
        c_type = CustomerType.FOREIGN if request.form.get('customer_type') == 'FOREIGN' else CustomerType.DOMESTIC
        dao.register_customer(
            full_name=request.form.get('full_name'),
            identity_card=request.form.get('identity_card'),
            phone=request.form.get('phone'),
            username=request.form.get('username'),
            password=password,
            email=request.form.get('email'),
            address=request.form.get('address'),
            customer_type=c_type,
            avatar=request.files.get('avatar')
        )
        return redirect('/login')
    except Exception as ex:
        return render_template('register.html', err_msg='Lỗi đăng ký: ' + str(ex))

# add online booking cart and confirmation routes
@app.route('/booking-cart')
def booking_cart():
    reg = dao.get_current_regulation()
    return render_template('booking_list.html', regulation=reg)

@app.route('/api/selected-rooms', methods=['POST'])
def add_selected_room():
    selected = session.get('selected_rooms', {})
    room_id = str(request.json.get('id'))

    if room_id not in selected:
        selected[room_id] = {
            "id": room_id,
            "room_number": request.json.get('room_number'),
            "room_type": request.json.get('room_type'),
            "base_price": float(request.json.get('base_price'))
        }

    session['selected_rooms'] = selected
    return jsonify(utils.summarize_selected_rooms(selected))

@app.route('/api/selected-rooms/<room_id>', methods=['DELETE'])
def remove_selected_room(room_id):
    selected = session.get('selected_rooms', {})
    if room_id in selected:
        del selected[room_id]

    session['selected_rooms'] = selected
    return jsonify(utils.summarize_selected_rooms(selected))

@app.route('/api/confirm-booking', methods=['POST'])
@login_required
def confirm_booking():
    selected = session.get('selected_rooms')
    if not selected:
        return jsonify({'status': 400, 'err_msg': 'Chưa chọn phòng nào để đặt!'})

    try:
        checkin_str = request.json.get('expected_checkin')
        checkout_str = request.json.get('expected_checkout')
        expected_checkin = datetime.strptime(checkin_str, '%Y-%m-%d')
        expected_checkout = datetime.strptime(checkout_str, '%Y-%m-%d')

        booking = dao.create_online_booking(
            customer_user_id=current_user.user_id,
            selected_rooms=selected,
            expected_checkin=expected_checkin,
            expected_checkout=expected_checkout
        )
        del session['selected_rooms']
        return jsonify({'status': 200, 'booking_id': booking.id})
    except Exception as ex:
        return jsonify({'status': 400, 'err_msg': str(ex)})

@app.route('/my-bookings')
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(customer_id=current_user.user_id).order_by(Booking.id.desc()).all()
    return render_template('my_bookings.html', bookings=bookings)

# add receptionist checkin checkout routes and context processor
@app.route('/reception')
@login_required
def reception_dashboard():
    if current_user.role not in [AccountRole.STAFF, AccountRole.MANAGER]:
        return redirect('/')
    all_rooms = dao.load_rooms(page=1)
    pending_bookings = Booking.query.filter_by(status='PENDING_CHECKIN').all()
    active_rentals = Rental.query.filter_by(status='ACTIVE').all()
    customers = Customer.query.all()
    return render_template('reception.html',
                           rooms=all_rooms,
                           pending_bookings=pending_bookings,
                           active_rentals=active_rentals,
                           customers=customers)

@app.route('/reception/checkin', methods=['POST'])
@login_required
def reception_checkin():
    try:
        room_ids = request.form.getlist('room_ids')
        checkout_str = request.form.get('expected_checkout')
        expected_checkout = datetime.strptime(checkout_str, '%Y-%m-%d')
        guest_ids = request.form.getlist('guest_ids')
        booking_id = request.form.get('booking_id') or None

        dao.create_rental_checkin(
            staff_user_id=current_user.user_id,
            room_ids=room_ids,
            expected_checkout=expected_checkout,
            guest_customer_ids=guest_ids,
            booking_id=booking_id
        )
        return redirect('/reception')
    except Exception as ex:
        return "Lỗi lập phiếu thuê: " + str(ex), 400

# update checkout and add momo checkout return
@app.route('/reception/checkout/<int:rental_id>', methods=['POST'])
@login_required
def reception_checkout(rental_id):
    payment_method = request.form.get('payment_method', 'Tiền mặt')
    if payment_method == 'Chuyển khoản bằng MoMo':
        rental = Rental.query.get(rental_id)
        reg = dao.get_current_regulation()
        now = datetime.now()
        guest_count = len(rental.stay_details)
        has_foreign = any(s.customer.customer_type == CustomerType.FOREIGN for s in rental.stay_details)

        total_room = 0
        for rd in rental.rental_details:
            stay_days = max(1, (now.date() - rental.checkin_date.date()).days)
            calc = utils.calculate_room_checkout(rd.room.room_type.base_price, stay_days, guest_count, has_foreign, reg)
            total_room += calc['room_total']

        final_amount = max(0, total_room - rental.deposit_deducted)
        if final_amount > 0:
            momo = MoMoService()
            redirect_url = request.host_url + 'momo-checkout-return?rental_id=' + str(rental_id)
            res = momo.create_payment_url(
                amount=final_amount,
                order_info='Thanh toan tra phong #' + str(rental_id),
                redirect_url=redirect_url,
                ipn_url=redirect_url
            )
            if res.get('resultCode') == 0:
                return redirect(res.get('payUrl'))

    invoice = dao.checkout_and_create_invoice(
        rental_id=rental_id,
        staff_user_id=current_user.user_id,
        payment_method=payment_method
    )
    return render_template('invoice.html', invoice=invoice)

@app.route('/momo-checkout-return')
@login_required
def momo_checkout_return():
    if request.args.get('resultCode') == '0':
        rental_id = int(request.args.get('rental_id'))
        invoice = dao.checkout_and_create_invoice(
            rental_id=rental_id,
            staff_user_id=current_user.user_id,
            payment_method='Chuyển khoản bằng MoMo'
        )
        return render_template('invoice.html', invoice=invoice)
    return redirect('/reception')

@app.context_processor
def common_responses():
    return {
        'room_types': dao.load_room_types(),
        'selected_summary': utils.summarize_selected_rooms(session.get('selected_rooms'))
    }

@login.user_loader
def get_user(account_id):
    return dao.get_account_by_id(account_id)

# add momo deposit payment and callback routes
@app.route('/api/confirm-booking', methods=['POST'])
@login_required
def confirm_booking():
    selected = session.get('selected_rooms')
    if not selected:
        return jsonify({'status': 400, 'err_msg': 'Chưa chọn phòng nào để đặt!'})

    try:
        checkin_str = request.json.get('expected_checkin')
        checkout_str = request.json.get('expected_checkout')
        expected_checkin = datetime.strptime(checkin_str, '%Y-%m-%d')
        expected_checkout = datetime.strptime(checkout_str, '%Y-%m-%d')

        reg = dao.get_current_regulation()
        now = datetime.now()
        if not utils.validate_max_hold_days(now, expected_checkin, reg.max_hold_days):
            return jsonify({'status': 400, 'err_msg': 'Ngày nhận phòng vượt quá ' + str(reg.max_hold_days) + ' ngày!'})

        stay_days = max(1, (expected_checkout.date() - expected_checkin.date()).days)
        total_estimated = sum(r['base_price'] * stay_days for r in selected.values())
        deposit_amount = utils.calculate_deposit(total_estimated, reg.deposit_rate)

        # Save pending dates in session while waiting for MoMo QR payment
        session['pending_booking_dates'] = {
            'checkin': checkin_str,
            'checkout': checkout_str
        }

        momo = MoMoService()
        redirect_url = request.host_url + 'momo-booking-return'
        res = momo.create_payment_url(
            amount=deposit_amount,
            order_info='Dat coc dat phong Aurelia Hotel',
            redirect_url=redirect_url,
            ipn_url=redirect_url
        )

        if res.get('resultCode') == 0:
            return jsonify({'status': 200, 'pay_url': res.get('payUrl')})
        return jsonify({'status': 400, 'err_msg': 'Không tạo được giao dịch MoMo: ' + str(res.get('message'))})
    except Exception as ex:
        return jsonify({'status': 400, 'err_msg': str(ex)})

@app.route('/momo-booking-return')
@login_required
def momo_booking_return():
    result_code = request.args.get('resultCode')
    if result_code == '0':
        selected = session.get('selected_rooms')
        dates = session.get('pending_booking_dates')
        if selected and dates:
            expected_checkin = datetime.strptime(dates['checkin'], '%Y-%m-%d')
            expected_checkout = datetime.strptime(dates['checkout'], '%Y-%m-%d')
            dao.create_online_booking(
                customer_user_id=current_user.user_id,
                selected_rooms=selected,
                expected_checkin=expected_checkin,
                expected_checkout=expected_checkout
            )
            session.pop('selected_rooms', None)
            session.pop('pending_booking_dates', None)
        return redirect('/my-bookings')
    return redirect('/booking-cart')

if __name__ == '__main__':
    with app.app_context():
        from eapp import admin
        app.run(debug=True)
