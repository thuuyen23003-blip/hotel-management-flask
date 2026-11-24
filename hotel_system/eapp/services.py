import os
import uuid
import threading
import hmac
import hashlib
import requests
from datetime import datetime
from flask import render_template
from flask_mail import Message
from eapp import app, mail, dao
from email.mime.application import MIMEApplication
from datetime import datetime
from eapp.models import Regulation

class NotificationService:
    def send_email_confirmation(self, to_email, booking, customer_name="Quý khách"):
        if not to_email:
            return False

        try:
            subject = "[Aurelia Hotel & Suites] Xác nhận đặt phòng #" + str(booking.id)
            checkin = booking.expected_checkin.strftime('%d/%m/%Y')
            checkout = booking.expected_checkout.strftime('%d/%m/%Y')
            total = "{:,.0f}".format(booking.total_estimated)
            deposit = "{:,.0f}".format(booking.deposit_amount)

            body = "Xin chào " + str(customer_name) + ",\n\n"
            body += "Đơn đặt phòng #" + str(booking.id) + " của bạn tại Aurelia Hotel & Suites đã được xác nhận.\n"
            body += "- Ngày nhận phòng: " + checkin + "\n"
            body += "- Ngày trả phòng: " + checkout + "\n"
            body += "- Tổng tiền dự kiến: " + total + " VNĐ\n"
            body += "- Tiền cọc (20%): " + deposit + " VNĐ\n"

            reg = dao.get_current_regulation()
            created_str = datetime.now().strftime('%d/%m/%Y %H:%M')
            html = render_template('email/booking_slip.html',
                                   booking=booking,
                                   max_hold_days=reg.max_hold_days,
                                   created_str=created_str)

            msg = Message(subject=subject, recipients=[to_email], body=body, html=html)
            mail.send(msg)
            return True
        except Exception as ex:
            print("Lỗi gửi email đặt phòng:", ex)
            return False

    # Send electronic invoice email to customer after checkout
    def send_invoice_email(self, to_email, invoice, customer_name="Quý khách"):
        if not to_email:
            return False

        try:
            subject = "[Aurelia Hotel & Suites] Hóa đơn thanh toán #" + str(invoice.id)
            pay_time = invoice.payment_date.strftime('%d/%m/%Y %H:%M')
            checkin_time = invoice.rental.checkin_date.strftime('%d/%m/%Y %H:%M')
            total_room = "{:,.0f}".format(invoice.total_room_amount)
            deposit = "{:,.0f}".format(invoice.deposit_deducted)
            final_amt = "{:,.0f}".format(invoice.final_amount)

            body = "Xin chào " + str(customer_name) + ",\n\n"
            body += "Cảm ơn bạn đã lưu trú tại Aurelia Hotel & Suites. Dưới đây là chi tiết hóa đơn thanh toán của bạn:\n"
            body += "- Mã hóa đơn: #" + str(invoice.id) + "\n"
            body += "- Thời gian nhận phòng thực tế: " + checkin_time + "\n"
            body += "- Thời gian thanh toán trả phòng: " + pay_time + "\n"
            body += "- Tổng tiền phòng: " + total_room + " VNĐ\n"
            body += "- Tiền cọc đã khấu trừ: -" + deposit + " VNĐ\n"
            body += "- Tổng tiền đã thanh toán: " + final_amt + " VNĐ (" + str(invoice.payment_method) + ")\n\n"
            body += "Hẹn gặp lại quý khách trong những kỳ nghỉ tiếp theo tại Aurelia Hotel & Suites!"

            msg = Message(subject=subject, recipients=[to_email], body=body)
            mail.send(msg)
            return True
        except Exception as ex:
            print("Lỗi gửi email hóa đơn:", ex)
            return False

    # Send concise check-in summary message to customer
    def send_customer_checkin_summary(self, booking, room_numbers, customer_name="Quý khách"):
        checkin_str = booking.expected_checkin.strftime('%d/%m/%Y')
        checkout_str = booking.expected_checkout.strftime('%d/%m/%Y')
        deposit_str = "{:,.0f}".format(booking.deposit_amount)

        summary_msg = (
                "CÁM ƠN QUÝ KHÁCH ĐÃ ĐẾN VỚI HỆ THỐNG KHÁCH SẠN AURELIA HOTEL & SUITES\n" +
                "- Khách hàng: " + str(customer_name) + "\n" +
                "- Mã phiếu đặt: #" + str(booking.id) + "\n" +
                "- Phòng đã đặt: " + str(room_numbers) + "\n" +
                "- Nhận - Trả dự kiến: " + checkin_str + " - " + checkout_str + "\n" +
                "- Tiền cọc (20%): " + deposit_str + " VNĐ\n" +
                "Vui lòng mang theo CCCD khi đến nhận phòng."
        )
        return self.send_telegram_notification(summary_msg)

    # Send instant alert to manager via Telegram Bot
    def send_telegram_notification(self, message):
        token = app.config.get('TELEGRAM_BOT_TOKEN')
        chat_id = app.config.get('TELEGRAM_CHAT_ID')

        if not token or not chat_id:
            return False

        # Gửi ở luồng riêng để trang web không bị đứng chờ khi mạng tới Telegram chậm hoặc bị chặn
        thread = threading.Thread(target=self.post_telegram, args=(token, chat_id, message))
        thread.daemon = True
        thread.start()
        return True

    def post_telegram(self, token, chat_id, message):
        url = "https://api." + "telegram.org/bot" + str(token) + "/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": "[Aurelia Hotel & Suites] " + str(message)
        }

        # Nếu mạng chặn Telegram thì khai báo proxy trong file .env: TELEGRAM_PROXY=http://127.0.0.1:7890
        proxy = os.getenv('TELEGRAM_PROXY')
        proxies = {'https': proxy, 'http': proxy} if proxy else None

        try:
            res = requests.post(url, json=data, timeout=15, proxies=proxies)
            if res.status_code != 200:
                print("Telegram báo lỗi:", res.status_code, res.text)
        except Exception as ex:
            print("Lỗi gửi Telegram:", ex)


class MoMoService:
    def __init__(self):
        self.partner_code = os.getenv('MOMO_PARTNER_CODE', 'MOMO')
        self.access_key = os.getenv('MOMO_ACCESS_KEY', 'F8BBA842ECF85')
        self.secret_key = os.getenv('MOMO_SECRET_KEY', 'K951B6PE1waDMi640xX08PD3vg6EkVlz')
        self.endpoint = os.getenv('MOMO_ENDPOINT', 'https://test-payment.' + 'momo.vn/v2/gateway/api/create')

    # Ký bằng HMAC-SHA256 với secret key
    def sign(self, raw_text):
        return hmac.new(
            self.secret_key.encode('utf-8'),
            raw_text.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    # Chữ ký riêng cho URL giả lập (khi MoMo sandbox không phản hồi), để không ai tự gõ URL thành công được
    def sign_fallback(self, order_id, amount_str):
        return self.sign("fallback&orderId=" + order_id + "&amount=" + amount_str)

    # Kiểm tra chữ ký trên URL kết quả thanh toán (chống tự gõ URL resultCode=0 để làm giả thanh toán)
    def verify_signature(self, args):
        # Trường hợp URL giả lập: không có signature của MoMo, chỉ có fallbackSig do server mình ký
        if 'signature' not in args and 'fallbackSig' in args:
            expected = self.sign_fallback(args.get('orderId', ''), args.get('amount', ''))
            return expected == args.get('fallbackSig')

        # Trường hợp MoMo thật: các tham số xếp theo thứ tự A-Z rồi ký
        keys = ['amount', 'extraData', 'message', 'orderId', 'orderInfo', 'orderType',
                'partnerCode', 'payType', 'requestId', 'responseTime', 'resultCode', 'transId']
        raw_signature = "accessKey=" + self.access_key
        for k in keys:
            raw_signature += "&" + k + "=" + args.get(k, '')

        if self.sign(raw_signature) != args.get('signature', ''):
            print("Chữ ký MoMo không khớp. Chuỗi đã ký:", raw_signature)
            return False
        return True

    def create_payment(self, order_id, amount, order_info, return_url, notify_url):
        request_id = str(uuid.uuid4())
        amount_str = str(int(round(amount)))
        request_type = "captureWallet"
        extra_data = ""

        raw_signature = (
                "accessKey=" + self.access_key +
                "&amount=" + amount_str +
                "&extraData=" + extra_data +
                "&ipnUrl=" + notify_url +
                "&orderId=" + order_id +
                "&orderInfo=" + order_info +
                "&partnerCode=" + self.partner_code +
                "&redirectUrl=" + return_url +
                "&requestId=" + request_id +
                "&requestType=" + request_type
        )

        signature = self.sign(raw_signature)

        payload = {
            'partnerCode': self.partner_code,
            'partnerName': "Aurelia Hotel & Suites",
            'storeId': "AureliaHotelStore",
            'requestId': request_id,
            'amount': amount_str,
            'orderId': order_id,
            'orderInfo': order_info,
            'redirectUrl': return_url,
            'ipnUrl': notify_url,
            'lang': 'vi',
            'extraData': extra_data,
            'requestType': request_type,
            'signature': signature
        }

        try:
            res = requests.post(self.endpoint, json=payload, timeout=10)
            if res.status_code == 200 and res.text.strip().startswith('{'):
                return res.json()
        except Exception as ex:
            print("MoMo Sandbox Fallback:", ex)

        # Chế độ thử nghiệm: MoMo không phản hồi thì giả lập thanh toán thành công
        sep = '&' if '?' in return_url else '?'
        fallback_url = (return_url + sep + "resultCode=0&orderId=" + order_id + "&amount=" + amount_str +
                        "&fallbackSig=" + self.sign_fallback(order_id, amount_str))
        return {'resultCode': 0, 'payUrl': fallback_url, 'message': 'Successful (Sandbox)'}
