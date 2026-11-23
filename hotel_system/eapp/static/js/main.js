function addSelectedRoom(id, roomNumber, roomType, basePrice) {
    fetch('/api/selected-rooms', {
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
        let counters = document.getElementsByClassName('room-counter');
        for (let c of counters) {
            c.innerText = data.total_rooms;
        }
        alert('Đã thêm Phòng ' + roomNumber + ' vào danh sách đặt!');
    });
}

function removeSelectedRoom(roomId) {
    if (confirm('Bạn chắc chắn muốn bỏ chọn phòng này không?')) {
        fetch('/api/selected-rooms/' + roomId, {
            method: 'DELETE'
        }).then(res => res.json()).then(data => {
            let counters = document.getElementsByClassName('room-counter');
            for (let c of counters) {
                c.innerText = data.total_rooms;
            }
            let row = document.getElementById('room-row-' + roomId);
            if (row) {
                row.style.display = 'none';
            }
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

    if (confirm('Xác nhận đặt phòng và thanh toán tiền cọc 20%?')) {
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
                alert('Lỗi: ' + data.err_msg);
            }
        });

    }
}
