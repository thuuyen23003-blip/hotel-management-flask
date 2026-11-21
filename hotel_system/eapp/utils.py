import requests
from flask_mail import Message
from eapp import app, mail


def count_booking_cart(cart):
    total_rooms, total_amount = 0, 0
    if cart:
        for item in cart.values():
            total_rooms += 1
            total_amount += item['price'] * item.get('days', 1)

    return {
        'total_rooms': total_rooms,
        'total_amount': total_amount
    }


def calculate_deposit(total_amount, deposit_rate):
    return round(total_amount * deposit_rate, 0)
