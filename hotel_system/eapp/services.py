import uuid
import hmac
import hashlib
import requests
from flask_mail import Message
from eapp import app, mail


class NotificationService:
    # Send booking confirmation email to customer
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
            body += "Lưu ý: Phiếu đặt phòng có hiệu lực giữ phòng tối đa 28 ngày kể từ ngày đặt.\n"
            body += "Trân trọng cảm ơn bạn đã lựa chọn Aurelia Hotel & Suites!"

            msg = Message(subject=subject, recipients=[to_email], body=body)
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

        try:
            url = "https://api." + "telegram.org/bot" + str(token) + "/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": "[Aurelia Hotel & Suites] " + str(message)
            }
            requests.post(url, json=data, timeout=5)
            return True
        except Exception as ex:
            print("Lỗi gửi Telegram:", ex)
            return False


class MoMoService:
    def create_payment(self, order_id, amount, order_info, return_url, notify_url):
        partner_code = app.config.get('MOMO_PARTNER_CODE')
        access_key = app.config.get('MOMO_ACCESS_KEY')
        secret_key = app.config.get('MOMO_SECRET_KEY')
        endpoint = app.config.get('MOMO_ENDPOINT')

        request_id = str(uuid.uuid4())
        amount_str = str(int(amount))
        request_type = "captureWallet"
        extra_data = ""

        raw_signature = (
            "accessKey=" + str(access_key) +
            "&amount=" + amount_str +
            "&extraData=" + extra_data +
            "&ipnUrl=" + str(notify_url) +
            "&orderId=" + str(order_id) +
            "&orderInfo=" + str(order_info) +
            "&partnerCode=" + str(partner_code) +
            "&redirectUrl=" + str(return_url) +
            "&requestId=" + request_id +
            "&requestType=" + request_type
        )

        signature = hmac.new(
            secret_key.encode('utf-8'),
            raw_signature.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        payload = {
            "partnerCode": partner_code,
            "partnerName": "Aurelia Hotel & Suites",
            "storeId": "AureliaHotel",
            "requestId": request_id,
            "amount": amount_str,
            "orderId": str(order_id),
            "orderInfo": str(order_info),
            "redirectUrl": str(return_url),
            "ipnUrl": str(notify_url),
            "lang": "vi",
            "extraData": extra_data,
            "requestType": request_type,
            "signature": signature
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=10)
            return response.json()
        except Exception as ex:
            return {"resultCode": -1, "message": str(ex)}
