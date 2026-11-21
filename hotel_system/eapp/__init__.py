from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
import cloudinary

app = Flask(__name__)
app.secret_key = '&*(^UIGKJHJKHG&TFUTFYHGIUG&T*TUITGUIG&F'
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:root1234@localhost/hoteldb?charset=utf8mb4"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
app.config['PAGE_SIZE'] = 8

# Gmail SMTP Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'thuuyen23003@gmail.com'
app.config['MAIL_PASSWORD'] = 'pqifykrsvtmwuyga'
app.config['MAIL_DEFAULT_SENDER'] = ('Hotel Management', 'thuuyen23003@gmail.com')

# Telegram Bot Configuration
app.config['TELEGRAM_BOT_TOKEN'] = '9262396677:AAEheB1LIMkdFs_dnCBo9ZTTWmCWUo6przw'
app.config['TELEGRAM_CHAT_ID'] = '9242656093'

db = SQLAlchemy(app=app)
login = LoginManager(app=app)
mail = Mail(app=app)

# Cloudinary Configuration
cloudinary.config(cloud_name='isbvimga', api_key='513263947619764', api_secret='T34iggHkQ6h1vHwb0J3zVL4hQbc')
