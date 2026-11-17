from flask_login import UserMixin
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Enum, Date, DateTime
from sqlalchemy.orm import relationship
from eapp import db, app
from enum import Enum as PyEnum
from datetime import datetime, date
import hashlib

class BaseModel(db.Model):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True)


# Nhóm Enum:
class VaiTroTaiKhoan(PyEnum):
    KHACH_HANG = 1
    NHAN_VIEN = 2
    QUAN_LY = 3

class TrangThaiPhong(PyEnum):
    TRONG = "TRONG"
    DA_DAT = "DA_DAT"
    DANG_SU_DUNG = "DANG_SU_DUNG"
    DANG_DON_DEP = "DANG_DON_DEP"

class TrangThaiPhieuDat(PyEnum):
    CHO_NHAN_PHONG = "CHO_NHAN_PHONG"
    DA_NHAN_PHONG = "DA_NHAN_PHONG"
    QUA_HAN_HUY_PHONG = "QUA_HAN_HUY_PHONG"
    DA_HUY = "DA_HUY"

class TrangThaiPhieuThue(PyEnum):
    DANG_THUE = "DANG_THUE"
    DA_THANH_TOAN = "DA_THANH_TOAN"

class LoaiKhach(PyEnum):
    NOI_DIA = "NOI_DIA"
    NUOC_NGOAI = "NUOC_NGOAI"


#Nhóm User:
class User(BaseModel, UserMixin):
    __tablename__ = 'user'
    ho_ten = Column(String(100), nullable=False)
    cmnd = Column(String(20), unique=True, nullable=False)
    so_dien_thoai = Column(String(15), nullable=False)
    email = Column(String(100), nullable=True)
    dia_chi = Column(String(255), nullable=True)
    avatar = Column(String(255), default='https://cloudinary.com')

    tai_khoan = relationship('TaiKhoan', backref='user', uselist=False, lazy=True)
    khach_hang = relationship('KhachHang', backref='user', uselist=False, lazy=True)
    nhan_vien = relationship('NhanVien', backref='user', uselist=False, lazy=True)
    quan_ly = relationship('QuanLy', backref='user', uselist=False, lazy=True)

    def __str__(self):
        return self.ho_ten

