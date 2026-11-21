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





