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
