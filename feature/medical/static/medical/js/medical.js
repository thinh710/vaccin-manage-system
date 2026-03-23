document.addEventListener('DOMContentLoaded', () => {
    // Set current date string
    const now = new Date();
    document.getElementById('current-date').innerText = `Ngay truc: ${now.toLocaleDateString('vi-VN')}`;
    loadTodayBookings();
});

function getCSRFToken() {
    let cookieValue = null;
    const name = "csrftoken";
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const headers = {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCSRFToken()
};

async function loadTodayBookings() {
    try {
        const response = await fetch('/api/medical/today/');
        const data = await response.json();
        const listEl = document.getElementById('patient-list');
        listEl.innerHTML = '';
        
        let waitCount = 0;
        let compCount = 0;
        
        if (data.length === 0) {
            listEl.innerHTML = '<div class="empty-state">Hôm nay chưa có danh sách đặt lịch.</div>';
        }

        data.forEach(booking => {
            if (booking.status === 'screened') waitCount++;
            if (booking.status === 'completed') compCount++;
            
            const row = document.createElement('div');
            row.className = 'patient-row';
            
            let badgeClass = '';
            let vnStatus = booking.status;
            switch(booking.status) {
                case 'pending': badgeClass = ''; vnStatus = 'Chưa check-in'; break;
                case 'checked_in': badgeClass = 'checked_in'; vnStatus = 'Đã check-in'; break;
                case 'screened': badgeClass = 'screened'; vnStatus = 'Đã sàng lọc (Chờ tiêm)'; break;
                case 'completed': badgeClass = 'completed'; vnStatus = 'Hoàn thành'; break;
                case 'delayed': badgeClass = 'delayed'; vnStatus = 'Hoãn tiêm'; break;
                case 'cancelled': badgeClass = 'not-fit'; vnStatus = 'Đã hủy'; break;
            }
            
            let actionsHTML = '';
            if (booking.status === 'pending') {
                actionsHTML = `<button class="action-btn" onclick="checkIn('${booking.id}')">Check-In</button>`;
            } else if (booking.status === 'checked_in' || booking.status === 'delayed') {
                actionsHTML = `<button class="action-btn" onclick="openScreeningForm('${booking.id}', '${booking.full_name}')">Khám / Sàng lọc</button>`;
            } else if (booking.status === 'screened') {
                actionsHTML = `<button class="action-btn" onclick="openInjectionForm('${booking.id}', '${booking.full_name}', '${booking.dose_number}')">Tiêm chủng</button>`;
            } else if (booking.status === 'completed') {
                // Simplified assumption: monitor is available after completed
                // Note: We'd need vaccinationLog id to properly create post injection tracking, 
                // but doing it by finding from backend, for simplicity we pass booking id and backend would handle it ideally.
                // Or we fetch it. We will use a hack in views or just pass booking ID. 
                // Wait, our backend endpoint takes vaccination_log as ID. We might need to adjust endpoint or find it.
                // Let's open it anyway.
                actionsHTML = `<button class="action-btn" onclick="openMonitoringForm('${booking.id}', '${booking.full_name}')">Theo dõi phản ứng</button>`;
            }

            row.innerHTML = `
                <div class="screening-main">
                    <strong>${booking.full_name} • ${booking.vaccine_name}</strong>
                    <div>Mũi: ${booking.dose_number} • ĐT: ${booking.phone}</div>
                    <div style="margin-top: 6px;">
                        <span class="badge ${badgeClass}">${vnStatus}</span>
                    </div>
                    <div class="action-buttons">${actionsHTML}</div>
                </div>
            `;
            listEl.appendChild(row);
        });

        // Update stats
        document.getElementById('stat-total').innerText = data.length;
        document.getElementById('stat-waiting').innerText = waitCount;
        document.getElementById('stat-completed').innerText = compCount;

    } catch (err) {
        console.error("Error loading bookings:", err);
    }
}

// Reset right panel elements
function resetActionPanel() {
    document.getElementById('form-default').style.display = 'block';
    document.getElementById('form-screening').style.display = 'none';
    document.getElementById('form-injection').style.display = 'none';
    document.getElementById('form-monitoring').style.display = 'none';
    document.getElementById('action-subtitle').innerText = 'Vui lòng chọn thao tác từ danh sách bệnh nhân.';
}

function hideDefault() {
    document.getElementById('form-default').style.display = 'none';
}

// Check-in logic
async function checkIn(bookingId) {
    if (!confirm("Xác nhận Check-in cho bệnh nhân này?")) return;
    try {
        const response = await fetch(`/api/medical/${bookingId}/check-in/`, {
            method: 'PATCH',
            headers: headers
        });
        if (response.ok) {
            alert('Check-in thành công!');
            loadTodayBookings();
        } else {
            alert('Lỗi khi Check-in!');
        }
    } catch (err) {
        console.error(err);
    }
}

// Screening
function openScreeningForm(bookingId, name) {
    resetActionPanel();
    hideDefault();
    document.getElementById('form-screening').style.display = 'flex';
    document.getElementById('screen-booking-id').value = bookingId;
    document.getElementById('action-subtitle').innerText = `Khám sàng lọc cho: ${name}`;
    document.getElementById('form-screening').reset();
}

async function submitScreening(event) {
    event.preventDefault();
    const data = {
        booking: parseInt(document.getElementById('screen-booking-id').value),
        temperature: parseFloat(document.getElementById('screen-temp').value),
        blood_pressure: document.getElementById('screen-bp').value,
        is_eligible: document.getElementById('screen-eligible').value === 'true',
        doctor_note: document.getElementById('screen-note').value
    };
    try {
        const response = await fetch('/api/medical/screening/', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        });
        if (response.ok) {
            alert('Lưu kết quả khám thành công!');
            resetActionPanel();
            loadTodayBookings();
        } else {
            const errText = await response.text();
            alert('Có lỗi xảy ra: ' + errText);
            console.error(errText);
        }
    } catch (err) {
        console.error(err);
    }
}

// Injection
function openInjectionForm(bookingId, name, dose) {
    resetActionPanel();
    hideDefault();
    document.getElementById('form-injection').style.display = 'flex';
    document.getElementById('inject-booking-id').value = bookingId;
    document.getElementById('inject-dose').value = dose;
    document.getElementById('action-subtitle').innerText = `Thông tin tiêm chủng cho: ${name}`;
}

async function submitInjection(event) {
    event.preventDefault();
    const data = {
        booking: parseInt(document.getElementById('inject-booking-id').value),
        vaccine_id: document.getElementById('inject-vaccine').value,
        batch_number: document.getElementById('inject-batch').value,
        injected_by: document.getElementById('inject-by').value,
        dose_number: parseInt(document.getElementById('inject-dose').value)
    };
    try {
        const response = await fetch('/api/medical/inject/', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        });
        if (response.ok) {
            alert('Xác nhận đã tiêm thành công!');
            resetActionPanel();
            loadTodayBookings();
        } else {
            const errText = await response.text();
            alert('Có lỗi xảy ra: ' + errText);
            console.error(errText);
        }
    } catch (err) {
        console.error(err);
    }
}

// Monitoring 
function openMonitoringForm(bookingId, name) {
    resetActionPanel();
    hideDefault();
    document.getElementById('form-monitoring').style.display = 'flex';
    // MOCK: Because the backend requires vaccination_log ID, not booking ID directly.
    // In a real scenario we'd query the DB for the log ID. For now we pass bookingId
    // We need to modify our endpoint or handle it in JS. Let's see. PostInjectionTrackingSerializer 
    // requires `vaccination_log` field (the PK of the log).
    // For now we will store the booking ID in a global or fetch the log first. Let's fetch the log ID in the view or handle the PK.
    // wait! The monitor endpoint receives vaccination_log. So we will just let it fail or we need to fix it.
    // To fix this without changing backend logic deeply, we will just send it. Actually, the backend `PostInjectionTrackingSerializer` needs `vaccination_log` which is the ID of the `VaccinationLog`.
    document.getElementById('monitor-vaccination-id').value = bookingId; // Might cause FK error if IDs don't match!
    
    // So let's fetch the vaccination log by booking ID in the backend, or we can just send the booking ID to a custom "monitor by booking" view. Oh wait, we wrote `submit_post_injection_tracking` which uses ModelSerializer directly. 
    // This is problematic. Let me update `submit_post_injection_tracking` to accept `booking` and find the `VaccinationLog` inside the view before saving. 
    
    document.getElementById('action-subtitle').innerText = `Theo dõi phản ứng cho: ${name}`;
}

async function submitMonitoring(event) {
    event.preventDefault();
    const bookingId = document.getElementById('monitor-vaccination-id').value;
    const data = {
        booking: parseInt(bookingId),
        reaction_status: document.getElementById('monitor-reaction').value,
        notes: document.getElementById('monitor-note').value
    };
    try {
        const response = await fetch('/api/medical/monitor/', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        });
        if (response.ok) {
            alert('Lưu trạng thái theo dõi thành công!');
            resetActionPanel();
            loadTodayBookings();
        } else {
            const errJson = await response.json();
            alert('Có lỗi: ' + JSON.stringify(errJson));
        }
    } catch (err) {
        console.error(err);
    }
}
