function filterRoomsByFloor() {
    let selectedFloor = document.getElementById('floorFilter').value;
    let cards = document.getElementsByClassName('room-card-item');
    for (let i = 0; i < cards.length; i++) {
        if (selectedFloor === 'ALL' || cards[i].getAttribute('data-floor') === selectedFloor) {
            cards[i].style.display = 'block';
        } else {
            cards[i].style.display = 'none';
        }
    }
}

function switchReceptionForm() {
    let selected = document.getElementById('customerScenarioSelect').value;
    let boxes = document.getElementsByClassName('reception-scenario-box');
    for (let i = 0; i < boxes.length; i++) {
        boxes[i].style.display = 'none';
    }
    let activeBox = document.getElementById('formBox_' + selected);
    if (activeBox) {
        activeBox.style.display = 'block';
    }
}

function isOnlyLetters(text) {
    for (let i = 0; i < text.length; i++) {
        let ch = text[i];
        if (ch >= '0' && ch <= '9') {
            return false;
        }
        if ("!@#$%^&*()_+=[]{}|;:'\",.<>?/\\~`".indexOf(ch) !== -1) {
            return false;
        }
    }
    return true;
}

function isDigitsOnly(text) {
    if (isNaN(text) || text.indexOf(' ') !== -1 || text.indexOf('.') !== -1) {
        return false;
    }
    for (let i = 0; i < text.length; i++) {
        if (text[i] < '0' || text[i] > '9') {
            return false;
        }
    }
    return true;
}

function showRowError(row, msg) {
    let errRow = row.nextElementSibling;
    let errText = errRow.getElementsByTagName('small')[0];
    if (msg) {
        errRow.style.display = 'table-row';
        errText.innerText = msg;
    } else {
        errRow.style.display = 'none';
        errText.innerText = '';
    }
}

function checkOneRow(row, isFirstRequired) {
    let stt = row.getAttribute('data-row');
    let inputs = row.getElementsByTagName('input');
    let name = inputs[0].value.trim();
    let cccd = inputs[1].value.trim();
    let address = inputs[2].value.trim();

    if (name === '' && cccd === '' && address === '') {
        if (isFirstRequired && stt === '1') {
            showRowError(row, 'Dòng số 1: Vui lòng nhập đầy đủ họ tên và số CMND/CCCD khách hàng!');
            return false;
        }
        showRowError(row, '');
        return true;
    }

    if (name === '') {
        showRowError(row, 'Dòng số ' + stt + ': Vui lòng nhập họ tên khách hàng!');
        return false;
    }

    if (name.length < 2 || !isOnlyLetters(name)) {
        showRowError(row, 'Dòng số ' + stt + ': Họ tên khách hàng chỉ được chứa chữ cái!');
        return false;
    }

    if (cccd === '') {
        showRowError(row, 'Dòng số ' + stt + ': Vui lòng nhập số CMND/CCCD!');
        return false;
    }

    if (!isDigitsOnly(cccd) || (cccd.length !== 9 && cccd.length !== 12)) {
        showRowError(row, 'Dòng số ' + stt + ': Số CMND/CCCD phải gồm đúng 9 hoặc 12 chữ số!');
        return false;
    }

    showRowError(row, '');
    return true;
}

function checkGuestRow(inputElem) {
    let row = inputElem.parentElement.parentElement;
    let form = row.closest('form');
    let isFirstRequired = (form.getAttribute('data-require-one') === 'true');
    checkOneRow(row, isFirstRequired);
}

function validateGuestForm(form) {
    let isFirstRequired = (form.getAttribute('data-require-one') === 'true');
    let rows = form.getElementsByTagName('tr');
    let isValid = true;

    for (let i = 0; i < rows.length; i++) {
        if (rows[i].hasAttribute('data-row')) {
            if (!checkOneRow(rows[i], isFirstRequired)) {
                isValid = false;
            }
        }
    }
    return isValid;
}
