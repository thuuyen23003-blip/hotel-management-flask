import requests
from flask_mail import Message
from eapp import app, mail
import json
import hmac
import hashlib
import uuid

# add selected rooms summary and deposit calculation
def summarize_selected_rooms(selected_rooms):
    total_rooms, total_amount_per_night = 0, 0

    if selected_rooms:
        for room in selected_rooms.values():
            total_rooms += 1
            total_amount_per_night += room['base_price']

    return {
        'total_rooms': total_rooms,
        'total_amount_per_night': total_amount_per_night
    }

def calculate_deposit(total_amount, deposit_rate):
    return round(total_amount * deposit_rate, 0)

# add 28-day maximum booking hold rule validation
def validate_max_hold_days(booking_date, expected_checkin, max_hold_days):
    d1 = booking_date.date() if hasattr(booking_date, 'date') else booking_date
    d2 = expected_checkin.date() if hasattr(expected_checkin, 'date') else expected_checkin
    wait_days = (d2 - d1).days
    return 0 <= wait_days <= max_hold_days

# add room checkout calculation with surcharge and foreign factor
def calculate_room_checkout(base_price, stay_days, guest_count,
                            has_foreign_guest, regulation):
    actual_days = max(1, stay_days)
    base_total = base_price * actual_days

    surcharge_rate = regulation.extra_guest_rate if guest_count >= regulation.max_guests else 0.0
    guest_factor = regulation.foreign_guest_factor if has_foreign_guest else 1.0

    room_total = base_total * (1 + surcharge_rate) * guest_factor
    return {
        'stay_days': actual_days,
        'extra_guest_rate': surcharge_rate,
        'guest_factor': guest_factor,
        'room_total': round(room_total, 0)
    }

# implement NotificationService for Gmail and Telegram alerts
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
            body += "Đơn đặt phòng #" + str(booking.id) + " của bạn tại Aurelia Hotel & Suites đã được xác nhận thành công.\n"
            body += "- Ngày nhận phòng dự kiến: " + checkin + "\n"
            body += "- Ngày trả phòng dự kiến: " + checkout + "\n"
            body += "- Tổng tiền dự kiến: " + total + " VNĐ\n"
            body += "- Tiền cọc 20% đã thanh toán: " + deposit + " VNĐ\n\n"
            body += "Cảm ơn bạn đã lựa chọn dịch vụ của Aurelia Hotel & Suites!"

            msg = Message(subject=subject, recipients=[to_email], body=body)
            mail.send(msg)
            return True
        except Exception as ex:
            print("Lỗi gửi email:", ex)
            return False

    def send_telegram_notification(self, message):
        token = app.config.get('TELEGRAM_BOT_TOKEN')
        chat_id = app.config.get('TELEGRAM_CHAT_ID')

        if not token or not chat_id:
            return False

        try:
            url = "https://telegram.org" + str(token) + "/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": "[Aurelia Hotel & Suites] " + str(message)
            }
            requests.post(url, json=data, timeout=5)
            return True
        except Exception as ex:
            print("Lỗi gửi Telegram:", ex)
            return False


# add momo service payment link generator
class MoMoService:
    def create_payment_url(self, amount, order_info, redirect_url, ipn_url):
        partner_code = app.config.get('MOMO_PARTNER_CODE')
        access_key = app.config.get('MOMO_ACCESS_KEY')
        secret_key = app.config.get('MOMO_SECRET_KEY')
        endpoint = app.config.get('MOMO_ENDPOINT')

        order_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        amount_str = str(int(amount))
        request_type = "captureWallet"
        extra_data = ""

        raw_signature = (
            "accessKey=" + access_key +
            "&amount=" + amount_str +
            "&extraData=" + extra_data +
            "&ipnUrl=" + ipn_url +
            "&orderId=" + order_id +
            "&orderInfo=" + order_info +
            "&partnerCode=" + partner_code +
            "&redirectUrl=" + redirect_url +
            "&requestId=" + request_id +
            "&requestType=" + request_type
        )

        signature = hmac.new(
            secret_key.encode('utf-8'),
            raw_signature.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        payload = {
            'partnerCode': partner_code,
            'partnerName': 'Aurelia Hotel',
            'storeId': 'AureliaStore',
            'requestId': request_id,
            'amount': amount_str,
            'orderId': order_id,
            'orderInfo': order_info,
            'redirectUrl': redirect_url,
            'ipnUrl': ipn_url,
            'lang': 'vi',
            'extraData': extra_data,
            'requestType': request_type,
            'signature': signature
        }

        res = requests.post(endpoint, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        return res.json()
