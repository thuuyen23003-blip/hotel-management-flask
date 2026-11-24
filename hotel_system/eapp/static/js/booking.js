function selectRoom(id, roomNumber, roomType, basePrice) {
    fetch('/api/select-room', {
        method: 'POST',
        body: JSON.stringify({
            'id': id,
            'room_number': roomNumber,
            'room_type': roomType,
            'base_price': basePrice
        }),
        headers: {
            'Content-Type': 'application/json'
        }
    }).then(function (res) {
        return res.json();
    }).then(function (data) {
        let cartCounter = document.getElementById('cartCounter');
        if (cartCounter) {
            cartCounter.innerText = data.total_rooms;
        }
        let counters = document.getElementsByClassName('booking-counter');
        for (let i = 0; i < counters.length; i++) {
            counters.item(i).innerText = data.total_rooms;
        }
        alert('Đã thêm Phòng ' + roomNumber + ' vào danh sách đặt!');
    });
}

function updateBookingTotals() {
    let checkinEl = document.getElementById('expected_checkin');
    let checkoutEl = document.getElementById('expected_checkout');
    if (!checkinEl || !checkoutEl) return;

    let d1 = new Date(checkinEl.value);
    let d2 = new Date(checkoutEl.value);
    let nights = 1;
    if (!isNaN(d1) && !isNaN(d2) && d2 > d1) {
        nights = Math.round((d2 - d1) / (1000 * 60 * 60 * 24));
    }

    let nightsEl = document.getElementById('stayNightsText');
    if (nightsEl) nightsEl.innerText = nights;

    let rows = document.querySelectorAll('tr[id^="roomRow_"]');
    let unitTotal = 0;
    for (let i = 0; i < rows.length; i++) {
        let priceText = rows.item(i).children.item(2).innerText.replace(/[^0-9]/g, '');
        unitTotal += Number(priceText);
    }

    let total = unitTotal * nights;
    let deposit = Math.round(total * 0.2);

    let totalEl = document.getElementById('estimatedTotal');
    let depositEl = document.getElementById('depositAmount');
    if (totalEl) totalEl.innerText = total.toLocaleString('en-US') + ' VNĐ';
    if (depositEl) depositEl.innerText = deposit.toLocaleString('en-US') + ' VNĐ';
}

function removeRoom(roomId) {
    fetch('/api/remove-room/' + roomId, {
        method: 'DELETE'
    }).then(function (res) {
        return res.json();
    }).then(function (data) {
        let cartCounter = document.getElementById('cartCounter');
        if (cartCounter) cartCounter.innerText = data.total_rooms;

        let selectedCount = document.getElementById('selectedCount');
        if (selectedCount) selectedCount.innerText = data.total_rooms;

        if (data.total_rooms === 0) {
            location.reload();
            return;
        }

        let row = document.getElementById('roomRow_' + roomId);
        if (row) row.remove();

        updateBookingTotals();
    });
}

function confirmBooking() {
    let checkin = document.getElementById('expected_checkin').value;
    let checkout = document.getElementById('expected_checkout').value;

    if (!checkin || !checkout) {
        alert('Vui lòng chọn đầy đủ ngày nhận phòng và ngày trả phòng!');
        return;
    }

    fetch('/api/confirm-booking', {
        method: 'POST',
        body: JSON.stringify({
            'expected_checkin': checkin,
            'expected_checkout': checkout
        }),
        headers: {
            'Content-Type': 'application/json'
        }
    }).then(function (res) {
        return res.json();
    }).then(function (data) {
        if (data.status === 200) {
            location.href = data.pay_url;
        } else {
            alert(data.err_msg);
        }
    });
}

function btnSelectRoom_Click(id, roomNumber, roomType, basePrice) {
    selectRoom(id, roomNumber, roomType, basePrice);
}

function btnRemoveRoom_Click(roomId) {
    removeRoom(roomId);
}

function txtExpectedCheckin_Change() {
    updateBookingTotals();
}

function txtExpectedCheckout_Change() {
    updateBookingTotals();
}

function btnConfirmBooking_Click() {
    confirmBooking();
}
