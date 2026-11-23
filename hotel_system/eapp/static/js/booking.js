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
    }).then(res => res.json()).then(data => {
        let counters = document.getElementsByClassName('booking-counter');
        for (let c of counters) {
            c.innerText = data.total_rooms;
        }
        alert('Đã thêm Phòng ' + roomNumber + ' vào danh sách đặt!');
    });
}

function removeRoom(roomId) {
    if (confirm('Bạn chắc chắn muốn bỏ chọn phòng này?')) {
        fetch('/api/remove-room/' + roomId, {
            method: 'DELETE'
        }).then(res => res.json()).then(data => {
            let row = document.getElementById('room-row-' + roomId);
            if (row) row.remove();
            location.reload();
        });
    }
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
    }).then(res => res.json()).then(data => {
        if (data.status === 200) {
            location.href = data.pay_url;
        } else {
            alert(data.err_msg);
        }
    });
}
