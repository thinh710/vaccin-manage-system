document.addEventListener('DOMContentLoaded', () => {
    const now = new Date();
    const currentDate = document.getElementById('current-date');
    if (currentDate) {
        currentDate.innerText = `Ngày trực: ${now.toLocaleDateString('vi-VN')}`;
    }
    loadTodayBookings();
});

function getCSRFToken() {
    let cookieValue = null;
    const name = 'csrftoken';
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i += 1) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === `${name}=`) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const headers = {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCSRFToken(),
};

let todayBookingsById = {};

async function getResponseErrorMessage(response, fallbackMessage) {
    const rawText = await response.text().catch(() => '');
    if (!rawText) {
        return fallbackMessage;
    }

    try {
        const payload = JSON.parse(rawText);
        if (typeof payload.detail === 'string') {
            return payload.detail;
        }
        return JSON.stringify(payload);
    } catch (error) {
        return rawText;
    }
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderPreScreeningBox(bookingId) {
    const declarationBox = document.getElementById('pre-screening-box');
    if (!declarationBox) {
        return;
    }

    const booking = todayBookingsById[String(bookingId)];
    const declaration = booking?.pre_screening;
    declarationBox.style.display = 'block';

    if (!declaration) {
        declarationBox.innerHTML = '<strong>Khai báo trước tiêm</strong><div>Chưa có khai báo trước tiêm từ bệnh nhân.</div>';
        return;
    }

    declarationBox.innerHTML = `
        <strong>Khai báo trước tiêm</strong>
        <div class="declaration-grid">
            <div>Sốt: ${declaration.has_fever ? 'Có' : 'Không'}</div>
            <div>Dị ứng: ${declaration.has_allergy_history ? 'Có' : 'Không'}</div>
            <div>Bệnh nền: ${declaration.has_chronic_condition ? 'Có' : 'Không'}</div>
        </div>
        ${declaration.recent_symptoms ? `<div>Triệu chứng gần đây: ${escapeHtml(declaration.recent_symptoms)}</div>` : ''}
        ${declaration.current_medications ? `<div>Thuốc đang dùng: ${escapeHtml(declaration.current_medications)}</div>` : ''}
        ${declaration.note ? `<div>Ghi chú thêm: ${escapeHtml(declaration.note)}</div>` : ''}
    `;
}

function getStatusLabel(status) {
    switch (status) {
        case 'pending':
            return 'Chờ bác sĩ xác nhận';
        case 'confirmed':
            return 'Đã xác nhận, chờ check-in';
        case 'checked_in':
            return 'Đã check-in';
        case 'screened':
            return 'Đã sàng lọc, chờ tiêm';
        case 'completed':
            return 'Hoàn thành';
        case 'delayed':
            return 'Chờ bác sĩ xác nhận lại';
        case 'cancelled':
            return 'Đã hủy';
        default:
            return status;
    }
}

function getStatusClass(status) {
    switch (status) {
        case 'confirmed':
            return 'checked_in';
        case 'checked_in':
            return 'checked_in';
        case 'screened':
            return 'screened';
        case 'completed':
            return 'completed';
        case 'delayed':
            return 'delayed';
        default:
            return '';
    }
}

function getWorkflowHint(booking) {
    switch (booking.status) {
        case 'pending':
            return '<div class="pre-screening-snippet">Booking đang chờ bác sĩ xác nhận, y tá chưa thể thao tác.</div>';
        case 'confirmed':
            return '<div class="pre-screening-snippet">Đã được bác sĩ xác nhận. Y tá có thể check-in để tiếp nhận bệnh nhân.</div>';
        case 'checked_in':
            return '<div class="pre-screening-snippet">Bệnh nhân đã check-in. Có thể mở form khám / sàng lọc.</div>';
        case 'delayed':
            return '<div class="pre-screening-snippet">Ca này đang tạm hoãn và cần bác sĩ xác nhận lại trước khi xử lý tiếp.</div>';
        default:
            return '';
    }
}

function getActionButton(booking) {
    if (booking.status === 'confirmed') {
        return `<button class="action-btn" onclick="checkIn('${booking.id}')">Check-in</button>`;
    }
    if (booking.status === 'checked_in') {
        return `<button class="action-btn" onclick="openScreeningForm('${booking.id}', '${escapeHtml(booking.full_name)}')">Khám / Sàng lọc</button>`;
    }
    if (booking.status === 'screened') {
        return `<button class="action-btn" onclick="openInjectionForm('${booking.id}', '${escapeHtml(booking.full_name)}', '${booking.dose_number}')">Tiêm chủng</button>`;
    }
    if (booking.status === 'completed') {
        return `<button class="action-btn" onclick="openMonitoringForm('${booking.id}', '${escapeHtml(booking.full_name)}')">Theo dõi phản ứng</button>`;
    }
    return '';
}

function getPreScreeningSnippet(booking) {
    if (!booking.pre_screening) {
        return '<div class="pre-screening-snippet">Chưa có khai báo trước tiêm từ bệnh nhân.</div>';
    }

    return `
        <div class="pre-screening-snippet">
            Khai báo trước tiêm: sốt ${booking.pre_screening.has_fever ? 'có' : 'không'}, dị ứng ${booking.pre_screening.has_allergy_history ? 'có' : 'không'}, bệnh nền ${booking.pre_screening.has_chronic_condition ? 'có' : 'không'}.
        </div>
    `;
}

async function loadTodayBookings() {
    try {
        const response = await fetch('/api/medical/today/', {
            credentials: 'same-origin',
        });
        const data = await response.json();
        const listEl = document.getElementById('patient-list');
        listEl.innerHTML = '';
        todayBookingsById = {};

        let waitingInjectionCount = 0;
        let completedCount = 0;

        if (data.length === 0) {
            listEl.innerHTML = '<div class="empty-state">Hôm nay chưa có danh sách đặt lịch.</div>';
        }

        data.forEach((booking) => {
            todayBookingsById[String(booking.id)] = booking;

            if (booking.status === 'screened') {
                waitingInjectionCount += 1;
            }
            if (booking.status === 'completed') {
                completedCount += 1;
            }

            const row = document.createElement('div');
            row.className = 'patient-row';

            row.innerHTML = `
                <div class="screening-main">
                    <strong>${escapeHtml(booking.full_name)} • ${escapeHtml(booking.vaccine_name)}</strong>
                    <div>Mũi: ${booking.dose_number} • ĐT: ${escapeHtml(booking.phone)}</div>
                    ${getPreScreeningSnippet(booking)}
                    ${getWorkflowHint(booking)}
                    <div style="margin-top: 6px;">
                        <span class="badge ${getStatusClass(booking.status)}">${getStatusLabel(booking.status)}</span>
                    </div>
                    <div class="action-buttons">${getActionButton(booking)}</div>
                </div>
            `;
            listEl.appendChild(row);
        });

        document.getElementById('stat-total').innerText = data.length;
        document.getElementById('stat-waiting').innerText = waitingInjectionCount;
        document.getElementById('stat-completed').innerText = completedCount;
    } catch (error) {
        console.error('Lỗi tải danh sách booking:', error);
    }
}

function resetActionPanel() {
    const defaultBox = document.getElementById('form-default');
    const declarationBox = document.getElementById('pre-screening-box');
    const screeningForm = document.getElementById('form-screening');
    const injectionForm = document.getElementById('form-injection');
    const monitoringForm = document.getElementById('form-monitoring');
    const subtitle = document.getElementById('action-subtitle');

    defaultBox.style.display = 'block';
    declarationBox.style.display = 'none';
    screeningForm.style.display = 'none';
    injectionForm.style.display = 'none';
    monitoringForm.style.display = 'none';
    subtitle.innerText = 'Vui lòng chọn thao tác từ danh sách bệnh nhân.';

    screeningForm.reset();
    injectionForm.reset();
    monitoringForm.reset();
}

function hideDefault() {
    document.getElementById('form-default').style.display = 'none';
}

async function checkIn(bookingId) {
    if (!window.confirm('Xác nhận check-in cho bệnh nhân này?')) {
        return;
    }

    try {
        const response = await fetch(`/api/medical/${bookingId}/check-in/`, {
            method: 'PATCH',
            headers,
            credentials: 'same-origin',
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            window.alert(data.detail || 'Không thể check-in lúc này.');
            return;
        }

        window.alert('Check-in thành công.');
        resetActionPanel();
        await loadTodayBookings();
    } catch (error) {
        console.error(error);
    }
}

function openScreeningForm(bookingId, name) {
    resetActionPanel();
    hideDefault();
    renderPreScreeningBox(bookingId);

    const form = document.getElementById('form-screening');
    form.style.display = 'grid';
    form.reset();

    document.getElementById('screen-booking-id').value = bookingId;
    document.getElementById('action-subtitle').innerText = `Khám sàng lọc cho: ${name}`;
}

async function submitScreening(event) {
    event.preventDefault();
    const data = {
        booking: parseInt(document.getElementById('screen-booking-id').value, 10),
        temperature: parseFloat(document.getElementById('screen-temp').value),
        blood_pressure: document.getElementById('screen-bp').value.trim(),
        is_eligible: document.getElementById('screen-eligible').value === 'true',
        doctor_note: document.getElementById('screen-note').value.trim(),
    };

    try {
        const response = await fetch('/api/medical/screening/', {
            method: 'POST',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errorMessage = await getResponseErrorMessage(response, 'Không thể lưu kết quả khám lúc này.');
            window.alert(`Có lỗi xảy ra: ${errorMessage}`);
            console.error(errorMessage);
            return;
        }

        window.alert('Lưu kết quả khám thành công.');
        resetActionPanel();
        await loadTodayBookings();
    } catch (error) {
        console.error(error);
    }
}

function openInjectionForm(bookingId, name, dose) {
    resetActionPanel();
    hideDefault();
    renderPreScreeningBox(bookingId);

    const form = document.getElementById('form-injection');
    form.style.display = 'grid';
    form.reset();

    const batchInput = document.getElementById('inject-batch');
    if (batchInput) {
        batchInput.required = false;
        batchInput.placeholder = 'Tùy chọn, hệ thống sẽ tự điền từ kho nếu có.';
    }

    document.getElementById('inject-booking-id').value = bookingId;
    document.getElementById('inject-dose').value = dose;
    document.getElementById('action-subtitle').innerText = `Thông tin tiêm chủng cho: ${name}`;
}

async function submitInjection(event) {
    event.preventDefault();
    const data = {
        booking: parseInt(document.getElementById('inject-booking-id').value, 10),
        injected_by: document.getElementById('inject-by').value.trim(),
        dose_number: parseInt(document.getElementById('inject-dose').value, 10),
    };

    const batchInput = document.getElementById('inject-batch');
    if (batchInput && batchInput.value.trim()) {
        data.batch_number = batchInput.value.trim();
    }

    try {
        const response = await fetch('/api/medical/inject/', {
            method: 'POST',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errorMessage = await getResponseErrorMessage(response, 'Không thể xác nhận tiêm lúc này.');
            window.alert(`Có lỗi xảy ra: ${errorMessage}`);
            console.error(errorMessage);
            return;
        }

        window.alert('Xác nhận đã tiêm thành công.');
        resetActionPanel();
        await loadTodayBookings();
    } catch (error) {
        console.error(error);
    }
}

function openMonitoringForm(bookingId, name) {
    resetActionPanel();
    hideDefault();
    renderPreScreeningBox(bookingId);

    const form = document.getElementById('form-monitoring');
    form.style.display = 'grid';
    form.reset();

    document.getElementById('monitor-vaccination-id').value = bookingId;
    document.getElementById('action-subtitle').innerText = `Theo dõi phản ứng cho: ${name}`;
}

async function submitMonitoring(event) {
    event.preventDefault();
    const data = {
        booking: parseInt(document.getElementById('monitor-vaccination-id').value, 10),
        reaction_status: document.getElementById('monitor-reaction').value,
        notes: document.getElementById('monitor-note').value.trim(),
    };

    try {
        const response = await fetch('/api/medical/monitor/', {
            method: 'POST',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errJson = await response.json().catch(() => ({}));
            window.alert(`Có lỗi: ${JSON.stringify(errJson)}`);
            return;
        }

        window.alert('Lưu trạng thái theo dõi thành công.');
        resetActionPanel();
        await loadTodayBookings();
    } catch (error) {
        console.error(error);
    }
}
