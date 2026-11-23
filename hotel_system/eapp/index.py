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




