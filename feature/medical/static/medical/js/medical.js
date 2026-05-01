document.addEventListener('DOMContentLoaded', () => {
    const now = new Date();
    const currentDate = document.getElementById('current-date');
    if (currentDate) {
        currentDate.innerText = `Ngay truc: ${now.toLocaleDateString('vi-VN')}`;
    }
    setupMedicalDeclarationForms();
    setupPatientSearch();
    setupPatientSort();
    setupWalkinVaccineSearch();
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

const PATIENTS_PER_PAGE = 5;
let todayBookings = [];
let todayBookingsById = {};
let patientSearchTerm = '';
let currentPatientPage = 1;
let currentPatientSort = { key: 'vaccine_date', direction: 'asc' };
let walkinVaccineOptions = [];
let filteredWalkinVaccineOptions = [];
let highlightedWalkinVaccineIndex = -1;
let selectedWalkinVaccineValue = '';
const MEDICAL_DECLARATION_FIELDS = [
    {
        prefixKey: 'severe-allergy',
        boolKey: 'has_severe_allergy',
        detailKey: 'severe_allergy_details',
        label: 'Tien su phan ve/di ung nang hoac di ung voi thanh phan thuoc/thuc an',
        placeholder: 'Mo ta phan ung, tac nhan, muc do...'
    },
    {
        prefixKey: 'current-health-issue',
        boolKey: 'has_current_health_issue',
        detailKey: 'current_health_issue_details',
        label: 'Tinh trang suc khoe hien tai: sot, benh cap tinh, hoac benh man tinh dang dot cap',
        placeholder: 'Mo ta trieu chung, benh ly, dot cap...'
    },
    {
        prefixKey: 'recent-vaccination',
        boolKey: 'had_recent_vaccination',
        detailKey: 'recent_vaccination_details',
        label: 'Da tiem vaccine khac trong vong 14 - 28 ngay qua',
        placeholder: 'Loai vaccine, ngay tiem, phan ung neu co...'
    },
    {
        prefixKey: 'immunosuppressive-medication',
        boolKey: 'uses_immunosuppressive_medication',
        detailKey: 'immunosuppressive_medication_details',
        label: 'Dang dung thuoc uc che mien dich, corticoid lieu cao, hoac dieu tri ung thu',
        placeholder: 'Ten thuoc, lieu dung, thoi gian su dung...'
    },
    {
        prefixKey: 'pregnancy-consideration',
        boolKey: 'has_pregnancy_or_breastfeeding_consideration',
        detailKey: 'pregnancy_or_breastfeeding_details',
        label: 'Doi voi nu gioi trong do tuoi sinh de: mang thai, du dinh mang thai, hoac dang cho con bu',
        placeholder: 'Mo ta tinh trang hien tai, du dinh mang thai, hoac cho con bu...'
    }
];

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

function normalizeSearchText(value) {
    return String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/Ä‘/g, 'd')
        .replace(/Ä/g, 'D')
        .toLowerCase()
        .trim();
}

function formatDate(value) {
    if (!value) {
        return '--';
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }
    return parsed.toLocaleDateString('vi-VN');
}

function getDepositState(booking) {
    if (booking.deposit_deadline_status && booking.deposit_deadline_status !== 'not_applicable') {
        return booking.deposit_deadline_status;
    }
    if (booking.status === 'confirmed' && booking.deposit_paid_at) {
        return 'paid';
    }
    if (booking.status === 'deposit_pending') {
        return booking.deposit_deadline_status || 'pending';
    }
    return 'not_applicable';
}

function getDepositLabel(booking) {
    const state = getDepositState(booking);
    switch (state) {
        case 'paid':
            return 'Da coc';
        case 'warning':
            return 'Sap het han';
        case 'upcoming':
            return 'Cho coc';
        case 'expired':
            return 'Qua han';
        default:
            return booking.booking_source === 'walkin' ? 'Walk-in' : '--';
    }
}

function getDepositClass(booking) {
    switch (getDepositState(booking)) {
        case 'paid':
            return 'completed';
        case 'warning':
        case 'expired':
            return 'delayed';
        case 'upcoming':
            return 'deposit_pending';
        default:
            return '';
    }
}

function getMedicalDeclarationFormMarkup(prefix, options = {}) {
    const background = options.background || '#f8fafc';
    const border = options.border || '#e2e8f0';
    return MEDICAL_DECLARATION_FIELDS.map((field) => (
        `<div style="display:grid; gap:6px;">
            <label style="display:flex; align-items:center; gap:10px; padding:11px 13px; border-radius:9px; background:${background}; border:1px solid ${border}; font-weight:600; cursor:pointer;">
                <input type="checkbox" id="${prefix}-${field.prefixKey}" style="width:17px;height:17px;">
                <span>${field.label}</span>
            </label>
            <label style="display:grid; gap:5px; font-weight:600;">
                <span>Chi tiet</span>
                <textarea id="${prefix}-${field.prefixKey}-details" rows="2" placeholder="${field.placeholder}" style="padding:9px 11px; border:1px solid #d1d5db; border-radius:7px; font:inherit; resize:vertical;"></textarea>
            </label>
        </div>`
    )).join('');
}

function setupMedicalDeclarationForms() {
    const walkinFieldset = document.querySelector('#form-walkin fieldset');
    if (walkinFieldset) {
        walkinFieldset.innerHTML = `
            <legend style="font-size:13px; font-weight:500; padding:0 6px;">Khai bao y te so bo</legend>
            ${getMedicalDeclarationFormMarkup('walkin')}
        `;
    }
}

function collectMedicalDeclarationPayload(prefix) {
    const payload = {};
    MEDICAL_DECLARATION_FIELDS.forEach((field) => {
        payload[field.boolKey] = Boolean(document.getElementById(`${prefix}-${field.prefixKey}`)?.checked);
        payload[field.detailKey] = document.getElementById(`${prefix}-${field.prefixKey}-details`)?.value.trim() || '';
    });
    return payload;
}

function renderMedicalDeclarationSummary(declaration) {
    if (!declaration) {
        return ['Chua co khai bao truoc tiem tu benh nhan.'];
    }

    const lines = [];
    MEDICAL_DECLARATION_FIELDS.forEach((field) => {
        const state = declaration[field.boolKey] ? 'Co' : 'Khong';
        const detail = declaration[field.detailKey] ? `: ${escapeHtml(declaration[field.detailKey])}` : '';
        lines.push(`${field.label}: ${state}${detail}`);
    });
    if (declaration.note) {
        lines.push(`Ghi chu them: ${escapeHtml(declaration.note)}`);
    }
    return lines;
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
        declarationBox.innerHTML = '<strong>Khai bao truoc tiem</strong><div>Chua co khai bao truoc tiem tu benh nhan.</div>';
        return;
    }

    declarationBox.innerHTML = `
        <strong>Khai bao truoc tiem</strong>
        ${renderMedicalDeclarationSummary(declaration).map((line) => `<div>${line}</div>`).join('')}
    `;
}

function renderOnlineReviewBox(bookingId) {
    const reviewBox = document.getElementById('online-review-box');
    if (!reviewBox) {
        return;
    }

    const booking = todayBookingsById[String(bookingId)];
    const review = booking?.online_review;
    reviewBox.style.display = 'block';

    if (!review) {
        reviewBox.innerHTML = '<strong>Ket luan duyet online</strong><div>Chua co ket luan duyet online tu bac si.</div>';
        return;
    }

    const decisionMap = {
        eligible: 'Du dieu kien tiem',
        delayed: 'Tam hoan',
        ineligible: 'Khong du dieu kien tiem',
    };
    const meta = [
        review.reviewed_by_name || '',
        review.reviewed_at ? new Date(review.reviewed_at).toLocaleString('vi-VN') : '',
    ].filter(Boolean).join(' • ');

    reviewBox.innerHTML = `
        <strong>Ket luan duyet online</strong>
        <div>${decisionMap[review.decision] || review.decision}</div>
        ${meta ? `<div>${escapeHtml(meta)}</div>` : ''}
        ${review.doctor_note ? `<div>${escapeHtml(review.doctor_note)}</div>` : ''}
    `;
}

function getStatusLabel(status) {
    switch (status) {
        case 'awaiting_eligibility':
            return 'Cho duyet dieu kien';
        case 'pending':
            return 'Cho duyet lich';
        case 'deposit_pending':
            return 'Cho dat coc';
        case 'confirmed':
            return 'Da xac nhan, cho check-in';
        case 'ineligible':
            return 'Khong du dieu kien tiem';
        case 'checked_in':
            return 'Da check-in';
        case 'ready_to_inject':
            return 'Cho tiem';
        case 'in_observation':
            return 'Dang theo doi';
        case 'completed':
            return 'Hoan thanh';
        case 'delayed':
            return 'Tam hoan';
        case 'cancelled':
            return 'Da huy';
        default:
            return status;
    }
}

function getStatusClass(status) {
    switch (status) {
        case 'awaiting_eligibility':
        case 'pending':
            return 'awaiting_eligibility';
        case 'deposit_pending':
            return 'deposit_pending';
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
        case 'cancelled':
        case 'ineligible':
            return 'delayed';
        default:
            return '';
    }
}

function getWorkflowHint(booking) {
    const role = window.medicalConfig?.userRole || 'staff';

    if (booking.status === 'awaiting_eligibility' || booking.status === 'pending') {
        if (!booking.pre_screening) {
            return 'Can co khai bao y te truoc khi bac si duyet online.';
        }
        return role === 'doctor'
            ? 'Bac si duyet online ngay tai dashboard medical de quyet dinh duoc tiem, tam hoan, hoac khong du dieu kien.'
            : 'Dang cho bac si duyet online tai dashboard medical.';
    }

    if (booking.status === 'deposit_pending') {
        return booking.deposit_deadline_message || 'Da duoc bac si duyet online, dang cho nhan vien xac nhan dat coc.';
    }

    if (booking.status === 'confirmed') {
        return role === 'staff'
            ? 'Da duyet online va da coc. Co the check-in khi benh nhan den.'
            : 'Staff se thuc hien check-in tai quay.';
    }

    if (booking.status === 'checked_in') {
        return role === 'doctor'
            ? 'Benh nhan da check-in. Bac si co the kham sang loc tai quay.'
            : 'Dang cho bac si kham sang loc.';
    }

    if (booking.status === 'ready_to_inject') {
        return 'Bac si da duyet sang loc tai quay. Staff co the thuc hien tiem.';
    }

    if (booking.status === 'in_observation') {
        return 'Da tiem xong, dang theo doi sau tiem.';
    }

    if (booking.status === 'delayed') {
        return 'Ca nay dang tam hoan va can doi lich neu tiep tuc.';
    }

    if (booking.status === 'ineligible') {
        return 'Bac si da ket luan khong du dieu kien tiem cho lan dang ky nay.';
    }

    return '';
}

function makeActionButton(label, handler, style) {
    const button = document.createElement('button');
    button.className = 'action-btn';
    button.type = 'button';
    if (style) {
        button.style.cssText = style;
    }
    button.textContent = label;
    button.addEventListener('click', handler);
    return button;
}

function makeActionMessage(message, style) {
    const span = document.createElement('span');
    span.style.cssText = style || 'color:#64748b; font-size:13px; display:inline-block;';
    span.textContent = message;
    return span;
}

function getActionControls(booking) {
    const role = window.medicalConfig?.userRole || 'staff';
    const bookingId = String(booking.id);
    const fullName = booking.full_name || '';

    if (booking.status === 'awaiting_eligibility' || booking.status === 'pending') {
        if (!booking.pre_screening) {
            return [makeActionMessage('Can khai bao y te truoc khi duyet online')];
        }
        if (role === 'doctor') {
            return [makeActionButton('Duyet online', () => openDoctorReviewForm(bookingId, fullName))];
        }
        return [makeActionMessage('Dang cho bac si duyet online tai dashboard medical')];
    }

    if (booking.status === 'deposit_pending') {
        if (role === 'staff') {
            return [makeActionButton('Xac nhan coc', () => confirmDeposit(bookingId))];
        }
        return [makeActionMessage(booking.deposit_deadline_message || 'Dang cho nhan vien xac nhan dat coc')];
    }

    if (booking.status === 'confirmed') {
        if (role === 'staff') {
            return [makeActionButton('Check-in', () => checkIn(bookingId))];
        }
        return [makeActionMessage('Staff se check-in tai quay')];
    }

    if (booking.status === 'checked_in') {
        if (role === 'doctor') {
            return [makeActionButton('Nhap ket qua sang loc', () => openScreeningForm(bookingId, fullName))];
        }
        return [makeActionMessage('Dang cho bac si kham sang loc', 'color:#b45309; font-size:13px; font-weight:600;')];
    }

    if (booking.status === 'ready_to_inject') {
        if (role === 'staff') {
            return [makeActionButton('Tiem chung', () => openInjectionForm(bookingId, fullName, booking.dose_number))];
        }
        return [makeActionMessage('Staff se xu ly buoc tiem')];
    }

    if (booking.status === 'in_observation') {
        if (role === 'staff') {
            return [makeActionButton('Hoan tat theo doi', () => openMonitoringForm(bookingId, fullName))];
        }
        return [makeActionMessage('Dang theo doi sau tiem')];
    }

    if (booking.status === 'delayed') {
        return [makeActionMessage('Can doi lich o portal booking')];
    }

    if (booking.status === 'ineligible') {
        return [makeActionMessage('Khong con du dieu kien tiem trong lan dang ky nay')];
    }

    if (booking.status === 'completed') {
        return [makeActionMessage('Ca tiem da hoan thanh')];
    }

    if (booking.status === 'cancelled') {
        return [makeActionMessage('Booking da bi huy')];
    }

    return [];
}

function getPreScreeningSnippet(booking) {
    if (!booking.pre_screening) {
        return 'Chua co khai bao truoc tiem.';
    }

    const positives = MEDICAL_DECLARATION_FIELDS
        .filter((field) => booking.pre_screening[field.boolKey])
        .map((field) => field.label);

    if (!positives.length) {
        return 'Da khai bao day du, khong co yeu to nguy co duoc danh dau.';
    }

    return `Da danh dau: ${positives.join('; ')}.`;
}

function setupPatientSearch() {
    const searchInput = document.getElementById('patient-search');
    const clearButton = document.getElementById('patient-search-clear');
    if (!searchInput) {
        return;
    }

    patientSearchTerm = searchInput.value;
    searchInput.addEventListener('input', () => {
        patientSearchTerm = searchInput.value;
        currentPatientPage = 1;
        renderPatientList();
    });

    if (clearButton) {
        clearButton.addEventListener('click', () => {
            searchInput.value = '';
            patientSearchTerm = '';
            currentPatientPage = 1;
            renderPatientList();
            searchInput.focus();
        });
    }
}

function setupPatientSort() {
    const sortButtons = Array.from(document.querySelectorAll('.patient-sort'));
    if (!sortButtons.length) {
        return;
    }

    const updateActiveSort = () => {
        sortButtons.forEach((button) => {
            const isActive = button.dataset.sortKey === currentPatientSort.key;
            button.classList.toggle('is-active', isActive);
            const arrow = isActive ? (currentPatientSort.direction === 'asc' ? ' â†‘' : ' â†“') : '';
            const baseLabel = button.dataset.baseLabel || button.textContent.replace(/\s[â†‘â†“]$/, '');
            button.dataset.baseLabel = baseLabel;
            button.textContent = `${baseLabel}${arrow}`;
        });
    };

    sortButtons.forEach((button) => {
        button.dataset.baseLabel = button.textContent.trim();
        button.addEventListener('click', () => {
            const key = button.dataset.sortKey;
            if (!key) {
                return;
            }

            if (currentPatientSort.key === key) {
                currentPatientSort.direction = currentPatientSort.direction === 'asc' ? 'desc' : 'asc';
            } else {
                currentPatientSort = { key, direction: 'asc' };
            }
            currentPatientPage = 1;
            updateActiveSort();
            renderPatientList();
        });
    });

    updateActiveSort();
}

function getFilteredBookings() {
    const keyword = normalizeSearchText(patientSearchTerm);
    const filtered = !keyword
        ? [...todayBookings]
        : todayBookings.filter((booking) => {
            const name = normalizeSearchText(booking.full_name);
            const phone = normalizeSearchText(booking.phone);
            const vaccineName = normalizeSearchText(booking.vaccine_name);
            return name.includes(keyword) || phone.includes(keyword) || vaccineName.includes(keyword);
        });

    return filtered.sort((left, right) => compareBookings(left, right, currentPatientSort));
}

function compareBookings(left, right, sortConfig) {
    const direction = sortConfig.direction === 'desc' ? -1 : 1;

    const getValue = (booking, key) => {
        switch (key) {
            case 'full_name':
            case 'phone':
            case 'vaccine_name':
            case 'status':
                return normalizeSearchText(booking[key]);
            case 'vaccine_date':
                return booking.vaccine_date || '';
            case 'deposit_state':
                return getDepositState(booking);
            default:
                return booking[key] ?? '';
        }
    };

    const leftValue = getValue(left, sortConfig.key);
    const rightValue = getValue(right, sortConfig.key);

    if (leftValue < rightValue) {
        return -1 * direction;
    }
    if (leftValue > rightValue) {
        return 1 * direction;
    }
    return (left.id - right.id) * direction;
}

function updatePatientSearchCount(filteredCount) {
    const countEl = document.getElementById('patient-search-count');
    if (!countEl) {
        return;
    }

    if (todayBookings.length === 0) {
        countEl.textContent = 'Khong co booking can xu ly.';
        return;
    }

    if (patientSearchTerm.trim()) {
        countEl.textContent = `Tim thay ${filteredCount}/${todayBookings.length} booking.`;
        return;
    }

    countEl.textContent = `${todayBookings.length} booking dang can xu ly.`;
}

function getPatientPageCount(totalCount) {
    return Math.max(1, Math.ceil(totalCount / PATIENTS_PER_PAGE));
}

function normalizeCurrentPatientPage(totalCount) {
    const totalPages = getPatientPageCount(totalCount);
    currentPatientPage = Math.min(Math.max(currentPatientPage, 1), totalPages);
    return totalPages;
}

function renderPatientPagination(totalCount, visibleCount, startIndex) {
    const paginationEl = document.getElementById('patient-pagination');
    if (!paginationEl) {
        return;
    }

    paginationEl.textContent = '';
    if (todayBookings.length === 0) {
        paginationEl.hidden = true;
        return;
    }

    const totalPages = getPatientPageCount(totalCount);
    paginationEl.hidden = false;

    const infoEl = document.createElement('span');
    infoEl.className = 'patient-pagination-info';
    if (totalCount === 0) {
        infoEl.textContent = 'Khong co benh nhan phu hop Â· 0 benh nhan dang loc';
    } else {
        const firstVisible = startIndex + 1;
        const lastVisible = startIndex + visibleCount;
        infoEl.textContent = `Trang ${currentPatientPage}/${totalPages} Â· Hien thi ${firstVisible}-${lastVisible}/${totalCount} benh nhan`;
    }

    const actionsEl = document.createElement('div');
    actionsEl.className = 'patient-pagination-actions';

    const prevButton = document.createElement('button');
    prevButton.type = 'button';
    prevButton.textContent = 'Truoc';
    prevButton.disabled = currentPatientPage <= 1 || totalCount === 0;
    prevButton.addEventListener('click', () => {
        currentPatientPage -= 1;
        renderPatientList();
    });

    const nextButton = document.createElement('button');
    nextButton.type = 'button';
    nextButton.textContent = 'Sau';
    nextButton.disabled = currentPatientPage >= totalPages || totalCount === 0;
    nextButton.addEventListener('click', () => {
        currentPatientPage += 1;
        renderPatientList();
    });

    actionsEl.appendChild(prevButton);
    actionsEl.appendChild(nextButton);
    paginationEl.appendChild(infoEl);
    paginationEl.appendChild(actionsEl);
}

function appendEmptyPatientState(listEl, message) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 8;
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = message;
    cell.appendChild(empty);
    row.appendChild(cell);
    listEl.appendChild(row);
}

function renderPatientRow(booking) {
    const row = document.createElement('tr');

    const patientCell = document.createElement('td');
    const patientWrap = document.createElement('div');
    patientWrap.className = 'patient-row-name';
    const patientName = document.createElement('strong');
    patientName.textContent = booking.full_name || '';
    const patientMeta = document.createElement('span');
    patientMeta.className = 'patient-row-subtext';
    patientMeta.textContent = booking.email || `Mui ${booking.dose_number || '--'}`;
    patientWrap.appendChild(patientName);
    patientWrap.appendChild(patientMeta);
    patientCell.appendChild(patientWrap);

    const contactCell = document.createElement('td');
    const contactWrap = document.createElement('div');
    contactWrap.className = 'patient-row-name';
    const phoneLine = document.createElement('strong');
    phoneLine.textContent = booking.phone || '--';
    const sourceLine = document.createElement('span');
    sourceLine.className = 'patient-row-subtext';
    sourceLine.textContent = booking.booking_source === 'walkin' ? 'Walk-in' : 'Dat lich online';
    contactWrap.appendChild(phoneLine);
    contactWrap.appendChild(sourceLine);
    contactCell.appendChild(contactWrap);

    const vaccineCell = document.createElement('td');
    const vaccineWrap = document.createElement('div');
    vaccineWrap.className = 'patient-row-name';
    const vaccineName = document.createElement('strong');
    vaccineName.textContent = booking.vaccine_name || '--';
    const vaccineDose = document.createElement('span');
    vaccineDose.className = 'patient-row-subtext';
    vaccineDose.textContent = `Mui ${booking.dose_number || '--'}`;
    vaccineWrap.appendChild(vaccineName);
    vaccineWrap.appendChild(vaccineDose);
    vaccineCell.appendChild(vaccineWrap);

    const dateCell = document.createElement('td');
    const dateWrap = document.createElement('div');
    dateWrap.className = 'patient-row-name';
    const dateStrong = document.createElement('strong');
    dateStrong.textContent = formatDate(booking.vaccine_date);
    const dateHint = document.createElement('span');
    dateHint.className = 'patient-row-subtext';
    dateHint.textContent = booking.note || getWorkflowHint(booking) || '--';
    dateWrap.appendChild(dateStrong);
    dateWrap.appendChild(dateHint);
    dateCell.appendChild(dateWrap);

    const statusCell = document.createElement('td');
    const statusBadge = document.createElement('span');
    statusBadge.className = `badge ${getStatusClass(booking.status)}`;
    statusBadge.textContent = getStatusLabel(booking.status);
    statusCell.appendChild(statusBadge);

    const depositCell = document.createElement('td');
    const depositBadge = document.createElement('span');
    depositBadge.className = `badge ${getDepositClass(booking)}`;
    depositBadge.textContent = getDepositLabel(booking);
    depositCell.appendChild(depositBadge);
    if (booking.deposit_deadline_message) {
        const depositNote = document.createElement('div');
        depositNote.className = 'patient-row-subtext';
        depositNote.style.marginTop = '6px';
        depositNote.textContent = booking.deposit_deadline_message;
        depositCell.appendChild(depositNote);
    }

    const declarationCell = document.createElement('td');
    const declarationText = document.createElement('div');
    declarationText.className = 'patient-row-subtext';
    declarationText.textContent = getPreScreeningSnippet(booking);
    declarationCell.appendChild(declarationText);
    if (booking.pre_screening) {
        const tag = document.createElement('span');
        tag.className = 'patient-note-chip';
        tag.textContent = 'Da khai bao';
        tag.style.marginTop = '8px';
        declarationCell.appendChild(tag);
    }

    const actionsCell = document.createElement('td');
    const actionsWrap = document.createElement('div');
    actionsWrap.className = 'action-buttons';
    actionsWrap.style.display = 'flex';
    actionsWrap.style.flexWrap = 'wrap';
    getActionControls(booking).forEach((control) => actionsWrap.appendChild(control));
    actionsCell.appendChild(actionsWrap);

    [
        patientCell,
        contactCell,
        vaccineCell,
        dateCell,
        statusCell,
        depositCell,
        declarationCell,
        actionsCell,
    ].forEach((cell) => row.appendChild(cell));

    return row;
}

function renderPatientList() {
    const listEl = document.getElementById('patient-list');
    if (!listEl) {
        return;
    }

    listEl.innerHTML = '';
    const filteredBookings = getFilteredBookings();
    updatePatientSearchCount(filteredBookings.length);
    normalizeCurrentPatientPage(filteredBookings.length);

    if (todayBookings.length === 0) {
        renderPatientPagination(0, 0, 0);
        appendEmptyPatientState(listEl, 'Chua co booking nao can dashboard medical xu ly.');
        return;
    }

    if (filteredBookings.length === 0) {
        renderPatientPagination(0, 0, 0);
        appendEmptyPatientState(listEl, 'Khong tim thay benh nhan theo ten, so dien thoai hoac vac xin.');
        return;
    }

    const startIndex = (currentPatientPage - 1) * PATIENTS_PER_PAGE;
    const pageBookings = filteredBookings.slice(startIndex, startIndex + PATIENTS_PER_PAGE);
    renderPatientPagination(filteredBookings.length, pageBookings.length, startIndex);

    pageBookings.forEach((booking) => {
        listEl.appendChild(renderPatientRow(booking));
    });
}

async function loadTodayBookings() {
    try {
        const response = await fetch('/api/medical/today/', {
            credentials: 'same-origin',
        });
        const payload = await response.json();
        const data = Array.isArray(payload) ? payload : [];

        todayBookings = data;
        todayBookingsById = {};

        let waitingInjectionCount = 0;
        let completedCount = 0;

        data.forEach((booking) => {
            todayBookingsById[String(booking.id)] = booking;

            if (booking.status === 'ready_to_inject') {
                waitingInjectionCount += 1;
            }
            if (booking.status === 'completed') {
                completedCount += 1;
            }
        });

        document.getElementById('stat-total').innerText = data.length;
        document.getElementById('stat-waiting').innerText = waitingInjectionCount;
        document.getElementById('stat-completed').innerText = completedCount;
        renderPatientList();
    } catch (error) {
        console.error('Loi tai danh sach booking:', error);
    }
}

function getWalkinVaccineElements() {
    return {
        input: document.getElementById('walkin-vaccine-combobox'),
        toggle: document.getElementById('walkin-vaccine-toggle'),
        list: document.getElementById('walkin-vaccine-options'),
        select: document.getElementById('walkin-vaccine'),
        count: document.getElementById('walkin-vaccine-count'),
    };
}

function setupWalkinVaccineSearch() {
    const elements = getWalkinVaccineElements();
    if (!elements.input || !elements.list || !elements.select) {
        return;
    }

    walkinVaccineOptions = Array.from(elements.select.options)
        .filter((option) => option.value)
        .map((option, index) => {
            const label = option.textContent.trim();
            return {
                id: `walkin-vaccine-option-${index}`,
                value: option.value,
                label,
                detail: label.startsWith(option.value) ? label.slice(option.value.length).trim() : label,
                normalizedText: normalizeSearchText(`${option.value} ${option.textContent}`),
            };
        });

    elements.select.value = '';
    selectedWalkinVaccineValue = '';
    renderWalkinVaccineOptions();

    elements.input.addEventListener('focus', () => openWalkinVaccineDropdown());
    elements.input.addEventListener('click', () => openWalkinVaccineDropdown());
    elements.input.addEventListener('input', () => {
        selectedWalkinVaccineValue = '';
        elements.select.value = '';
        openWalkinVaccineDropdown();
    });
    elements.input.addEventListener('keydown', handleWalkinVaccineKeydown);

    if (elements.toggle) {
        elements.toggle.addEventListener('click', () => {
            if (elements.input.getAttribute('aria-expanded') === 'true') {
                closeWalkinVaccineDropdown();
            } else {
                elements.input.focus();
                openWalkinVaccineDropdown();
            }
        });
    }

    document.addEventListener('click', (event) => {
        const combobox = document.querySelector('[data-vaccine-combobox]');
        if (combobox && !combobox.contains(event.target)) {
            closeWalkinVaccineDropdown();
        }
    });
}

function renderWalkinVaccineOptions(searchTerm) {
    const elements = getWalkinVaccineElements();
    if (!elements.list) {
        return;
    }

    const keyword = normalizeSearchText(searchTerm ?? elements.input?.value ?? '');
    filteredWalkinVaccineOptions = walkinVaccineOptions.filter((option) => (
        !keyword || option.normalizedText.includes(keyword)
    ));

    elements.list.innerHTML = '';

    if (filteredWalkinVaccineOptions.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'vaccine-combobox-empty';
        empty.textContent = 'Khong tim thay vac xin phu hop.';
        elements.list.appendChild(empty);
        updateWalkinVaccineCount(0, Boolean(keyword));
        setWalkinVaccineHighlight(-1);
        return;
    }

    filteredWalkinVaccineOptions.forEach((option, index) => {
        const item = document.createElement('div');
        item.className = 'vaccine-combobox-option';
        item.id = option.id;
        item.setAttribute('role', 'option');
        item.setAttribute('aria-selected', 'false');
        item.tabIndex = -1;
        item.innerHTML = `
            <strong>${escapeHtml(option.value)}</strong>
            ${option.detail ? `<span>${escapeHtml(option.detail)}</span>` : ''}
        `;
        item.addEventListener('mousedown', (event) => {
            event.preventDefault();
            selectWalkinVaccine(option);
        });
        item.addEventListener('mouseenter', () => setWalkinVaccineHighlight(index));
        elements.list.appendChild(item);
    });

    updateWalkinVaccineCount(filteredWalkinVaccineOptions.length, Boolean(keyword));
    const isExpanded = elements.input?.getAttribute('aria-expanded') === 'true';
    setWalkinVaccineHighlight(isExpanded ? 0 : -1);
}

function updateWalkinVaccineCount(visibleCount, hasKeyword) {
    const { count } = getWalkinVaccineElements();
    if (!count) {
        return;
    }

    if (walkinVaccineOptions.length === 0) {
        count.textContent = 'Chua co vac xin de chon.';
    } else if (visibleCount === 0) {
        count.textContent = 'Khong tim thay vac xin phu hop.';
    } else if (selectedWalkinVaccineValue) {
        count.textContent = 'Da chon vac xin tu danh sach.';
    } else if (hasKeyword) {
        count.textContent = `Tim thay ${visibleCount} loai vac xin.`;
    } else {
        count.textContent = `Co ${visibleCount} loai vac xin co the chon.`;
    }
}

function setWalkinVaccineExpanded(isExpanded) {
    const elements = getWalkinVaccineElements();
    if (!elements.input || !elements.list) {
        return;
    }

    elements.input.setAttribute('aria-expanded', String(isExpanded));
    elements.list.classList.toggle('is-open', isExpanded);
    if (!isExpanded) {
        setWalkinVaccineHighlight(-1);
    }
}

function openWalkinVaccineDropdown() {
    const { input } = getWalkinVaccineElements();
    setWalkinVaccineExpanded(true);
    renderWalkinVaccineOptions(input ? input.value : '');
}

function closeWalkinVaccineDropdown() {
    setWalkinVaccineExpanded(false);
}

function setWalkinVaccineHighlight(index) {
    const elements = getWalkinVaccineElements();
    if (!elements.input || !elements.list) {
        return;
    }

    highlightedWalkinVaccineIndex = index;
    Array.from(elements.list.querySelectorAll('.vaccine-combobox-option')).forEach((item, itemIndex) => {
        const isActive = itemIndex === index;
        item.classList.toggle('is-active', isActive);
        item.setAttribute('aria-selected', String(isActive));
        if (isActive) {
            elements.input.setAttribute('aria-activedescendant', item.id);
            item.scrollIntoView({ block: 'nearest' });
        }
    });

    if (index < 0) {
        elements.input.removeAttribute('aria-activedescendant');
    }
}

function handleWalkinVaccineKeydown(event) {
    const { input } = getWalkinVaccineElements();
    if (!input) {
        return;
    }

    const isExpanded = input.getAttribute('aria-expanded') === 'true';

    if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (!isExpanded) {
            openWalkinVaccineDropdown();
            return;
        }
        const nextIndex = Math.min(highlightedWalkinVaccineIndex + 1, filteredWalkinVaccineOptions.length - 1);
        setWalkinVaccineHighlight(nextIndex);
    } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (!isExpanded) {
            openWalkinVaccineDropdown();
            return;
        }
        const previousIndex = Math.max(highlightedWalkinVaccineIndex - 1, 0);
        setWalkinVaccineHighlight(previousIndex);
    } else if (event.key === 'Enter' && isExpanded) {
        event.preventDefault();
        const option = filteredWalkinVaccineOptions[highlightedWalkinVaccineIndex];
        if (option) {
            selectWalkinVaccine(option);
        }
    } else if (event.key === 'Escape') {
        closeWalkinVaccineDropdown();
    }
}

function selectWalkinVaccine(option) {
    const elements = getWalkinVaccineElements();
    if (!elements.input || !elements.select) {
        return;
    }

    selectedWalkinVaccineValue = option.value;
    elements.input.value = option.value;
    elements.select.value = option.value;
    updateWalkinVaccineCount(1, true);
    closeWalkinVaccineDropdown();
}

function resetWalkinVaccineSearch() {
    const elements = getWalkinVaccineElements();
    selectedWalkinVaccineValue = '';
    highlightedWalkinVaccineIndex = -1;

    if (elements.input) {
        elements.input.value = '';
        elements.input.removeAttribute('aria-activedescendant');
        elements.input.setAttribute('aria-expanded', 'false');
    }
    if (elements.select) {
        elements.select.value = '';
    }

    renderWalkinVaccineOptions('');
    closeWalkinVaccineDropdown();
}

function resetActionPanel() {
    const defaultBox = document.getElementById('form-default');
    const declarationBox = document.getElementById('pre-screening-box');
    const reviewBox = document.getElementById('online-review-box');
    const screeningForm = document.getElementById('form-screening');
    const doctorReviewForm = document.getElementById('form-doctor-review');
    const injectionForm = document.getElementById('form-injection');
    const monitoringForm = document.getElementById('form-monitoring');
    const walkinForm = document.getElementById('form-walkin');
    const subtitle = document.getElementById('action-subtitle');

    defaultBox.style.display = 'block';
    declarationBox.style.display = 'none';
    if (reviewBox) {
        reviewBox.style.display = 'none';
    }
    screeningForm.style.display = 'none';
    if (doctorReviewForm) {
        doctorReviewForm.style.display = 'none';
    }
    injectionForm.style.display = 'none';
    monitoringForm.style.display = 'none';
    if (walkinForm) {
        walkinForm.style.display = 'none';
    }
    subtitle.innerText = 'Vui long chon thao tac tu danh sach booking.';

    screeningForm.reset();
    doctorReviewForm?.reset();
    injectionForm.reset();
    monitoringForm.reset();
    if (walkinForm) {
        walkinForm.reset();
        resetWalkinVaccineSearch();
    }
}

function hideDefault() {
    document.getElementById('form-default').style.display = 'none';
}

function openDoctorReviewForm(bookingId, name) {
    resetActionPanel();
    hideDefault();
    renderPreScreeningBox(bookingId);
    renderOnlineReviewBox(bookingId);

    const form = document.getElementById('form-doctor-review');
    const booking = todayBookingsById[String(bookingId)];
    if (!form || !booking) {
        return;
    }

    form.style.display = 'grid';
    document.getElementById('doctor-review-booking-id').value = bookingId;
    document.getElementById('doctor-review-decision').value = booking.online_review?.decision || 'eligible';
    document.getElementById('doctor-review-note').value = booking.online_review?.doctor_note || '';
    document.getElementById('action-subtitle').innerText = `Duyet online cho: ${name}`;
}

async function submitDoctorReview(event) {
    event.preventDefault();
    const bookingId = document.getElementById('doctor-review-booking-id').value;
    if (!bookingId) {
        return;
    }

    try {
        const response = await fetch(`/booking/${bookingId}/doctor-review/`, {
            method: 'PATCH',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify({
                decision: document.getElementById('doctor-review-decision').value,
                doctor_note: document.getElementById('doctor-review-note').value.trim(),
            }),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            window.alert(data.detail || 'Khong the luu ket luan duyet online luc nay.');
            return;
        }

        window.alert('Da luu ket luan duyet online.');
        resetActionPanel();
        await loadTodayBookings();
    } catch (error) {
        console.error(error);
        window.alert('Co loi ket noi khi luu ket luan duyet online.');
    }
}

async function confirmDeposit(bookingId) {
    if (!window.confirm('Xac nhan da nhan coc cho booking nay?')) {
        return;
    }

    try {
        const response = await fetch(`/booking/${bookingId}/deposit/`, {
            method: 'PATCH',
            headers,
            credentials: 'same-origin',
            body: JSON.stringify({ deposit_note: 'Xac nhan coc tai dashboard y khoa.' }),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            window.alert(data.detail || 'Khong the xac nhan dat coc luc nay.');
            return;
        }

        window.alert('Da xac nhan dat coc thanh cong.');
        await loadTodayBookings();
    } catch (error) {
        console.error(error);
        window.alert('Co loi ket noi khi xac nhan dat coc.');
    }
}

async function checkIn(bookingId) {
    if (!window.confirm('Xac nhan check-in cho benh nhan nay?')) {
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
            window.alert(data.detail || 'Khong the check-in luc nay.');
            return;
        }

        resetActionPanel();
        await loadTodayBookings();
        window.alert('Check-in thanh cong.');
    } catch (error) {
        console.error(error);
    }
}

function openScreeningForm(bookingId, name) {
    resetActionPanel();
    hideDefault();
    renderPreScreeningBox(bookingId);
    renderOnlineReviewBox(bookingId);

    const form = document.getElementById('form-screening');
    form.style.display = 'grid';
    form.reset();

    document.getElementById('screen-booking-id').value = bookingId;
    document.getElementById('action-subtitle').innerText = `Kham sang loc cho: ${name}`;
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
            const errorMessage = await getResponseErrorMessage(response, 'Khong the luu ket qua kham luc nay.');
            window.alert(`Co loi xay ra: ${errorMessage}`);
            console.error(errorMessage);
            return;
        }

        window.alert('Luu ket qua kham thanh cong.');
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
        batchInput.placeholder = 'Tuy chon, he thong se tu dien tu kho neu co.';
    }

    document.getElementById('inject-booking-id').value = bookingId;
    document.getElementById('inject-dose').value = dose;
    document.getElementById('action-subtitle').innerText = `Thong tin tiem chung cho: ${name}`;
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
            const errorMessage = await getResponseErrorMessage(response, 'Khong the xac nhan tiem luc nay.');
            window.alert(`Co loi xay ra: ${errorMessage}`);
            console.error(errorMessage);
            return;
        }

        window.alert('Xac nhan da tiem thanh cong.');
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
    document.getElementById('action-subtitle').innerText = `Theo doi phan ung cho: ${name}`;
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
            window.alert(`Co loi: ${JSON.stringify(errJson)}`);
            return;
        }

        window.alert('Luu trang thai theo doi thanh cong.');
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
            el.textContent = 'Da du 30 phut, co the hoan tat';
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
    document.getElementById('action-subtitle').innerText = 'Tiep nhan khach vang lai';
    const dateInput = document.getElementById('walkin-date');
    if (dateInput) {
        dateInput.valueAsDate = new Date();
    }
    renderWalkinVaccineOptions();
}

async function submitWalkin(event) {
    event.preventDefault();
    const vaccineSelect = document.getElementById('walkin-vaccine');
    const vaccineInput = document.getElementById('walkin-vaccine-combobox');
    const selectedVaccine = vaccineSelect ? vaccineSelect.selectedOptions[0] : null;
    if (
        !vaccineSelect
        || !vaccineSelect.value
        || !selectedVaccine
        || !selectedVaccine.value
        || selectedWalkinVaccineValue !== vaccineSelect.value
        || (vaccineInput && vaccineInput.value !== selectedWalkinVaccineValue)
    ) {
        window.alert('Vui long chon vac xin tu danh sach.');
        if (vaccineInput) {
            vaccineInput.focus();
            openWalkinVaccineDropdown();
        }
        return;
    }

    const payload = {
        full_name: document.getElementById('walkin-name').value.trim(),
        phone: document.getElementById('walkin-phone').value.trim(),
        email: document.getElementById('walkin-email').value.trim(),
        vaccine_name: vaccineSelect.value,
        vaccine_date: document.getElementById('walkin-date').value,
        dose_number: parseInt(document.getElementById('walkin-dose').value, 10),
        pre_screening: collectMedicalDeclarationPayload('walkin'),
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
            window.alert(`Loi: ${err.detail || JSON.stringify(err)}`);
            return;
        }

        const booking = await response.json();
        window.alert(`Tiep nhan thanh cong! Booking #${booking.id} - ${booking.full_name} da vao hang doi.`);
        resetActionPanel();
        await loadTodayBookings();
    } catch (err) {
        console.error(err);
        window.alert('Co loi xay ra khi tiep nhan walk-in.');
    }
}







