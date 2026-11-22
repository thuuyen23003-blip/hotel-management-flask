import math
from datetime import datetime
from flask import render_template, request, redirect, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from eapp import app, dao, login, utils
from eapp.models import AccountRole, CustomerType, Booking, Rental

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
    return render_template('cart.html', regulation=reg)

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




