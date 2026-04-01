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
    const cancelEditButton = document.getElementById("cancel-edit-btn");
    const fullNameInput = document.getElementById("full-name");
    const phoneInput = document.getElementById("phone");
    const emailInput = document.getElementById("email");
    const vaccineNameInput = document.getElementById("vaccine-name");
    const vaccineDateInput = document.getElementById("vaccine-date");
    const doseNumberInput = document.getElementById("dose-number");
    const statusInput = document.getElementById("status");
    const noteInput = document.getElementById("note");

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
        if (!dateString) return "";
        return new Date(dateString + "T00:00:00").toLocaleDateString("vi-VN");
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

    function collectFormPayload() {
        return {
            full_name: fullNameInput.value.trim(),
            phone: phoneInput.value.trim(),
            email: emailInput.value.trim(),
            vaccine_name: vaccineNameInput.value,
            vaccine_date: vaccineDateInput.value,
            dose_number: parseInt(doseNumberInput.value, 10),
            status: statusInput.value,
            note: noteInput.value.trim(),
        };
    }

    function resetForm() {
        editingBookingId = null;
        form.reset();
        document.getElementById("booking-id").value = "";
        document.getElementById("form-heading").textContent = "Tạo booking mới";
        document.getElementById("form-subtitle").textContent =
            "Thông tin sẽ được lưu và gửi sang quy trình xác nhận.";
        document.getElementById("submit-btn").textContent = "Tạo booking";
        cancelEditButton.hidden = true;
        clearAlert();

        fullNameInput.value = defaultValues.fullName;
        phoneInput.value = defaultValues.phone;
        emailInput.value = defaultValues.email;
        doseNumberInput.value = "1";
        statusInput.value = "pending";
        vaccineDateInput.value = "";
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
        statusInput.value = booking.status || "pending";
        noteInput.value = booking.note || "";
        document.getElementById("form-heading").textContent = "Cập nhật booking";
        document.getElementById("form-subtitle").textContent =
            "Bạn đang chỉnh sửa một booking đã tạo.";
        document.getElementById("submit-btn").textContent = "Lưu thay đổi";
        cancelEditButton.hidden = false;
        clearAlert();
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    function updateStats() {
        const counter = bookings.reduce(
            (accumulator, booking) => {
                accumulator.total += 1;
                accumulator.upcoming +=
                    booking.status !== "cancelled" && booking.vaccine_date >= config.today ? 1 : 0;
                if (booking.status in accumulator) {
                    accumulator[booking.status] += 1;
                }
                return accumulator;
            },
            { total: 0, pending: 0, confirmed: 0, completed: 0, upcoming: 0 }
        );

        document.getElementById("stat-total").textContent = counter.total;
        document.getElementById("stat-pending").textContent = counter.pending;
        document.getElementById("stat-confirmed").textContent = counter.confirmed;
        document.getElementById("stat-completed").textContent = counter.completed;
        document.getElementById("upcoming-badge").textContent = "Sắp tới: " + counter.upcoming;
    }

    function renderTable() {
        tableBody.innerHTML = "";
        emptyState.hidden = bookings.length > 0;

        bookings.forEach((booking) => {
            const row = document.createElement("tr");
            const note = booking.note ? booking.note : "Không có";
            const screeningActionLabel = ["screened", "completed", "delayed"].includes(booking.status)
                ? "Xem sàng lọc"
                : "Khai báo";
            const screeningAction = config.userRole === "citizen" && booking.status !== "cancelled"
                ? `<button class="action-btn" type="button" data-action="screening" data-id="${booking.id}">${screeningActionLabel}</button>`
                : "";
            const editAction = booking.can_edit
                ? `<button class="action-btn" type="button" data-action="edit" data-id="${booking.id}">Sửa</button>`
                : "";
            const cancelAction = booking.can_cancel
                ? `<button class="action-btn is-danger" type="button" data-action="cancel" data-id="${booking.id}">Hủy lịch</button>`
                : "";

            row.innerHTML = `
                <td>
                    <strong>${booking.full_name}</strong><br>
                    <span>${booking.phone}</span>
                </td>
                <td>${booking.vaccine_name}</td>
                <td>${formatDate(booking.vaccine_date)}</td>
                <td>Mũi ${booking.dose_number}</td>
                <td><span class="status-badge status-${booking.status}">${booking.status}</span></td>
                <td>${note}</td>
                <td><div class="row-actions">${screeningAction}${editAction}${cancelAction}</div></td>
            `;
            tableBody.appendChild(row);
        });

        updateStats();
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
        showAlert(isEditing ? "Cập nhật booking thành công." : "Tạo booking thành công.", false);
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
            throw new Error(data.detail || "Không thể hủy booking lúc này.");
        }

        await loadBookings();
    }

    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearAlert();

        try {
            await saveBooking(collectFormPayload());
        } catch (error) {
            showAlert(error.message || "Không thể lưu booking.", true);
        }
    });

    cancelEditButton?.addEventListener("click", resetForm);
    document.getElementById("filter-btn")?.addEventListener("click", loadBookings);

    tableBody?.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) return;

        const bookingId = Number(button.dataset.id);
        const booking = bookings.find((item) => item.id === bookingId);
        if (!booking) return;

        if (button.dataset.action === "edit") {
            startEdit(booking);
            return;
        }

        if (button.dataset.action === "screening") {
            window.location.href = `/users/screening/?booking=${bookingId}`;
            return;
        }

        if (!window.confirm("Bạn chắc chắn muốn hủy lịch hẹn này?")) return;
        try {
            await cancelBooking(bookingId);
            showAlert("Đã hủy booking thành công.", false);
        } catch (error) {
            showAlert(error.message || "Không thể hủy booking.", true);
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

    renderTable();
})();
