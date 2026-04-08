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
            return 'Chờ duyệt lịch (Hành chính)';
        case 'confirmed':
            return 'Đã xác nhận, chờ check-in';
        case 'checked_in':
            return 'Đã check-in';
        case 'ready_to_inject':
            return 'Chờ tiêm';
        case 'in_observation':
            return 'Đang theo dõi (30 phút)';
        case 'completed':
            return 'Hoàn thành';
        case 'delayed':
            return 'Tạm hoãn';
        case 'cancelled':
            return 'Đã hủy';
        default:
            return status;
    }
}

function getStatusClass(status) {
    switch (status) {
        case 'confirmed':
        case 'checked_in':
            return 'checked_in';
        case 'ready_to_inject':
            return 'ready_to_inject';
        case 'in_observation':
            return 'in_observation';
        case 'completed':
            return 'completed';
        case 'delayed':
            return 'delayed';
        default:
            return '';
    }
}

function getWorkflowHint(booking) {
    const role = window.medicalConfig?.userRole || 'staff';
    switch (booking.status) {
        case 'pending':
            if (role === 'staff' || role === 'admin' || role === 'doctor') {
                return '<div class="pre-screening-snippet" style="color:#0f766e;"><strong>Trạng thái hiện tại: Chờ duyệt lịch (Hành chính)</strong><br>Vui lòng kiểm tra tồn kho và xác nhận lịch hẹn cho bệnh nhân.</div>';
            }
            return '<div class="pre-screening-snippet">Booking đang chờ xác nhận hành chính.</div>';
        case 'confirmed':
            if (role === 'doctor') {
                return '<div class="pre-screening-snippet">Lịch đã được xác nhận. Bước check-in sẽ do staff thực hiện tại quầy.</div>';
            }
            return '<div class="pre-screening-snippet">Đã xác nhận lịch. Y tá có thể check-in để tiếp nhận bệnh nhân.</div>';
        case 'checked_in':
            if (role === 'doctor' || role === 'admin') {
                return '<div class="pre-screening-snippet">Bệnh nhân đã check-in. Bác sĩ có thể thực hiện khám sàng lọc.</div>';
            }
            return '<div class="pre-screening-snippet" style="color:#b45309;"><strong>Đang chờ bác sĩ khám sàng lọc.</strong> Y tá chưa có thao tác tại bước này.</div>';
        case 'ready_to_inject':
            return '<div class="pre-screening-snippet">Bác sĩ đã duyệt. Y tá có thể mở form tiêm chủng.</div>';
        case 'in_observation': {
            const startTime = booking.injection_time ? new Date(booking.injection_time) : new Date();
            const endTime = new Date(startTime.getTime() + 30 * 60 * 1000);
            const timerId = `timer-${booking.id}`;
            setTimeout(() => startCountdown(timerId, endTime), 100);
            return `<div class="pre-screening-snippet">Đã tiêm xong. Đang theo dõi: <strong id="${timerId}">30:00</strong> còn lại.</div>`;
        }
        case 'delayed':
            return '<div class="pre-screening-snippet" style="color:#b45309;">Ca này đang tạm hoãn. Bệnh nhân có thể đặt lại lịch từ trang Booking.</div>';
        default:
            return '';
    }
}

function getActionButton(booking) {
    const role = window.medicalConfig?.userRole || 'staff';

    if (booking.status === 'pending') {
        if (role === 'staff' || role === 'admin' || role === 'doctor') {
            return `<button class="action-btn" style="background:#0f766e;" onclick="confirmBooking('${booking.id}')">✔ Xác nhận lịch</button>`;
        }
        return '<span style="color:#94a3b8; font-size:13px;">Y tá/Hành chính cần duyệt trước</span>';
    }

    if (booking.status === 'confirmed') {
        if (role === 'staff' || role === 'admin') {
            return `<button class="action-btn" onclick="checkIn('${booking.id}')">Check-in</button>`;
        }
        if (role === 'doctor') {
            return '<span style="color:#94a3b8; font-size:13px;">Staff sẽ check-in tại quầy</span>';
        }
        return '';
    }

    if (booking.status === 'checked_in') {
        if (role === 'doctor' || role === 'admin') {
            return `<button class="action-btn" onclick="openScreeningForm('${booking.id}', '${escapeHtml(booking.full_name)}')">Nhập kết quả sàng lọc</button>`;
        }
        return '<span style="color:#b45309; font-size:13px; font-weight:600;">Đang chờ bác sĩ khám sàng lọc</span>';
    }

    if (booking.status === 'ready_to_inject') {
        return `<button class="action-btn" onclick="openInjectionForm('${booking.id}', '${escapeHtml(booking.full_name)}', '${booking.dose_number}')">Tiêm chủng</button>`;
    }

    if (booking.status === 'in_observation') {
        return `<button class="action-btn" onclick="openMonitoringForm('${booking.id}', '${escapeHtml(booking.full_name)}')">Hoàn tất theo dõi</button>`;
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

            if (booking.status === 'ready_to_inject') {
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
    const walkinForm = document.getElementById('form-walkin');
    const subtitle = document.getElementById('action-subtitle');

    defaultBox.style.display = 'block';
    declarationBox.style.display = 'none';
    screeningForm.style.display = 'none';
    injectionForm.style.display = 'none';
    monitoringForm.style.display = 'none';
    if (walkinForm) {
        walkinForm.style.display = 'none';
    }
    subtitle.innerText = 'Vui lòng chọn thao tác từ danh sách bệnh nhân.';

    screeningForm.reset();
    injectionForm.reset();
    monitoringForm.reset();
    if (walkinForm) {
        walkinForm.reset();
    }
}

function hideDefault() {
    document.getElementById('form-default').style.display = 'none';
}

async function confirmBooking(bookingId) {
    if (!window.confirm('Xác nhận duyệt lịch hẹn cho bệnh nhân này? Booking sẽ chuyển sang trạng thái "Đã xác nhận".')) {
        return;
    }

    try {
        const response = await fetch(`/booking/${bookingId}/`, {
            method: 'PATCH',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify({ status: 'confirmed' }),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            window.alert(data.detail || data.status?.[0] || 'Không thể xác nhận lịch lúc này.');
            return;
        }

        window.alert('Đã xác nhận lịch hẹn thành công.');
        await loadTodayBookings();
    } catch (error) {
        console.error(error);
        window.alert('Có lỗi kết nối khi xác nhận lịch.');
    }
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

        resetActionPanel();
        await loadTodayBookings();

        if (data.has_pre_screening === false) {
            openMissingPrescreenModal(bookingId);
        } else {
            window.alert('Check-in thành công.');
        }
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
        decision: document.getElementById('screen-eligible').value,
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

function startCountdown(elementId, endTime) {
    function tick() {
        const el = document.getElementById(elementId);
        if (!el) {
            return;
        }
        const remaining = Math.max(0, endTime - Date.now());
        const mins = Math.floor(remaining / 60000);
        const secs = Math.floor((remaining % 60000) / 1000);
        el.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        if (remaining > 0) {
            setTimeout(tick, 1000);
        } else {
            el.textContent = 'Đã đủ 30 phút, có thể hoàn tất';
            el.style.color = '#16a34a';
        }
    }
    tick();
}

function openWalkinForm() {
    resetActionPanel();
    hideDefault();
    const walkinForm = document.getElementById('form-walkin');
    if (walkinForm) {
        walkinForm.style.display = 'grid';
    }
    document.getElementById('action-subtitle').innerText = 'Tiếp nhận khách vãng lai';
    const dateInput = document.getElementById('walkin-date');
    if (dateInput) {
        dateInput.valueAsDate = new Date();
    }
}

async function submitWalkin(event) {
    event.preventDefault();
    const payload = {
        full_name: document.getElementById('walkin-name').value.trim(),
        phone: document.getElementById('walkin-phone').value.trim(),
        email: document.getElementById('walkin-email').value.trim(),
        vaccine_name: document.getElementById('walkin-vaccine').value,
        vaccine_date: document.getElementById('walkin-date').value,
        dose_number: parseInt(document.getElementById('walkin-dose').value, 10),
        pre_screening: {
            has_fever: document.getElementById('walkin-fever').checked,
            has_allergy_history: document.getElementById('walkin-allergy').checked,
            has_chronic_condition: document.getElementById('walkin-chronic').checked,
            recent_symptoms: document.getElementById('walkin-symptoms').value.trim(),
            current_medications: document.getElementById('walkin-medications').value.trim(),
        },
    };

    try {
        const response = await fetch('/api/medical/walkin/', {
            method: 'POST',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            window.alert(`Lỗi: ${err.detail || JSON.stringify(err)}`);
            return;
        }

        const booking = await response.json();
        window.alert(`Tiếp nhận thành công! Booking #${booking.id} - ${booking.full_name} đã vào hàng đợi.`);
        resetActionPanel();
        await loadTodayBookings();
    } catch (err) {
        console.error(err);
        window.alert('Có lỗi xảy ra khi tiếp nhận walk-in.');
    }
}

function openMissingPrescreenModal(bookingId) {
    const modal = document.getElementById('missing-prescreen-modal');
    if (!modal) {
        return;
    }
    document.getElementById('mpm-booking-id').value = bookingId;
    document.getElementById('missing-prescreen-form').reset();
    document.getElementById('mpm-booking-id').value = bookingId;
    document.getElementById('mpm-notice').style.display = 'none';
    modal.style.display = 'flex';
}

function closeMissingPrescreenModal() {
    const modal = document.getElementById('missing-prescreen-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function submitMissingPrescreen(event) {
    event.preventDefault();
    const bookingId = document.getElementById('mpm-booking-id').value;
    if (!bookingId) {
        return;
    }

    const payload = {
        has_fever: document.getElementById('mpm-fever').checked,
        has_allergy_history: document.getElementById('mpm-allergy').checked,
        has_chronic_condition: document.getElementById('mpm-chronic').checked,
        recent_symptoms: document.getElementById('mpm-symptoms').value.trim(),
        current_medications: document.getElementById('mpm-medications').value.trim(),
        note: 'Bổ sung bởi y tá lúc check-in',
    };

    const btn = document.getElementById('mpm-submit-btn');
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Đang lưu...';

    function getMpmCSRF() {
        const name = 'csrftoken=';
        const cookies = document.cookie ? document.cookie.split(';') : [];
        for (const c of cookies) {
            const t = c.trim();
            if (t.startsWith(name)) {
                return decodeURIComponent(t.slice(name.length));
            }
        }
        return '';
    }

    try {
        const res = await fetch(`/api/medical/pre-screening/${bookingId}/`, {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getMpmCSRF(),
            },
            body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));

        const notice = document.getElementById('mpm-notice');
        if (!res.ok) {
            notice.textContent = `Lỗi: ${data.detail || JSON.stringify(data)}`;
            notice.style.cssText = 'display:block; background:#fff7ed; color:#92400e; border:1px solid #fed7aa; padding:10px 14px; border-radius:8px; margin-bottom:14px; font-size:13px;';
        } else {
            notice.textContent = 'Đã lưu khai báo bổ sung thành công.';
            notice.style.cssText = 'display:block; background:#f0fdf4; color:#166534; border:1px solid #bbf7d0; padding:10px 14px; border-radius:8px; margin-bottom:14px; font-size:13px;';
            setTimeout(() => {
                closeMissingPrescreenModal();
                loadTodayBookings();
            }, 1500);
        }
    } catch (err) {
        console.error(err);
        const notice = document.getElementById('mpm-notice');
        notice.textContent = 'Có lỗi xảy ra khi lưu khai báo.';
        notice.style.cssText = 'display:block; background:#fff7ed; color:#92400e; border:1px solid #fed7aa; padding:10px 14px; border-radius:8px; margin-bottom:14px; font-size:13px;';
    } finally {
        btn.disabled = false;
        btn.textContent = orig;
    }
}
