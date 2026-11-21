import requests
from flask_mail import Message
from eapp import app, mail

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
    wait_days = (expected_checkin.date() - booking_date.date()).days
    return 0 <= wait_days <= max_hold_days


def calculate_room_checkout(base_price, stay_days, guest_count, has_foreign_guest, regulation):
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



