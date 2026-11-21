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





