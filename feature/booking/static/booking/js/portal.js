let reschedulingBookingId = null;
let allPortalBookings = [];
let declarationBookingId = null;

const DECLARATION_FIELDS = [
    {
        checkboxId: "decl-severe-allergy",
        detailId: "decl-severe-allergy-details",
        payloadKey: "has_severe_allergy",
        detailKey: "severe_allergy_details",
    },
    {
        checkboxId: "decl-current-health-issue",
        detailId: "decl-current-health-issue-details",
        payloadKey: "has_current_health_issue",
        detailKey: "current_health_issue_details",
    },
    {
        checkboxId: "decl-recent-vaccination",
        detailId: "decl-recent-vaccination-details",
        payloadKey: "had_recent_vaccination",
        detailKey: "recent_vaccination_details",
    },
    {
        checkboxId: "decl-immunosuppressive-medication",
        detailId: "decl-immunosuppressive-medication-details",
        payloadKey: "uses_immunosuppressive_medication",
        detailKey: "immunosuppressive_medication_details",
    },
    {
        checkboxId: "decl-pregnancy-consideration",
        detailId: "decl-pregnancy-consideration-details",
        payloadKey: "has_pregnancy_or_breastfeeding_consideration",
        detailKey: "pregnancy_or_breastfeeding_details",
    },
];

(function () {
    const config = window.bookingPortalConfig || {};
    const initialBookingsNode = document.getElementById("initial-bookings-data");
    let bookings = [];
    let editingBookingId = null;

    if (initialBookingsNode?.textContent) {
        try {
            bookings = JSON.parse(initialBookingsNode.textContent);
        } catch (error) {
            bookings = [];
        }
    }

    const form = document.getElementById("booking-form");
    const tableBody = document.getElementById("booking-table-body");
    const emptyState = document.getElementById("booking-empty");
    const alertBox = document.getElementById("form-alert");
    const reminderBox = document.getElementById("portal-reminder");
    const cancelEditButton = document.getElementById("cancel-edit-btn");
    const fullNameInput = document.getElementById("full-name");
    const phoneInput = document.getElementById("phone");
    const emailInput = document.getElementById("email");
    const vaccineNameInput = document.getElementById("vaccine-name");
    const vaccineDateInput = document.getElementById("vaccine-date");
    const doseNumberInput = document.getElementById("dose-number");
    const statusInput = document.getElementById("status");
    const noteInput = document.getElementById("note");
    const isCitizenUser = config.userRole === "citizen";

    const defaultValues = {
        fullName: fullNameInput?.value || "",
        phone: phoneInput?.value || "",
        email: emailInput?.value || "",
    };

    function getCSRFToken() {
        const name = "csrftoken=";
        const cookies = document.cookie ? document.cookie.split(";") : [];
        for (const cookie of cookies) {
            const trimmed = cookie.trim();
            if (trimmed.startsWith(name)) {
                return decodeURIComponent(trimmed.slice(name.length));
            }
        }
        return "";
    }

    function formatDate(dateString) {
        if (!dateString) {
            return "";
        }
        return new Date(dateString + "T00:00:00").toLocaleDateString("vi-VN");
    }

    function formatMoney(value) {
        const amount = Number(value || 0);
        return `${amount.toLocaleString("vi-VN")} d`;
    }

    function showAlert(message, isError) {
        alertBox.hidden = false;
        alertBox.textContent = message;
        alertBox.classList.toggle("is-error", Boolean(isError));
    }

    function clearAlert() {
        alertBox.hidden = true;
        alertBox.textContent = "";
        alertBox.classList.remove("is-error");
    }

    function setEditLockedFields(isEditing) {
        fullNameInput.readOnly = isCitizenUser;
        emailInput.readOnly = isCitizenUser;

        if (!isCitizenUser) {
            return;
        }

        vaccineNameInput.disabled = false;
        doseNumberInput.readOnly = false;
        statusInput.disabled = isEditing;
    }

    function getSelectedVaccineOption() {
        return vaccineNameInput?.selectedOptions?.[0] || null;
    }

    function updatePricingSummary() {
        const selectedOption = getSelectedVaccineOption();
        const totalAmount = Number(selectedOption?.dataset.price || 0);
        const depositAmount = totalAmount * 0.2;
        const priceEl = document.getElementById("selected-vaccine-price");
        const depositEl = document.getElementById("selected-deposit-amount");
        const deadlineEl = document.getElementById("selected-deposit-deadline");

        if (priceEl) {
            priceEl.textContent = formatMoney(totalAmount);
        }
        if (depositEl) {
            depositEl.textContent = formatMoney(depositAmount);
        }
        if (deadlineEl) {
            if (!vaccineDateInput.value) {
                deadlineEl.textContent = "--/--/----";
            } else {
                const date = new Date(vaccineDateInput.value + "T00:00:00");
                date.setDate(date.getDate() - 2);
                deadlineEl.textContent = date.toLocaleDateString("vi-VN");
            }
        }
    }

    function collectFormPayload() {
        const fullPayload = {
            full_name: fullNameInput.value.trim(),
            phone: phoneInput.value.trim(),
            email: emailInput.value.trim(),
            vaccine_name: vaccineNameInput.value,
            vaccine_date: vaccineDateInput.value,
            dose_number: parseInt(doseNumberInput.value, 10),
            status: statusInput.value,
            note: noteInput.value.trim(),
        };

        if (editingBookingId && isCitizenUser) {
            return {
                phone: fullPayload.phone,
                vaccine_name: fullPayload.vaccine_name,
                vaccine_date: fullPayload.vaccine_date,
                dose_number: fullPayload.dose_number,
                note: fullPayload.note,
            };
        }

        return fullPayload;
    }

    function resetForm() {
        editingBookingId = null;
        form.reset();
        document.getElementById("booking-id").value = "";
        document.getElementById("form-heading").textContent = "Tao booking moi";
        document.getElementById("form-subtitle").textContent =
            "Thong tin se duoc dua vao luong khai bao, duyet online boi bac si, va dat coc 20%.";
        document.getElementById("submit-btn").textContent = "Tao booking";
        cancelEditButton.hidden = true;
        clearAlert();

        fullNameInput.value = defaultValues.fullName;
        phoneInput.value = defaultValues.phone;
        emailInput.value = defaultValues.email;
        doseNumberInput.value = "1";
        statusInput.value = "awaiting_eligibility";
        vaccineDateInput.value = "";
        setEditLockedFields(false);
        updatePricingSummary();
    }

    function startEdit(booking) {
        editingBookingId = booking.id;
        document.getElementById("booking-id").value = String(booking.id);
        fullNameInput.value = booking.full_name || "";
        phoneInput.value = booking.phone || "";
        emailInput.value = booking.email || "";
        vaccineNameInput.value = booking.vaccine_name || config.vaccineOptions[0];
        vaccineDateInput.value = booking.vaccine_date || "";
        doseNumberInput.value = booking.dose_number || 1;
        statusInput.value = booking.status || "awaiting_eligibility";
        noteInput.value = booking.note || "";
        document.getElementById("form-heading").textContent = "Cap nhat booking";
        document.getElementById("form-subtitle").textContent =
            "Ban dang chinh sua mot booking da tao.";
        document.getElementById("submit-btn").textContent = "Luu thay doi";
        cancelEditButton.hidden = false;
        clearAlert();
        setEditLockedFields(true);
        updatePricingSummary();
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    function updateStats() {
        const counter = bookings.reduce(
            (accumulator, booking) => {
                accumulator.total += 1;
                accumulator.upcoming +=
                    booking.status !== "cancelled"
                    && booking.status !== "ineligible"
                    && booking.vaccine_date >= config.today
                        ? 1
                        : 0;
                if (booking.status === "awaiting_eligibility" || booking.status === "pending") {
                    accumulator.awaiting += 1;
                }
                if (booking.status === "deposit_pending") {
                    accumulator.deposit += 1;
                }
                if (booking.status === "confirmed") {
                    accumulator.confirmed += 1;
                }
                return accumulator;
            },
            { total: 0, awaiting: 0, deposit: 0, confirmed: 0, upcoming: 0 }
        );

        document.getElementById("stat-total").textContent = counter.total;
        document.getElementById("stat-awaiting").textContent = counter.awaiting;
        document.getElementById("stat-deposit").textContent = counter.deposit;
        document.getElementById("stat-confirmed").textContent = counter.confirmed;
        document.getElementById("upcoming-badge").textContent = "Sap toi: " + counter.upcoming;
    }

    function safeStatusClass(statusValue) {
        const value = String(statusValue || "");
        return /^[a-z0-9_-]+$/i.test(value) ? value : "unknown";
    }

    function getStatusLabel(statusValue) {
        switch (statusValue) {
            case "awaiting_eligibility":
                return "Cho bac si duyet online";
            case "pending":
                return "Pending (legacy)";
            case "deposit_pending":
                return "Cho dat coc";
            case "confirmed":
                return "Da coc, cho check-in";
            case "ineligible":
                return "Khong du dieu kien tiem";
            case "checked_in":
                return "Da check-in";
            case "ready_to_inject":
                return "Cho tiem";
            case "in_observation":
                return "Theo doi sau tiem";
            case "completed":
                return "Hoan thanh";
            case "delayed":
                return "Tam hoan";
            case "cancelled":
                return "Da huy";
            default:
                return statusValue || "";
        }
    }

    function getDepositStateText(booking) {
        switch (booking.deposit_deadline_status) {
            case "paid":
                return "Da coc";
            case "warning":
                return booking.deposit_deadline_message || "Sap het han coc";
            case "upcoming":
                return booking.deposit_deadline_message || "Dang cho coc";
            case "expired":
                return "Qua han coc";
            default:
                if (booking.booking_source === "walkin") {
                    return "Walk-in";
                }
                return "Khong ap dung";
        }
    }

    function appendTextCell(row, value) {
        const cell = document.createElement("td");
        cell.textContent = value == null ? "" : String(value);
        row.appendChild(cell);
        return cell;
    }

    function makeActionButton(label, action, bookingId, isDanger = false) {
        const button = document.createElement("button");
        button.className = isDanger ? "action-btn is-danger" : "action-btn";
        button.type = "button";
        button.dataset.action = action;
        button.dataset.id = String(bookingId);
        button.textContent = label;
        return button;
    }

    function renderPortalReminder() {
        if (!reminderBox) {
            return;
        }

        if (!isCitizenUser) {
            reminderBox.hidden = true;
            reminderBox.textContent = "";
            return;
        }

        const remindedBooking = bookings.find((booking) => booking.needs_deposit_reminder);
        if (!remindedBooking) {
            reminderBox.hidden = true;
            reminderBox.textContent = "";
            return;
        }

        reminderBox.hidden = false;
        reminderBox.textContent = remindedBooking.deposit_deadline_message || "Ban co booking sap het han coc.";
    }

    function renderTable() {
        tableBody.textContent = "";
        emptyState.hidden = bookings.length > 0;

        bookings.forEach((booking) => {
            const row = document.createElement("tr");
            const note = booking.note ? booking.note : "Khong co";

            const contactCell = document.createElement("td");
            const nameEl = document.createElement("strong");
            nameEl.textContent = booking.full_name || "";
            const phoneEl = document.createElement("span");
            phoneEl.textContent = booking.phone || "";
            contactCell.appendChild(nameEl);
            contactCell.appendChild(document.createElement("br"));
            contactCell.appendChild(phoneEl);
            row.appendChild(contactCell);

            appendTextCell(row, booking.vaccine_name || "");
            appendTextCell(row, formatDate(booking.vaccine_date));
            appendTextCell(row, `Mui ${booking.dose_number || ""}`.trim());

            const statusCell = document.createElement("td");
            const statusBadge = document.createElement("span");
            statusBadge.className = `status-badge status-${safeStatusClass(booking.status)}`;
            statusBadge.textContent = getStatusLabel(booking.status);
            statusCell.appendChild(statusBadge);
            row.appendChild(statusCell);

            appendTextCell(row, formatMoney(booking.total_amount));
            appendTextCell(row, formatMoney(booking.deposit_amount));
            appendTextCell(
                row,
                booking.deposit_deadline
                    ? `${formatDate(booking.deposit_deadline)} - ${getDepositStateText(booking)}`
                    : getDepositStateText(booking)
            );
            appendTextCell(row, note);

            const actionsCell = document.createElement("td");
            const actions = document.createElement("div");
            actions.className = "row-actions";

            if (config.userRole === "citizen" && !["cancelled", "completed"].includes(booking.status)) {
                actions.appendChild(makeActionButton("Khai bao", "screening", booking.id));
            }
            if (booking.can_edit) {
                actions.appendChild(makeActionButton("Sua", "edit", booking.id));
            }
            if (booking.can_reschedule) {
                actions.appendChild(makeActionButton("Dat lai lich", "reschedule", booking.id));
            }
            if (booking.can_cancel) {
                actions.appendChild(makeActionButton("Huy lich", "cancel", booking.id, true));
            }

            actionsCell.appendChild(actions);
            row.appendChild(actionsCell);
            tableBody.appendChild(row);
        });

        updateStats();
        renderPortalReminder();
    }

    async function loadBookings() {
        const query = new URLSearchParams();
        const keyword = document.getElementById("filter-keyword").value.trim();
        const statusValue = document.getElementById("filter-status").value;
        const dateValue = document.getElementById("filter-date").value;

        if (keyword) query.set("q", keyword);
        if (statusValue) query.set("status", statusValue);
        if (dateValue) query.set("date", dateValue);

        const suffix = query.toString() ? "?" + query.toString() : "";
        const response = await fetch("/booking/" + suffix, { credentials: "same-origin" });
        const data = await response.json();
        bookings = Array.isArray(data) ? data : [];
        allPortalBookings = bookings.slice();
        renderTable();
    }

    async function saveBooking(payload) {
        const isEditing = Boolean(editingBookingId);
        const url = isEditing ? `/booking/${editingBookingId}/` : "/booking/";
        const method = isEditing ? "PATCH" : "POST";

        const response = await fetch(url, {
            method,
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken(),
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(
                typeof data.detail === "string" ? data.detail : Object.values(data).flat().join(" ")
            );
        }

        resetForm();
        showAlert(isEditing ? "Cap nhat booking thanh cong." : "Tao booking thanh cong.", false);
        await loadBookings();
    }

    async function cancelBooking(bookingId) {
        const response = await fetch(`/booking/${bookingId}/`, {
            method: "PATCH",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken(),
            },
            body: JSON.stringify({ status: "cancelled" }),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || "Khong the huy booking luc nay.");
        }

        await loadBookings();
    }

    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearAlert();

        try {
            await saveBooking(collectFormPayload());
        } catch (error) {
            showAlert(error.message || "Khong the luu booking.", true);
        }
    });

    cancelEditButton?.addEventListener("click", resetForm);
    document.getElementById("filter-btn")?.addEventListener("click", loadBookings);
    vaccineNameInput?.addEventListener("change", updatePricingSummary);
    vaccineDateInput?.addEventListener("change", updatePricingSummary);

    tableBody?.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) {
            return;
        }

        const bookingId = Number(button.dataset.id);
        const booking = bookings.find((item) => item.id === bookingId);
        if (!booking) {
            return;
        }

        if (button.dataset.action === "edit") {
            startEdit(booking);
            return;
        }
        if (button.dataset.action === "screening") {
            openDeclarationModal(String(bookingId));
            return;
        }
        if (button.dataset.action === "reschedule") {
            openRescheduleModal(String(bookingId));
            return;
        }

        try {
            if (!window.confirm("Ban chac chan muon huy lich hen nay?")) {
                return;
            }
            await cancelBooking(bookingId);
            showAlert("Da huy booking thanh cong.", false);
        } catch (error) {
            showAlert(error.message || "Khong the xu ly booking.", true);
        }
    });

    const vaccineQuery = new URLSearchParams(window.location.search).get("vaccine");
    if (vaccineQuery) {
        const matchedOption = Array.from(vaccineNameInput.options).find((option) => {
            return option.value === vaccineQuery || vaccineQuery.includes(option.value);
        });
        if (matchedOption) {
            vaccineNameInput.value = matchedOption.value;
        }
    }

    allPortalBookings = bookings.slice();
    renderTable();
    updatePricingSummary();
})();

function openRescheduleModal(bookingId) {
    reschedulingBookingId = bookingId;
    const modal = document.getElementById("reschedule-modal");
    if (!modal) {
        return;
    }

    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    document.getElementById("reschedule-date").min = tomorrow.toISOString().split("T")[0];
    document.getElementById("reschedule-date").value = "";
    modal.style.display = "flex";
}

function closeRescheduleModal() {
    reschedulingBookingId = null;
    const modal = document.getElementById("reschedule-modal");
    if (modal) {
        modal.style.display = "none";
    }
}

async function submitReschedule() {
    const newDate = document.getElementById("reschedule-date").value;
    if (!newDate) {
        window.alert("Vui long chon ngay tiem moi.");
        return;
    }

    try {
        const response = await fetch(`/api/medical/${reschedulingBookingId}/reschedule/`, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getPortalCSRF(),
            },
            body: JSON.stringify({ vaccine_date: newDate }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            window.alert(data.detail || JSON.stringify(data));
            return;
        }

        closeRescheduleModal();
        window.location.reload();
    } catch (error) {
        console.error(error);
        window.alert("Co loi xay ra khi dat lai lich.");
    }
}

function getPortalCSRF() {
    const name = "csrftoken=";
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const cookie of cookies) {
        const trimmed = cookie.trim();
        if (trimmed.startsWith(name)) {
            return decodeURIComponent(trimmed.slice(name.length));
        }
    }
    return "";
}

function formatPortalDate(dateString) {
    if (!dateString) {
        return "";
    }
    return new Date(dateString + "T00:00:00").toLocaleDateString("vi-VN");
}

function getCurrentPortalBooking() {
    return allPortalBookings.find((booking) => String(booking.id) === String(declarationBookingId)) || null;
}

function showDeclNotice(message, isSuccess) {
    const notice = document.getElementById("decl-notice");
    notice.textContent = message;
    notice.style.display = "block";
    notice.style.background = isSuccess ? "#f0fdf4" : "#fff7ed";
    notice.style.color = isSuccess ? "#166534" : "#92400e";
    notice.style.border = isSuccess ? "1px solid #bbf7d0" : "1px solid #fed7aa";
}

function clearDeclNotice() {
    const notice = document.getElementById("decl-notice");
    if (!notice) {
        return;
    }
    notice.style.display = "none";
    notice.textContent = "";
}

function resetDeclarationForm() {
    document.getElementById("declaration-form")?.reset();
    DECLARATION_FIELDS.forEach((field) => {
        const detail = document.getElementById(field.detailId);
        if (detail) {
            detail.value = "";
        }
    });
    const note = document.getElementById("decl-note");
    if (note) {
        note.value = "";
    }
}

function populateDeclarationForm(declaration) {
    resetDeclarationForm();
    if (!declaration) {
        return;
    }
    DECLARATION_FIELDS.forEach((field) => {
        const checkbox = document.getElementById(field.checkboxId);
        const detail = document.getElementById(field.detailId);
        if (checkbox) {
            checkbox.checked = Boolean(declaration[field.payloadKey]);
        }
        if (detail) {
            detail.value = declaration[field.detailKey] || "";
        }
    });
    const note = document.getElementById("decl-note");
    if (note) {
        note.value = declaration.note || "";
    }
}

function collectDeclarationPayload() {
    const payload = { note: document.getElementById("decl-note").value.trim() };
    DECLARATION_FIELDS.forEach((field) => {
        payload[field.payloadKey] = Boolean(document.getElementById(field.checkboxId)?.checked);
        payload[field.detailKey] = document.getElementById(field.detailId)?.value.trim() || "";
    });
    return payload;
}

function renderOnlineReview(review) {
    const box = document.getElementById("decl-online-review");
    if (!box) {
        return;
    }
    if (!review) {
        box.style.display = "none";
        return;
    }

    const textMap = {
        eligible: "Bac si danh gia ban du dieu kien de chuyen sang buoc dat coc.",
        delayed: "Bac si danh gia can tam hoan va theo doi them truoc khi dat coc.",
        ineligible: "Bac si danh gia booking nay khong du dieu kien tiem o giai doan hien tai.",
    };

    document.getElementById("decl-online-review-text").textContent = textMap[review.decision] || review.decision;
    document.getElementById("decl-online-review-meta").textContent =
        `Nguoi duyet: ${review.reviewed_by_name || "Bac si"} - ${formatPortalDate(review.reviewed_at?.slice(0, 10) || "")}`;
    document.getElementById("decl-online-review-note").textContent =
        review.doctor_note || "Khong co ghi chu them.";
    box.style.background = review.decision === "eligible" ? "#eff6ff" : "#fff7ed";
    box.style.borderColor = review.decision === "eligible" ? "#bfdbfe" : "#fed7aa";
    box.style.display = "block";
}

function renderScreeningResult(screeningResult) {
    const resultBox = document.getElementById("decl-screening-result");
    if (!resultBox) {
        return;
    }
    if (!screeningResult) {
        resultBox.style.display = "none";
        return;
    }

    const decision = screeningResult.decision || (screeningResult.is_eligible ? "eligible" : "delayed");
    const textMap = {
        eligible: "Ket qua kham tai quay: du dieu kien tiem chung.",
        delayed: "Ket qua kham tai quay: tam hoan va can dat lai lich.",
        cancelled: "Ket qua kham tai quay: chong chi dinh tiem.",
    };

    document.getElementById("decl-result-text").textContent = textMap[decision] || decision;
    document.getElementById("decl-result-temp").textContent = screeningResult.temperature ? `${screeningResult.temperature}Â°C` : "-";
    document.getElementById("decl-result-bp").textContent = screeningResult.blood_pressure || "-";
    document.getElementById("decl-result-note").textContent = screeningResult.doctor_note || "Khong co ghi chu them.";
    resultBox.style.background = decision === "eligible" ? "#f0fdf4" : "#fff7ed";
    resultBox.style.borderColor = decision === "eligible" ? "#bbf7d0" : "#fed7aa";
    resultBox.style.display = "block";
}

function setDeclarationFormEnabled(enabled) {
    const inputs = document.querySelectorAll(
        "#declaration-form input, #declaration-form textarea, #declaration-form button[type='submit']"
    );
    inputs.forEach((element) => {
        element.disabled = !enabled;
    });
}

function setDoctorReviewFormVisible() {}

function setDoctorReviewFormEnabled() {}

async function refreshDeclarationModal() {
    if (!declarationBookingId) {
        return;
    }

    const bookingInfo = getCurrentPortalBooking();
    if (bookingInfo) {
        document.getElementById("decl-modal-title").textContent = `Khai bao truoc tiem - ${bookingInfo.vaccine_name}`;
        document.getElementById("decl-modal-subtitle").textContent =
            `Ngay tiem: ${formatPortalDate(bookingInfo.vaccine_date)} | Mui ${bookingInfo.dose_number}`;
    }

    clearDeclNotice();
    renderOnlineReview(null);
    renderScreeningResult(null);

    try {
        const response = await fetch(`/api/medical/pre-screening/${declarationBookingId}/`, {
            credentials: "same-origin",
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            showDeclNotice(data.detail || "Khong tai duoc du lieu khai bao.", false);
            setDeclarationFormEnabled(false);
            return;
        }

        populateDeclarationForm(data.declaration);
        renderOnlineReview(data.online_review);
        renderScreeningResult(data.screening_result);

        const canEditDeclaration = Boolean(
            bookingInfo
            && window.bookingPortalConfig?.userRole === "citizen"
            && ["awaiting_eligibility", "pending", "deposit_pending", "confirmed", "delayed", "ineligible"].includes(bookingInfo.status)
        );

        setDeclarationFormEnabled(canEditDeclaration);
        if (!canEditDeclaration && window.bookingPortalConfig?.userRole === "citizen") {
            showDeclNotice("Booking nay khong con mo de cap nhat khai bao. Ban chi co the xem ket qua.", false);
        }
    } catch (error) {
        console.error("Khong tai duoc du lieu khai bao:", error);
        showDeclNotice("Khong tai duoc du lieu khai bao.", false);
        setDeclarationFormEnabled(false);
    }
}

async function openDeclarationModal(bookingId) {
    declarationBookingId = bookingId;
    const modal = document.getElementById("declaration-modal");
    if (!modal) {
        return;
    }

    resetDeclarationForm();
    await refreshDeclarationModal();
    modal.style.display = "flex";
}

function closeDeclarationModal() {
    declarationBookingId = null;
    const modal = document.getElementById("declaration-modal");
    if (modal) {
        modal.style.display = "none";
    }
}

async function submitDeclaration(event) {
    event.preventDefault();
    if (!declarationBookingId) {
        return;
    }

    const submitButton = document.getElementById("decl-submit-btn");
    const originalText = submitButton.textContent;
    submitButton.disabled = true;
    submitButton.textContent = "Dang luu...";

    try {
        const response = await fetch(`/api/medical/pre-screening/${declarationBookingId}/`, {
            method: "PATCH",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getPortalCSRF(),
            },
            body: JSON.stringify(collectDeclarationPayload()),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            showDeclNotice(`Loi: ${data.detail || JSON.stringify(data)}`, false);
        } else {
            showDeclNotice("Da luu khai bao thanh cong.", true);
            await reloadPortalBookingsAndModal();
        }
    } catch (error) {
        console.error(error);
        showDeclNotice("Co loi xay ra khi luu khai bao.", false);
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = originalText;
    }
}


async function reloadPortalBookingsAndModal() {
    window.location.reload();
}



