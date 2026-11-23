function filterRoomsByFloor() {
    let selectedFloor = document.getElementById('floorFilter').value;
    let cards = document.getElementsByClassName('room-card-item');
    for (let card of cards) {
        if (selectedFloor === 'ALL' || card.getAttribute('data-floor') === selectedFloor) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    }
}
