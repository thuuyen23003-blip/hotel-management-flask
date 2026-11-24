import os
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
import cloudinary

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE_URI')
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['PAGE_SIZE'] = 8

# Gmail SMTP Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = ('Aurelia Hotel & Suites', os.environ.get('MAIL_USERNAME'))

# Telegram Bot Configuration
app.config['TELEGRAM_BOT_TOKEN'] = os.environ.get('TELEGRAM_BOT_TOKEN')
app.config['TELEGRAM_CHAT_ID'] = os.environ.get('TELEGRAM_CHAT_ID')

# MoMo Sandbox Configuration
app.config['MOMO_PARTNER_CODE'] = os.environ.get('MOMO_PARTNER_CODE')
app.config['MOMO_ACCESS_KEY'] = os.environ.get('MOMO_ACCESS_KEY')
app.config['MOMO_SECRET_KEY'] = os.environ.get('MOMO_SECRET_KEY')
app.config['MOMO_ENDPOINT'] = os.environ.get('MOMO_ENDPOINT', 'https://test-payment.' + 'momo.vn/v2/gateway/api/create')

db = SQLAlchemy(app=app)
login = LoginManager(app=app)
login.login_view = 'login_view'
mail = Mail(app=app)

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)
