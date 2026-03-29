(function () {
    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(";") : [];
        for (const cookie of cookies) {
            const trimmed = cookie.trim();
            if (trimmed.startsWith(name + "=")) {
                return decodeURIComponent(trimmed.slice(name.length + 1));
            }
        }
        return "";
    }

    function showMessage(type, message) {
        const box = document.getElementById("messageBox");
        if (!box) {
            return;
        }

        box.hidden = false;
        box.className = "alert " + type;
        box.textContent = message;
    }

    function closeModal(modal) {
        if (modal) {
            modal.hidden = true;
        }
    }

    function openModal(selector) {
        const modal = document.querySelector(selector);
        if (modal) {
            modal.hidden = false;
        }
    }

    function upsertSelectOption(select, value, label, shouldSelect) {
        if (!select) {
            return;
        }

        const normalizedValue = String(value);
        let option = Array.from(select.options).find((item) => item.value === normalizedValue);

        if (!option) {
            option = document.createElement("option");
            option.value = normalizedValue;
            select.appendChild(option);
        }

        option.textContent = label;

        if (shouldSelect) {
            select.value = normalizedValue;
        }
    }

    function syncLocationOption(locationData) {
        if (!locationData || !locationData.id || !locationData.name) {
            return;
        }

        const vaccineLocationSelect = document.getElementById("vaccineLocationSelect");
        const locationFilter = document.getElementById("locationFilter");
        const locationSupportList = document.getElementById("locationSupportList");

        upsertSelectOption(vaccineLocationSelect, locationData.id, locationData.name, true);
        upsertSelectOption(locationFilter, locationData.name.toLowerCase(), locationData.name, false);

        if (!locationSupportList) {
            return;
        }

        const emptyItem = locationSupportList.querySelector("[data-empty-location]");
        if (emptyItem) {
            emptyItem.remove();
        }

        const exists = Array.from(locationSupportList.querySelectorAll("li"))
            .some((item) => item.textContent.trim() === locationData.name);

        if (!exists) {
            const item = document.createElement("li");
            item.textContent = locationData.name;
            locationSupportList.appendChild(item);
        }
    }

    function serializeForm(form) {
        const formData = new FormData(form);
        const payload = {};

        for (const [key, value] of formData.entries()) {
            if (key === "csrfmiddlewaretoken") {
                continue;
            }

            payload[key] = value === "" ? null : value;
        }

        return payload;
    }

    function normalizeError(data) {
        if (!data) {
            return "Đã có lỗi xảy ra. Vui lòng thử lại.";
        }

        if (typeof data.detail === "string") {
            return data.detail;
        }

        const messages = [];
        Object.values(data).forEach((value) => {
            if (Array.isArray(value)) {
                messages.push(value.join(" "));
                return;
            }

            if (typeof value === "string") {
                messages.push(value);
            }
        });

        return messages.join(" ") || "Đã có lỗi xảy ra. Vui lòng thử lại.";
    }

    function getVaccineStatus(row) {
        const today = window.inventoryDashboardToday || "";
        const expiration = row.dataset.expiration || "";
        const quantity = Number(row.dataset.quantity || 0);
        const minimum = Number(row.dataset.minimum || 0);

        if (expiration && today && expiration < today) {
            return "expired";
        }

        if (quantity <= minimum) {
            return "low";
        }

        if (expiration && today) {
            const diff = Math.ceil((new Date(expiration) - new Date(today)) / 86400000);
            if (diff >= 0 && diff <= 30) {
                return "expiring";
            }
        }

        return "normal";
    }

    function filterRows() {
        const searchInput = document.getElementById("inventorySearch");
        const statusFilter = document.getElementById("statusFilter");
        const supplierFilter = document.getElementById("supplierFilter");
        const locationFilter = document.getElementById("locationFilter");
        const rows = Array.from(document.querySelectorAll("#vaccineTableBody tr[data-search]"));
        const emptyState = document.getElementById("searchEmptyState");
        const tableMeta = document.getElementById("tableMeta");

        if (!rows.length) {
            return;
        }

        const keyword = (searchInput.value || "").trim().toLowerCase();
        const status = statusFilter.value;
        const supplier = supplierFilter.value;
        const location = locationFilter.value;

        let visibleCount = 0;

        rows.forEach((row) => {
            const matchesSearch = !keyword || row.dataset.search.includes(keyword);
            const matchesSupplier = supplier === "all" || row.dataset.supplier === supplier;
            const matchesLocation = location === "all" || row.dataset.location === location;
            const matchesStatus = status === "all" || getVaccineStatus(row) === status;
            const isVisible = matchesSearch && matchesSupplier && matchesLocation && matchesStatus;

            row.hidden = !isVisible;
            if (isVisible) {
                visibleCount += 1;
            }
        });

        if (tableMeta) {
            tableMeta.textContent = "Đang hiển thị " + visibleCount + " lô vắc xin phù hợp.";
        }

        if (emptyState) {
            emptyState.hidden = visibleCount !== 0;
        }
    }

    function exportVisibleRowsToCsv() {
        const rows = Array.from(document.querySelectorAll("#vaccineTableBody tr[data-search]"))
            .filter((row) => !row.hidden);

        if (!rows.length) {
            showMessage("error", "Không có dữ liệu hiển thị để xuất CSV.");
            return;
        }

        const headers = Array.from(document.querySelectorAll(".inventory-table thead th"))
            .map((header) => header.textContent.trim());

        const dataRows = rows.map((row) =>
            Array.from(row.children).map((cell) =>
                '"' + cell.innerText.replace(/\s+/g, " ").trim().replace(/"/g, '""') + '"'
            ).join(",")
        );

        const csv = [headers.join(","), ...dataRows].join("\n");
        const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "kho-vac-xin.csv";
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }

    document.querySelectorAll("[data-open-modal]").forEach((button) => {
        button.addEventListener("click", function () {
            openModal(this.getAttribute("data-open-modal"));
        });
    });

    document.querySelectorAll("[data-close-modal]").forEach((button) => {
        button.addEventListener("click", function () {
            closeModal(this.closest(".modal"));
        });
    });

    document.querySelectorAll(".modal").forEach((modal) => {
        modal.addEventListener("click", function (event) {
            if (event.target === modal) {
                closeModal(modal);
            }
        });
    });

    document.querySelectorAll(".asset-form").forEach((form) => {
        form.addEventListener("submit", async function (event) {
            event.preventDefault();

            const submitButton = form.querySelector('button[type="submit"]');
            const initialLabel = submitButton ? submitButton.textContent : "";

            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = "Đang xử lý...";
            }

            try {
                const response = await fetch(form.dataset.endpoint, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCookie("csrftoken"),
                    },
                    credentials: "same-origin",
                    body: JSON.stringify(serializeForm(form)),
                });

                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(normalizeError(data));
                }

                showMessage("success", form.dataset.success || "Lưu dữ liệu thành công.");
                form.reset();
                closeModal(form.closest(".modal"));
                window.setTimeout(function () {
                    window.location.reload();
                }, 700);
            } catch (error) {
                showMessage("error", error.message);
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = initialLabel;
                }
            }
        });
    });

    const openQuickLocationModalButton = document.getElementById("openQuickLocationModalBtn");
    const quickLocationModal = document.getElementById("locationQuickModal");
    const quickLocationForm = document.getElementById("quickLocationForm");
    const quickLocationName = document.getElementById("quickLocationName");
    const quickLocationSubmitButton = document.getElementById("quickLocationSubmitBtn");

    if (openQuickLocationModalButton && quickLocationModal && quickLocationForm) {
        openQuickLocationModalButton.addEventListener("click", function () {
            quickLocationForm.reset();
            openModal("#locationQuickModal");
            if (quickLocationName) {
                window.setTimeout(function () {
                    quickLocationName.focus();
                }, 20);
            }
        });

        quickLocationForm.addEventListener("submit", async function (event) {
            event.preventDefault();

            const initialLabel = quickLocationSubmitButton ? quickLocationSubmitButton.textContent : "";
            if (quickLocationSubmitButton) {
                quickLocationSubmitButton.disabled = true;
                quickLocationSubmitButton.textContent = "Đang lưu vị trí...";
            }

            try {
                const response = await fetch("/assets/locations/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCookie("csrftoken"),
                    },
                    credentials: "same-origin",
                    body: JSON.stringify(serializeForm(quickLocationForm)),
                });

                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(normalizeError(data));
                }

                syncLocationOption(data);
                showMessage("success", "Đã thêm vị trí bảo quản và chọn sẵn trong form vắc xin.");
                quickLocationForm.reset();
                closeModal(quickLocationModal);
            } catch (error) {
                showMessage("error", error.message);
            } finally {
                if (quickLocationSubmitButton) {
                    quickLocationSubmitButton.disabled = false;
                    quickLocationSubmitButton.textContent = initialLabel;
                }
            }
        });
    }

    ["inventorySearch", "statusFilter", "supplierFilter", "locationFilter"].forEach((id) => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener("input", filterRows);
            element.addEventListener("change", filterRows);
        }
    });

    const resetFiltersButton = document.getElementById("resetFiltersBtn");
    if (resetFiltersButton) {
        resetFiltersButton.addEventListener("click", function () {
            document.getElementById("inventorySearch").value = "";
            document.getElementById("statusFilter").value = "all";
            document.getElementById("supplierFilter").value = "all";
            document.getElementById("locationFilter").value = "all";
            filterRows();
        });
    }

    const exportCsvButton = document.getElementById("exportCsvBtn");
    if (exportCsvButton) {
        exportCsvButton.addEventListener("click", exportVisibleRowsToCsv);
    }

    const refreshPageButton = document.getElementById("refreshPageBtn");
    if (refreshPageButton) {
        refreshPageButton.addEventListener("click", function () {
            window.location.reload();
        });
    }

    const logoutButton = document.getElementById("logoutBtn");
    if (logoutButton) {
        logoutButton.addEventListener("click", async function () {
            try {
                const response = await fetch("/auth/logout/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCookie("csrftoken"),
                    },
                    credentials: "same-origin",
                });

                if (!response.ok) {
                    throw new Error();
                }

                window.location.href = "/auth/login-page/";
            } catch (error) {
                showMessage("error", "Không thể đăng xuất lúc này. Vui lòng thử lại.");
            }
        });
    }

    filterRows();
})();
