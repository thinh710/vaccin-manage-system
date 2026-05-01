(function () {
    "use strict";

    const statusLabels = {
        awaiting_eligibility: "Chờ bác sĩ duyệt online",
        pending: "Chờ xác nhận",
        deposit_pending: "Chờ đặt cọc",
        confirmed: "Đã xác nhận",
        ineligible: "Không đủ điều kiện tiêm",
        checked_in: "Đã check-in",
        ready_to_inject: "Chờ tiêm",
        in_observation: "Đang theo dõi",
        completed: "Đã hoàn thành",
        delayed: "Tạm hoãn",
        cancelled: "Đã hủy",
    };
    const declarationClosedStatuses = new Set(["cancelled", "completed", "checked_in", "ready_to_inject", "in_observation"]);
    const declarationFields = [
        {
            prefixKey: "severe-allergy",
            boolKey: "has_severe_allergy",
            detailKey: "severe_allergy_details",
            label: "Tiền sử phản vệ/dị ứng nặng hoặc dị ứng với thành phần thuốc/thức ăn",
            placeholder: "Mô tả phản ứng, tác nhân, mức độ...",
        },
        {
            prefixKey: "current-health-issue",
            boolKey: "has_current_health_issue",
            detailKey: "current_health_issue_details",
            label: "Tình trạng sức khỏe hiện tại: sốt, bệnh cấp tính, hoặc bệnh mãn tính đang đợt cấp",
            placeholder: "Mô tả triệu chứng, bệnh lý, đợt cấp...",
        },
        {
            prefixKey: "recent-vaccination",
            boolKey: "had_recent_vaccination",
            detailKey: "recent_vaccination_details",
            label: "Đã tiêm vaccine khác trong vòng 14 - 28 ngày gần đây",
            placeholder: "Loại vaccine, ngày tiêm, phản ứng nếu có...",
        },
        {
            prefixKey: "immunosuppressive-medication",
            boolKey: "uses_immunosuppressive_medication",
            detailKey: "immunosuppressive_medication_details",
            label: "Đang dùng thuốc ức chế miễn dịch, corticoid liều cao, hoặc điều trị ung thư",
            placeholder: "Tên thuốc, liều dùng, thời gian sử dụng...",
        },
        {
            prefixKey: "pregnancy-consideration",
            boolKey: "has_pregnancy_or_breastfeeding_consideration",
            detailKey: "pregnancy_or_breastfeeding_details",
            label: "Đối với nữ giới trong độ tuổi sinh đẻ: mang thai, dự định mang thai, hoặc đang cho con bú",
            placeholder: "Mô tả tình trạng hiện tại, dự định mang thai, hoặc cho con bú...",
        },
    ];

    const seasonalVaccinesData = {
        hpv: {
            icon: "HPV",
            heading: "PhÃ²ng ngá»«a ung thÆ° do HPV hiá»‡u quáº£ hÆ¡n vá»›i lá»‹ch tiÃªm Ä‘Ãºng",
            description: "HPV lÃ  nguyÃªn nhÃ¢n chÃ­nh gÃ¢y ung thÆ° cá»• tá»­ cung vÃ  nhiá»u bá»‡nh lÃ½ khÃ¡c. TiÃªm Ä‘Ãºng lá»‹ch giÃºp giáº£m nguy cÆ¡ vÃ  báº£o vá»‡ lÃ¢u dÃ i cho cáº£ nam vÃ  ná»¯.",
            backgroundImage: "/static/users/img/seasonal-vaccines/hpv-banner.jpg",
            bullets: [
                "TiÃªm váº¯c xin Ä‘Ãºng lá»‹ch lÃ  biá»‡n phÃ¡p phÃ²ng ngá»«a hiá»‡u quáº£ cÃ¡c bá»‡nh liÃªn quan Ä‘áº¿n HPV.",
                "Gardasil 9 báº£o vá»‡ 9 chá»§ng, phÃ¹ há»£p cho ngÆ°á»i tá»« 9 Ä‘áº¿n 45 tuá»•i.",
                "NÃªn tÆ° váº¥n vá»›i bÃ¡c sÄ© Ä‘á»ƒ chá»n phÃ¡c Ä‘á»“ tiÃªm phÃ¹ há»£p theo Ä‘á»™ tuá»•i.",
            ],
            cards: [
                { country: "Hoa Ká»³", discount: "-170.000Ä‘", image: "/static/users/img/seasonal-vaccines/hpv-card.jpg", title: "Váº¯c xin Gardasil 9 0.5ml", desc: "PhÃ²ng bá»‡nh ung thÆ° do HPV 9 chá»§ng", price: "2.948.000Ä‘", oldPrice: "2.965.000Ä‘" },
                { country: "Hoa Ká»³", discount: "", image: "/static/users/img/seasonal-vaccines/hpv-card.jpg", title: "GÃ³i tÆ° váº¥n HPV", desc: "ÄÃ¡nh giÃ¡ Ä‘á»™ tuá»•i, lá»‹ch mÅ©i vÃ  hÆ°á»›ng Ä‘áº·t háº¹n tiÃªm phÃ¹ há»£p", price: "Äáº·t háº¹n", oldPrice: "" },
            ],
        },
        dengue: {
            icon: "SXH",
            heading: "MÃ¹a mÆ°a cáº§n phÃ²ng sá»‘t xuáº¥t huyáº¿t chá»§ Ä‘á»™ng",
            description: "Sá»‘t xuáº¥t huyáº¿t tÄƒng nhanh trong mÃ¹a mÆ°a, Ä‘áº·c biá»‡t vá»›i tráº» em vÃ  ngÆ°á»i cÃ³ sá»©c Ä‘á» khÃ¡ng yáº¿u. Cáº§n káº¿t há»£p tiÃªm phÃ²ng vÃ  phÃ²ng muá»—i Ä‘á»‘t.",
            backgroundImage: "/static/users/img/seasonal-vaccines/dengue-banner.jpg",
            bullets: [
                "Theo dÃµi triá»‡u chá»©ng sá»‘t cao, Ä‘au má»i, xuáº¥t huyáº¿t dÆ°á»›i da Ä‘á»ƒ Ä‘i khÃ¡m sá»›m.",
                "TiÃªm váº¯c xin giÃºp giáº£m nguy cÆ¡ diá»…n tiáº¿n náº·ng á»Ÿ nhÃ³m phÃ¹ há»£p.",
                "Káº¿t há»£p dá»n dáº¹p mÃ´i trÆ°á»ng sá»‘ng vÃ  ngá»§ mÃ n phÃ²ng muá»—i.",
            ],
            cards: [
                { country: "PhÃ¡p", discount: "-90.000Ä‘", image: "/static/users/img/seasonal-vaccines/dengue-card.jpg", title: "Váº¯c xin Qdenga", desc: "Há»— trá»£ phÃ²ng sá»‘t xuáº¥t huyáº¿t cho tráº» em vÃ  ngÆ°á»i lá»›n", price: "1.390.000Ä‘", oldPrice: "1.480.000Ä‘" },
                { country: "TÆ° váº¥n", discount: "", image: "/static/users/img/seasonal-vaccines/dengue-card.jpg", title: "GÃ³i tÆ° váº¥n mÃ¹a dá»‹ch", desc: "Kiá»ƒm tra lá»‹ch tiÃªm vÃ  má»©c Ä‘á»™ nguy cÆ¡ theo tá»«ng Ä‘á»™ tuá»•i", price: "Äáº·t háº¹n", oldPrice: "" },
            ],
        },
        bexsero: {
            icon: "MEN B",
            heading: "Báº£o vá»‡ tráº» nhá» trÆ°á»›c viÃªm nÃ£o mÃ´ cáº§u nhÃ³m B",
            description: "ViÃªm nÃ£o mÃ´ cáº§u cÃ³ thá»ƒ diá»…n tiáº¿n ráº¥t nhanh. Bexsero lÃ  lá»±a chá»n quan trá»ng Ä‘á»‘i vá»›i tráº» nhá» vÃ  nhá»¯ng ngÆ°á»i cÃ³ nguy cÆ¡ cao.",
            backgroundImage: "/static/users/img/seasonal-vaccines/meningo-banner.jpg",
            bullets: [
                "Cáº§n tiÃªm Ä‘Ãºng lá»‹ch theo khuyáº¿n nghá»‹ cá»§a bÃ¡c sÄ© nhi khoa.",
                "ChÃº Ã½ dáº¥u hiá»‡u sá»‘t cao, cá»• cá»©ng, li bÃ¬, nÃ´n Ã³i Ä‘á»ƒ cáº¥p cá»©u sá»›m.",
                "CÃ³ thá»ƒ tiÃªm cÃ¹ng cÃ¡c mÅ©i khÃ¡c nhÆ°ng cáº§n Ä‘Æ°á»£c tÆ° váº¥n lá»‹ch cá»¥ thá»ƒ.",
            ],
            cards: [
                { country: "Ã", discount: "", image: "/static/users/img/seasonal-vaccines/meningo-card.jpg", title: "Váº¯c xin Bexsero", desc: "PhÃ²ng viÃªm nÃ£o mÃ´ cáº§u nhÃ³m B cho tráº» em vÃ  thanh thiáº¿u niÃªn", price: "2.350.000Ä‘", oldPrice: "" },
                { country: "GÃ³i tiÃªm", discount: "", image: "/static/users/img/seasonal-vaccines/meningo-card.jpg", title: "TÆ° váº¥n lá»‹ch tiÃªm mÃ´ cáº§u", desc: "Tá»•ng há»£p lá»‹ch nháº¯c mÅ©i Ä‘á»ƒ khÃ´ng bá» lá»¡ cÃ¡c má»‘c quan trá»ng", price: "Äáº·t háº¹n", oldPrice: "" },
            ],
        },
        acyw: {
            icon: "ACYW",
            heading: "TÄƒng cÆ°á»ng báº£o vá»‡ vá»›i viÃªm nÃ£o mÃ´ cáº§u ACYW",
            description: "MÅ©i ACYW phÃ¹ há»£p vá»›i há»c sinh, sinh viÃªn, ngÆ°á»i Ä‘i du lá»‹ch vÃ  nhá»¯ng ngÆ°á»i sá»‘ng trong mÃ´i trÆ°á»ng Ä‘Ã´ng Ä‘Ãºc.",
            backgroundImage: "/static/users/img/seasonal-vaccines/meningo-banner.jpg",
            bullets: [
                "PhÃ¹ há»£p vá»›i nhÃ³m chuáº©n bá»‹ du há»c, á»Ÿ kÃ½ tÃºc xÃ¡ hoáº·c Ä‘i nÆ°á»›c ngoÃ i.",
                "Cáº§n xem láº¡i lá»‹ch sá»­ tiÃªm trÆ°á»›c Ä‘Ã³ Ä‘á»ƒ trÃ¡nh trÃ¹ng láº·p mÅ©i.",
                "BÃ¡c sÄ© sáº½ hÆ°á»›ng dáº«n thá»i Ä‘iá»ƒm nháº¯c láº¡i náº¿u cáº§n.",
            ],
            cards: [
                { country: "Hoa Ká»³", discount: "", image: "/static/users/img/seasonal-vaccines/meningo-card.jpg", title: "Váº¯c xin Menactra / MenQuadfi", desc: "PhÃ²ng viÃªm nÃ£o mÃ´ cáº§u nhÃ³m A, C, Y, W-135", price: "1.850.000Ä‘", oldPrice: "" },
                { country: "Lá»‹ch nháº¯c", discount: "", image: "/static/users/img/seasonal-vaccines/meningo-card.jpg", title: "PhÃ¡c Ä‘á»“ nháº¯c láº¡i", desc: "Theo dÃµi lá»‹ch nháº¯c cho há»c sinh, sinh viÃªn vÃ  ngÆ°á»i Ä‘i du lá»‹ch", price: "Äáº·t háº¹n", oldPrice: "" },
            ],
        },
        japanese: {
            icon: "JEV",
            heading: "Chuáº©n bá»‹ mÃ¹a hÃ¨ vá»›i tiÃªm phÃ²ng viÃªm nÃ£o Nháº­t Báº£n",
            description: "Bá»‡nh thÆ°á»ng gia tÄƒng vÃ o mÃ¹a hÃ¨, nháº¥t lÃ  á»Ÿ tráº» em sá»‘ng táº¡i khu vá»±c cÃ³ muá»—i truyá»n bá»‡nh. TiÃªm phÃ²ng sá»›m giÃºp báº£o vá»‡ tá»‘t hÆ¡n.",
            backgroundImage: "/static/users/img/seasonal-vaccines/combo-banner.jpg",
            bullets: [
                "NÃªn xem láº¡i lá»‹ch mÅ©i cÆ¡ báº£n vÃ  nháº¯c láº¡i trÆ°á»›c cao Ä‘iá»ƒm mÃ¹a hÃ¨.",
                "PhÃ¹ há»£p cho tráº» em vÃ  ngÆ°á»i lá»›n cÃ³ nguy cÆ¡ theo chá»‰ Ä‘á»‹nh.",
                "Cáº§n káº¿t há»£p phÃ²ng muá»—i Ä‘á»‘t vÃ  vá»‡ sinh mÃ´i trÆ°á»ng.",
            ],
            cards: [
                { country: "Nháº­t Báº£n", discount: "", image: "/static/users/img/seasonal-vaccines/dengue-card.jpg", title: "Váº¯c xin viÃªm nÃ£o Nháº­t Báº£n", desc: "Báº£o vá»‡ trÆ°á»›c nguy cÆ¡ viÃªm nÃ£o trong mÃ¹a hÃ¨", price: "890.000Ä‘", oldPrice: "" },
                { country: "TÆ° váº¥n", discount: "", image: "/static/users/img/seasonal-vaccines/dengue-card.jpg", title: "Lá»‹ch tiÃªm theo mÃ¹a", desc: "Tá»•ng há»£p cÃ¡c mÅ©i nÃªn tiÃªm trÆ°á»›c khi vÃ o mÃ¹a dá»‹ch", price: "Äáº·t háº¹n", oldPrice: "" },
            ],
        },
        combo: {
            icon: "6IN1",
            heading: "MÅ©i 6 trong 1 giÃºp tráº» nhá» Ä‘Æ°á»£c báº£o vá»‡ sá»›m",
            description: "Váº¯c xin 6 trong 1 giÃºp giáº£m sá»‘ mÅ©i tiÃªm, há»— trá»£ phÃ²ng nhiá»u bá»‡nh nguy hiá»ƒm vÃ  tiá»‡n lá»£i cho gia Ä‘Ã¬nh trong giai Ä‘oáº¡n Ä‘áº§u Ä‘á»i.",
            backgroundImage: "/static/users/img/seasonal-vaccines/combo-banner.jpg",
            bullets: [
                "Báº£o vá»‡ báº¡ch háº§u, ho gÃ , uá»‘n vÃ¡n, báº¡i liá»‡t, viÃªm gan B vÃ  Hib.",
                "PhÃ¹ há»£p vá»›i lá»‹ch tiÃªm cho tráº» nhá» theo tÆ° váº¥n cá»§a bÃ¡c sÄ©.",
                "Cáº§n theo dÃµi lá»‹ch nháº¯c mÅ©i Ä‘á»ƒ Ä‘áº£m báº£o hiá»‡u quáº£ báº£o vá»‡.",
            ],
            cards: [
                { country: "GÃ³i cÆ¡ báº£n", discount: "-120.000Ä‘", image: "/static/users/img/seasonal-vaccines/combo-banner.jpg", title: "Váº¯c xin 6 trong 1", desc: "Giáº£m sá»‘ mÅ©i tiÃªm, báº£o vá»‡ nhiá»u bá»‡nh cho tráº» nhá»", price: "1.015.000Ä‘", oldPrice: "1.135.000Ä‘" },
                { country: "Lá»‹ch tiÃªm", discount: "", image: "/static/users/img/seasonal-vaccines/combo-banner.jpg", title: "Äáº·t lá»‹ch cho bÃ©", desc: "Theo dÃµi lá»‹ch mÅ©i cÆ¡ báº£n vÃ  nháº¯c láº¡i ngay táº¡i dashboard", price: "Äáº·t háº¹n", oldPrice: "" },
            ],
        },
    };

    const config = readJsonScript("dashboard-config", {});
    const vaccineOptions = readJsonScript("dashboard-vaccine-options", []);
    let bookings = readJsonScript("dashboard-initial-bookings", []);
    let screeningBookings = readJsonScript("dashboard-screening-bookings", []);
    let editingBookingId = null;
    let reschedulingBookingId = null;
    let currentScreeningBooking = null;
    let dashboardVaccineOptions = [];
    let filteredDashboardVaccineOptions = [];
    let highlightedDashboardVaccineIndex = -1;
    let selectedDashboardVaccineValue = "";

    const elements = {
        logoutBtn: document.getElementById("logoutBtn"),
        bookingForm: document.getElementById("dashboard-booking-form"),
        bookingId: document.getElementById("dashboard-booking-id"),
        bookingAlert: document.getElementById("dashboard-booking-alert"),
        formHeading: document.getElementById("dashboard-booking-form-heading"),
        formSubtitle: document.getElementById("dashboard-booking-form-subtitle"),
        submitBookingBtn: document.getElementById("dashboard-booking-submit-btn"),
        cancelEditBtn: document.getElementById("dashboard-cancel-edit-btn"),
        fullName: document.getElementById("dashboard-full-name"),
        phone: document.getElementById("dashboard-phone"),
        email: document.getElementById("dashboard-email"),
        vaccineName: document.getElementById("dashboard-vaccine-name"),
        vaccineCombobox: document.querySelector("[data-dashboard-vaccine-combobox]"),
        vaccineComboboxInput: document.getElementById("dashboard-vaccine-combobox"),
        vaccineComboboxToggle: document.getElementById("dashboard-vaccine-toggle"),
        vaccineComboboxList: document.getElementById("dashboard-vaccine-options"),
        vaccineComboboxCount: document.getElementById("dashboard-vaccine-count"),
        vaccineDate: document.getElementById("dashboard-vaccine-date"),
        doseNumber: document.getElementById("dashboard-dose-number"),
        status: document.getElementById("dashboard-status"),
        note: document.getElementById("dashboard-note"),
        filterKeyword: document.getElementById("dashboard-filter-keyword"),
        filterStatus: document.getElementById("dashboard-filter-status"),
        filterDate: document.getElementById("dashboard-filter-date"),
        filterBtn: document.getElementById("dashboard-filter-btn"),
        bookingEmpty: document.getElementById("dashboard-booking-empty"),
        bookingTableBody: document.getElementById("dashboard-booking-table-body"),
        rescheduleModal: document.getElementById("dashboard-reschedule-modal"),
        rescheduleDate: document.getElementById("dashboard-reschedule-date"),
        rescheduleInfo: document.getElementById("dashboard-reschedule-info"),
        rescheduleSubmit: document.getElementById("dashboard-reschedule-submit"),
        rescheduleCancel: document.getElementById("dashboard-reschedule-cancel"),
        screeningList: document.getElementById("dashboard-screening-list"),
        screeningDetail: document.getElementById("dashboard-screening-detail"),
        screeningEmpty: document.getElementById("dashboard-screening-empty"),
        screeningResult: document.getElementById("dashboard-screening-result"),
        onlineReview: document.getElementById("dashboard-online-review"),
        onlineReviewSummary: document.getElementById("dashboard-online-review-summary"),
        onlineReviewMeta: document.getElementById("dashboard-online-review-meta"),
        screeningTitle: document.getElementById("dashboard-screening-title"),
        screeningDescription: document.getElementById("dashboard-screening-description"),
        screeningStatus: document.getElementById("dashboard-screening-status"),
        screeningDate: document.getElementById("dashboard-screening-date"),
        screeningVaccine: document.getElementById("dashboard-screening-vaccine"),
        screeningDose: document.getElementById("dashboard-screening-dose"),
        screeningDeclaration: document.getElementById("dashboard-screening-declaration"),
        screeningNotice: document.getElementById("dashboard-screening-notice"),
        screeningForm: document.getElementById("dashboard-screening-form"),
        screeningQuestionGroup: document.getElementById("dashboard-screening-question-group"),
        declarationNote: document.getElementById("dashboard-declaration-note"),
        screeningSaveBtn: document.getElementById("dashboard-screening-save-btn"),
        screeningResetBtn: document.getElementById("dashboard-screening-reset-btn"),
        resultSummary: document.getElementById("dashboard-result-summary"),
        resultTemperature: document.getElementById("dashboard-result-temperature"),
        resultBloodPressure: document.getElementById("dashboard-result-blood-pressure"),
        resultNote: document.getElementById("dashboard-result-note"),
    };

    const defaultBookingValues = {
        fullName: elements.fullName?.value || "",
        phone: elements.phone?.value || "",
        email: elements.email?.value || "",
    };

    function readJsonScript(id, fallback) {
        const node = document.getElementById(id);
        if (!node || !node.textContent) return fallback;
        try {
            const parsed = JSON.parse(node.textContent);
            if (typeof parsed === "string") {
                return JSON.parse(parsed);
            }
            return parsed;
        } catch (error) {
            console.warn("KhÃ´ng Ä‘á»c Ä‘Æ°á»£c dá»¯ liá»‡u dashboard:", id, error);
            return fallback;
        }
    }

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

    function normalizeText(value) {
        return String(value || "")
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/Ä‘/g, "d")
            .replace(/Ä/g, "D")
            .replace(/[^a-z0-9]+/g, " ")
            .trim();
    }

    function safeStatusClass(status) {
        return String(status || "pending").replace(/[^a-z0-9_-]/gi, "");
    }

    function setText(node, value) {
        if (node) node.textContent = value == null || value === "" ? "â€”" : String(value);
    }

    function clearNode(node) {
        if (!node) return;
        while (node.firstChild) node.removeChild(node.firstChild);
    }

    function getDeclarationFieldId(field) {
        return "dashboard-" + field.prefixKey;
    }

    function getDeclarationDetailId(field) {
        return "dashboard-" + field.prefixKey + "-details";
    }

    function buildScreeningQuestionMarkup() {
        return declarationFields.map((field) => (
            '<div class="field">'
            + '<label class="checkbox-field is-wide">'
            + `<input id="${getDeclarationFieldId(field)}" type="checkbox">`
            + `<span>${field.label}</span>`
            + '</label>'
            + `<textarea id="${getDeclarationDetailId(field)}" rows="3" placeholder="${field.placeholder}"></textarea>`
            + '</div>'
        )).join("");
    }

    function setupScreeningQuestionGroup() {
        if (!elements.screeningQuestionGroup) return;
        elements.screeningQuestionGroup.innerHTML = buildScreeningQuestionMarkup();
    }

    function fillDeclarationFields(declaration) {
        declarationFields.forEach((field) => {
            const checkbox = document.getElementById(getDeclarationFieldId(field));
            const detail = document.getElementById(getDeclarationDetailId(field));
            if (checkbox) checkbox.checked = Boolean(declaration?.[field.boolKey]);
            if (detail) detail.value = declaration?.[field.detailKey] || "";
        });
    }

    function collectDeclarationFields() {
        const payload = {};
        declarationFields.forEach((field) => {
            payload[field.boolKey] = Boolean(document.getElementById(getDeclarationFieldId(field))?.checked);
            payload[field.detailKey] = document.getElementById(getDeclarationDetailId(field))?.value.trim() || "";
        });
        return payload;
    }

    function getOnlineReviewSummary(review) {
        if (!review) return "Chưa có kết luận duyệt online từ bác sĩ.";
        if (review.decision === "eligible") return "Bác sĩ xác nhận bạn đủ điều kiện để chuyển sang bước đặt cọc.";
        if (review.decision === "delayed") return "Bác sĩ kết luận cần tạm hoãn tiêm và theo dõi thêm trước khi đặt lại lịch.";
        if (review.decision === "ineligible") return "Bác sĩ kết luận bạn không đủ điều kiện tiêm cho lịch đăng ký này.";
        return review.decision || "";
    }
    function showAlert(node, message, isError) {
        if (!node) return;
        node.hidden = false;
        node.textContent = message;
        node.classList.toggle("is-error", Boolean(isError));
        node.classList.toggle("is-success", !isError);
    }

    function hideAlert(node) {
        if (!node) return;
        node.hidden = true;
        node.textContent = "";
        node.classList.remove("is-error", "is-success", "is-warning");
    }

    function parseApiError(data, fallback) {
        if (data && typeof data.detail === "string") return data.detail;
        if (data && typeof data === "object") {
            const values = Object.values(data).flat().filter(Boolean);
            if (values.length) return values.join(" ");
        }
        return fallback;
    }

    function makeButton(label, action, bookingId, extraClass) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "action-btn" + (extraClass ? " " + extraClass : "");
        button.dataset.action = action;
        button.dataset.id = String(bookingId);
        button.textContent = label;
        return button;
    }

    function getPanel(tabName) {
        return Array.from(document.querySelectorAll("[data-dashboard-panel]")).find(
            (panel) => panel.dataset.dashboardPanel === tabName
        );
    }

    function switchTab(tabName, options) {
        const panel = getPanel(tabName);
        if (!panel) return;

        document.querySelectorAll("[data-dashboard-panel]").forEach((item) => {
            item.classList.toggle("is-active", item === panel);
        });
        document.querySelectorAll(".dashboard-nav-item[data-dashboard-tab]").forEach((item) => {
            item.classList.toggle("is-active", item.dataset.dashboardTab === tabName);
        });

        if (options?.scroll) {
            panel.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    function bindTabs() {
        document.addEventListener("click", (event) => {
            const trigger = event.target.closest("[data-dashboard-tab]");
            if (!trigger) return;
            event.preventDefault();
            switchTab(trigger.dataset.dashboardTab, { scroll: true });
        });

        const initialTab = config.selectedScreeningBookingId
            ? "screening"
            : config.selectedTab && getPanel(config.selectedTab)
                ? config.selectedTab
                : "vaccines";
        switchTab(initialTab, { scroll: false });
    }

    function bindLogout() {
        elements.logoutBtn?.addEventListener("click", async () => {
            try {
                const response = await fetch("/auth/logout/", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCSRFToken(),
                    },
                });
                if (!response.ok) throw new Error("Logout failed");
                window.location.href = "/auth/login-page/";
            } catch (error) {
                window.alert("KhÃ´ng thá»ƒ Ä‘Äƒng xuáº¥t lÃºc nÃ y. Vui lÃ²ng thá»­ láº¡i.");
            }
        });
    }

    function bindHeroSlider() {
        const track = document.getElementById("dashboardHeroTrack");
        const dotsContainer = document.getElementById("dashboardHeroDots");
        const prevButton = document.getElementById("heroPrevBtn");
        const nextButton = document.getElementById("heroNextBtn");
        const slides = track ? Array.from(track.querySelectorAll(".dashboard-hero-slide")) : [];
        if (!track || !slides.length) return;

        let currentIndex = 0;
        let autoRotateId = null;

        function renderDots() {
            clearNode(dotsContainer);
            if (!dotsContainer) return;
            slides.forEach((_, index) => {
                const dot = document.createElement("button");
                dot.type = "button";
                dot.className = "dashboard-hero-dot" + (index === currentIndex ? " is-active" : "");
                dot.setAttribute("aria-label", "Chuyá»ƒn Ä‘áº¿n áº£nh " + (index + 1));
                dot.addEventListener("click", () => {
                    currentIndex = index;
                    updateHero();
                    restartAutoRotate();
                });
                dotsContainer.appendChild(dot);
            });
        }

        function updateHero() {
            track.style.transform = "translateX(-" + currentIndex * 100 + "%)";
            renderDots();
        }

        function goToNext() {
            currentIndex = (currentIndex + 1) % slides.length;
            updateHero();
        }

        function goToPrev() {
            currentIndex = (currentIndex - 1 + slides.length) % slides.length;
            updateHero();
        }

        function restartAutoRotate() {
            if (autoRotateId) window.clearInterval(autoRotateId);
            if (slides.length > 1) autoRotateId = window.setInterval(goToNext, 5000);
        }

        prevButton?.addEventListener("click", () => {
            goToPrev();
            restartAutoRotate();
        });
        nextButton?.addEventListener("click", () => {
            goToNext();
            restartAutoRotate();
        });
        updateHero();
        restartAutoRotate();
    }

    function renderSeasonalCategory(key) {
        const item = seasonalVaccinesData[key];
        const copy = document.getElementById("seasonalCopy");
        const icon = document.getElementById("seasonalIcon");
        const heading = document.getElementById("seasonalHeading");
        const description = document.getElementById("seasonalDescription");
        const bullets = document.getElementById("seasonalBullets");
        const cards = document.getElementById("seasonalCards");
        if (!item || !copy || !icon || !heading || !description || !bullets || !cards) return;

        document.querySelectorAll(".seasonal-tab").forEach((tab) => {
            tab.classList.toggle("is-active", tab.dataset.key === key);
        });
        copy.style.background =
            'linear-gradient(135deg, rgba(17, 184, 199, 0.94), rgba(16, 148, 166, 0.96)), url("' +
            item.backgroundImage +
            '") center center/cover no-repeat';
        icon.textContent = item.icon;
        heading.textContent = item.heading;
        description.textContent = item.description;

        clearNode(bullets);
        item.bullets.forEach((bullet) => {
            const listItem = document.createElement("li");
            const marker = document.createElement("span");
            const text = document.createElement("span");
            marker.className = "seasonal-bullet-dot";
            marker.textContent = "+";
            text.textContent = bullet;
            listItem.append(marker, text);
            bullets.appendChild(listItem);
        });

        clearNode(cards);
        item.cards.forEach((card) => {
            const article = document.createElement("article");
            article.className = "seasonal-card";

            const meta = document.createElement("div");
            meta.className = "seasonal-card-meta";
            const country = document.createElement("span");
            country.className = "seasonal-card-country";
            country.textContent = card.country;
            meta.appendChild(country);
            if (card.discount) {
                const discount = document.createElement("span");
                discount.className = "seasonal-card-discount";
                discount.textContent = card.discount;
                meta.appendChild(discount);
            }

            const image = document.createElement("img");
            image.className = "seasonal-card-image";
            image.src = card.image;
            image.alt = card.title;

            const title = document.createElement("div");
            title.className = "seasonal-card-title";
            title.textContent = card.title;

            const desc = document.createElement("p");
            desc.className = "seasonal-card-desc";
            desc.textContent = card.desc;

            const price = document.createElement("div");
            price.className = "seasonal-card-price" + (card.price === "Äáº·t háº¹n" ? " is-cta" : "");
            price.textContent = card.price;
            const dose = document.createElement("span");
            dose.textContent = " / Liá»u";
            price.appendChild(dose);

            article.append(meta, image, title, desc, price);

            if (card.oldPrice) {
                const oldPrice = document.createElement("div");
                oldPrice.className = "seasonal-card-old-price";
                oldPrice.textContent = card.oldPrice;
                article.appendChild(oldPrice);
            }

            const button = document.createElement("button");
            button.className = "seasonal-card-btn";
            button.type = "button";
            button.textContent = "Äáº·t háº¹n";
            button.addEventListener("click", () => openAppointmentForVaccine(card.title));
            article.appendChild(button);
            cards.appendChild(article);
        });
    }

    function bindSeasonalTabs() {
        document.querySelectorAll(".seasonal-tab").forEach((tab) => {
            tab.addEventListener("click", () => renderSeasonalCategory(tab.dataset.key));
        });
        renderSeasonalCategory("hpv");
    }

    function hasSelectableVaccines() {
        return Boolean(elements.vaccineName && Array.from(elements.vaccineName.options).some((option) => option.value));
    }

    function buildDashboardVaccineOptions() {
        if (!elements.vaccineName) return [];
        return Array.from(elements.vaccineName.options)
            .filter((option) => option.value)
            .map((option) => ({
                value: option.value,
                label: option.textContent.replace(/\s+/g, " ").trim(),
                quantity: option.dataset.qty || "",
                id: option.dataset.id || "",
            }));
    }

    function updateDashboardVaccineCount(visibleCount, hasKeyword) {
        if (!elements.vaccineComboboxCount) return;
        if (!dashboardVaccineOptions.length) {
            elements.vaccineComboboxCount.textContent = "Hiá»‡n chÆ°a cÃ³ váº¯c xin cÃ²n hÃ ng.";
            return;
        }
        if (
            selectedDashboardVaccineValue
            && elements.vaccineComboboxInput?.value === selectedDashboardVaccineValue
        ) {
            elements.vaccineComboboxCount.textContent = "ÄÃ£ chá»n " + selectedDashboardVaccineValue + ".";
            return;
        }
        if (hasKeyword) {
            elements.vaccineComboboxCount.textContent = visibleCount
                ? "TÃ¬m tháº¥y " + visibleCount + " váº¯c xin phÃ¹ há»£p."
                : "KhÃ´ng tÃ¬m tháº¥y váº¯c xin phÃ¹ há»£p.";
            return;
        }
        elements.vaccineComboboxCount.textContent = dashboardVaccineOptions.length + " váº¯c xin cÃ³ thá»ƒ chá»n.";
    }

    function setDashboardVaccineExpanded(isExpanded) {
        if (!elements.vaccineComboboxInput || !elements.vaccineComboboxList) return;
        elements.vaccineComboboxInput.setAttribute("aria-expanded", isExpanded ? "true" : "false");
        elements.vaccineComboboxList.classList.toggle("is-open", isExpanded);
        if (!isExpanded) {
            highlightedDashboardVaccineIndex = -1;
            elements.vaccineComboboxInput.removeAttribute("aria-activedescendant");
        }
    }

    function setDashboardVaccineHighlight(index) {
        if (!elements.vaccineComboboxList) return;
        const options = Array.from(elements.vaccineComboboxList.querySelectorAll(".dashboard-vaccine-combobox-option"));
        if (!options.length) {
            highlightedDashboardVaccineIndex = -1;
            return;
        }

        highlightedDashboardVaccineIndex = Math.max(0, Math.min(index, options.length - 1));
        options.forEach((option, optionIndex) => {
            const isActive = optionIndex === highlightedDashboardVaccineIndex;
            option.classList.toggle("is-active", isActive);
            option.setAttribute("aria-selected", isActive ? "true" : "false");
            if (isActive && elements.vaccineComboboxInput) {
                elements.vaccineComboboxInput.setAttribute("aria-activedescendant", option.id);
                option.scrollIntoView({ block: "nearest" });
            }
        });
    }

    function renderDashboardVaccineOptions(searchTerm) {
        if (!elements.vaccineComboboxList) return;
        const keyword = normalizeText(searchTerm);
        filteredDashboardVaccineOptions = keyword
            ? dashboardVaccineOptions.filter((option) => {
                const searchable = normalizeText(option.value + " " + option.label);
                return searchable.includes(keyword);
            })
            : [...dashboardVaccineOptions];

        clearNode(elements.vaccineComboboxList);
        if (!filteredDashboardVaccineOptions.length) {
            const empty = document.createElement("div");
            empty.className = "dashboard-vaccine-combobox-empty";
            empty.textContent = "KhÃ´ng tÃ¬m tháº¥y váº¯c xin phÃ¹ há»£p";
            elements.vaccineComboboxList.appendChild(empty);
            updateDashboardVaccineCount(0, Boolean(keyword));
            return;
        }

        filteredDashboardVaccineOptions.forEach((option, index) => {
            const item = document.createElement("div");
            item.className = "dashboard-vaccine-combobox-option";
            item.id = "dashboard-vaccine-option-" + index;
            item.setAttribute("role", "option");
            item.setAttribute("aria-selected", "false");
            item.tabIndex = -1;

            const title = document.createElement("strong");
            title.textContent = option.value;
            const meta = document.createElement("span");
            meta.textContent = option.quantity ? "CÃ²n " + option.quantity + " liá»u" : option.label;
            item.append(title, meta);

            item.addEventListener("mousedown", (event) => {
                event.preventDefault();
                selectDashboardVaccineOption(option);
            });
            item.addEventListener("mouseenter", () => setDashboardVaccineHighlight(index));
            elements.vaccineComboboxList.appendChild(item);
        });

        updateDashboardVaccineCount(filteredDashboardVaccineOptions.length, Boolean(keyword));
        setDashboardVaccineHighlight(0);
    }

    function openDashboardVaccineDropdown() {
        if (!elements.vaccineComboboxInput || elements.vaccineComboboxInput.disabled) return;
        const selectedValue = elements.vaccineName?.value || "";
        const searchTerm = selectedDashboardVaccineValue && selectedDashboardVaccineValue === selectedValue
            ? ""
            : elements.vaccineComboboxInput.value;
        renderDashboardVaccineOptions(searchTerm);
        setDashboardVaccineExpanded(true);
    }

    function closeDashboardVaccineDropdown() {
        setDashboardVaccineExpanded(false);
    }

    function setDashboardVaccineValue(value, fallbackLabel) {
        const option = dashboardVaccineOptions.find((item) => item.value === value);
        if (elements.vaccineName) elements.vaccineName.value = option ? option.value : "";
        selectedDashboardVaccineValue = option ? option.value : "";
        if (elements.vaccineComboboxInput) {
            elements.vaccineComboboxInput.value = option ? option.value : (fallbackLabel || "");
        }
        updateDashboardVaccineCount(option ? dashboardVaccineOptions.length : 0, false);
    }

    function selectDashboardVaccineOption(option) {
        setDashboardVaccineValue(option?.value || "");
        closeDashboardVaccineDropdown();
        elements.vaccineComboboxInput?.focus();
    }

    function syncDashboardVaccineComboboxFromSelect(fallbackLabel) {
        setDashboardVaccineValue(elements.vaccineName?.value || "", fallbackLabel);
    }

    function hasValidDashboardVaccineSelection() {
        return Boolean(
            elements.vaccineName?.value
            && selectedDashboardVaccineValue
            && elements.vaccineName.value === selectedDashboardVaccineValue
        );
    }

    function setDashboardVaccineDisabled(isDisabled) {
        const disabled = Boolean(isDisabled || !hasSelectableVaccines());
        if (elements.vaccineName) elements.vaccineName.disabled = disabled;
        if (elements.vaccineComboboxInput) elements.vaccineComboboxInput.disabled = disabled;
        if (elements.vaccineComboboxToggle) elements.vaccineComboboxToggle.disabled = disabled;
        if (disabled) closeDashboardVaccineDropdown();
    }

    function handleDashboardVaccineKeydown(event) {
        const isOpen = elements.vaccineComboboxInput?.getAttribute("aria-expanded") === "true";
        if (event.key === "ArrowDown") {
            event.preventDefault();
            if (!isOpen) {
                openDashboardVaccineDropdown();
                return;
            }
            setDashboardVaccineHighlight(highlightedDashboardVaccineIndex + 1);
            return;
        }
        if (event.key === "ArrowUp") {
            event.preventDefault();
            if (!isOpen) {
                openDashboardVaccineDropdown();
                return;
            }
            setDashboardVaccineHighlight(highlightedDashboardVaccineIndex - 1);
            return;
        }
        if (event.key === "Enter" && isOpen) {
            const option = filteredDashboardVaccineOptions[highlightedDashboardVaccineIndex];
            if (option) {
                event.preventDefault();
                selectDashboardVaccineOption(option);
            }
            return;
        }
        if (event.key === "Escape") {
            closeDashboardVaccineDropdown();
        }
    }

    function setupDashboardVaccineCombobox() {
        if (!elements.vaccineName || !elements.vaccineComboboxInput || !elements.vaccineComboboxList) return;
        dashboardVaccineOptions = buildDashboardVaccineOptions();
        syncDashboardVaccineComboboxFromSelect();
        setDashboardVaccineDisabled(!hasSelectableVaccines());

        elements.vaccineComboboxInput.addEventListener("focus", openDashboardVaccineDropdown);
        elements.vaccineComboboxInput.addEventListener("click", openDashboardVaccineDropdown);
        elements.vaccineComboboxInput.addEventListener("input", () => {
            selectedDashboardVaccineValue = "";
            if (elements.vaccineName) elements.vaccineName.value = "";
            renderDashboardVaccineOptions(elements.vaccineComboboxInput.value);
            setDashboardVaccineExpanded(true);
        });
        elements.vaccineComboboxInput.addEventListener("keydown", handleDashboardVaccineKeydown);

        elements.vaccineComboboxToggle?.addEventListener("click", () => {
            if (elements.vaccineComboboxInput?.getAttribute("aria-expanded") === "true") {
                closeDashboardVaccineDropdown();
                return;
            }
            elements.vaccineComboboxInput?.focus();
            openDashboardVaccineDropdown();
        });

        document.addEventListener("click", (event) => {
            if (!elements.vaccineCombobox?.contains(event.target)) {
                closeDashboardVaccineDropdown();
            }
        });
    }

    function setEditLockedFields(isEditing) {
        if (!elements.vaccineName || !elements.doseNumber || !elements.status) return;
        setDashboardVaccineDisabled(!hasSelectableVaccines());
        elements.doseNumber.readOnly = false;
        elements.status.disabled = isEditing;
    }

    function resetBookingForm() {
        editingBookingId = null;
        elements.bookingForm?.reset();
        if (elements.bookingId) elements.bookingId.value = "";
        if (elements.formHeading) elements.formHeading.textContent = "Táº¡o lá»‹ch háº¹n má»›i";
        if (elements.formSubtitle) elements.formSubtitle.textContent = "ThÃ´ng tin sáº½ Ä‘Æ°á»£c gá»­i sang quy trÃ¬nh xÃ¡c nháº­n.";
        if (elements.submitBookingBtn) elements.submitBookingBtn.textContent = "Táº¡o lá»‹ch háº¹n";
        if (elements.cancelEditBtn) elements.cancelEditBtn.hidden = true;
        if (elements.fullName) elements.fullName.value = defaultBookingValues.fullName;
        if (elements.phone) elements.phone.value = defaultBookingValues.phone;
        if (elements.email) elements.email.value = defaultBookingValues.email;
        if (elements.vaccineName) elements.vaccineName.value = "";
        syncDashboardVaccineComboboxFromSelect();
        if (elements.vaccineDate) elements.vaccineDate.value = "";
        if (elements.doseNumber) elements.doseNumber.value = "1";
        if (elements.status) elements.status.value = "pending";
        if (elements.note) elements.note.value = "";
        hideAlert(elements.bookingAlert);
        setEditLockedFields(false);
    }

    function collectBookingPayload() {
        const payload = {
            full_name: elements.fullName?.value.trim() || "",
            phone: elements.phone?.value.trim() || "",
            email: elements.email?.value.trim() || "",
            vaccine_name: elements.vaccineName?.value || "",
            vaccine_date: elements.vaccineDate?.value || "",
            dose_number: parseInt(elements.doseNumber?.value || "1", 10),
            status: elements.status?.value || "pending",
            note: elements.note?.value.trim() || "",
        };

        if (editingBookingId) {
            return {
                phone: payload.phone,
                vaccine_name: payload.vaccine_name,
                vaccine_date: payload.vaccine_date,
                dose_number: payload.dose_number,
                note: payload.note,
            };
        }

        if (!hasValidDashboardVaccineSelection()) {
            throw new Error("Vui lÃ²ng chá»n váº¯c xin tá»« danh sÃ¡ch.");
        }
        return payload;
    }

    function startEditBooking(booking) {
        editingBookingId = booking.id;
        if (elements.bookingId) elements.bookingId.value = String(booking.id);
        if (elements.fullName) elements.fullName.value = booking.full_name || "";
        if (elements.phone) elements.phone.value = booking.phone || "";
        if (elements.email) elements.email.value = booking.email || "";
        if (elements.vaccineName) elements.vaccineName.value = booking.vaccine_name || vaccineOptions[0] || "";
        syncDashboardVaccineComboboxFromSelect(booking.vaccine_name || "");
        if (elements.vaccineDate) elements.vaccineDate.value = booking.vaccine_date || "";
        if (elements.doseNumber) elements.doseNumber.value = booking.dose_number || 1;
        if (elements.status) elements.status.value = booking.status || "pending";
        if (elements.note) elements.note.value = booking.note || "";
        if (elements.formHeading) elements.formHeading.textContent = "Cáº­p nháº­t lá»‹ch háº¹n";
        if (elements.formSubtitle) elements.formSubtitle.textContent = "Báº¡n Ä‘ang chá»‰nh sá»­a lá»‹ch háº¹n Ä‘Ã£ táº¡o.";
        if (elements.submitBookingBtn) elements.submitBookingBtn.textContent = "LÆ°u thay Ä‘á»•i";
        if (elements.cancelEditBtn) elements.cancelEditBtn.hidden = false;
        hideAlert(elements.bookingAlert);
        setEditLockedFields(true);
        elements.bookingForm?.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function upsertBooking(booking) {
        const index = bookings.findIndex((item) => item.id === booking.id);
        if (index >= 0) bookings[index] = booking;
        else bookings.unshift(booking);
    }

    function updateBookingStats() {
        const counter = bookings.reduce(
            (accumulator, booking) => {
                accumulator.total += 1;
                accumulator.upcoming += booking.status !== "cancelled" && booking.vaccine_date >= config.today ? 1 : 0;
                if (booking.status in accumulator) accumulator[booking.status] += 1;
                return accumulator;
            },
            { total: 0, pending: 0, confirmed: 0, completed: 0, upcoming: 0 }
        );

        setText(document.getElementById("dashboard-stat-total"), counter.total);
        setText(document.getElementById("dashboard-stat-pending"), counter.pending);
        setText(document.getElementById("dashboard-stat-confirmed"), counter.confirmed);
        setText(document.getElementById("dashboard-stat-completed"), counter.completed);
        setText(document.getElementById("dashboard-upcoming-count"), counter.upcoming);
    }

    function renderBookingTable() {
        if (!elements.bookingTableBody) return;
        clearNode(elements.bookingTableBody);
        if (elements.bookingEmpty) elements.bookingEmpty.hidden = bookings.length > 0;

        bookings.forEach((booking) => {
            const row = document.createElement("tr");

            const customerCell = document.createElement("td");
            const customerName = document.createElement("strong");
            const customerPhone = document.createElement("span");
            customerName.textContent = booking.full_name || "";
            customerPhone.textContent = booking.phone || "";
            customerCell.append(customerName, document.createElement("br"), customerPhone);

            const vaccineCell = document.createElement("td");
            vaccineCell.textContent = booking.vaccine_name || "";

            const dateCell = document.createElement("td");
            dateCell.textContent = formatDate(booking.vaccine_date);

            const doseCell = document.createElement("td");
            doseCell.textContent = "MÅ©i " + (booking.dose_number || 1);

            const statusCell = document.createElement("td");
            const badge = document.createElement("span");
            badge.className = "status-badge status-" + safeStatusClass(booking.status);
            badge.textContent = statusLabels[booking.status] || booking.status || "";
            statusCell.appendChild(badge);

            const noteCell = document.createElement("td");
            noteCell.textContent = booking.note || "KhÃ´ng cÃ³";

            const actionCell = document.createElement("td");
            const actions = document.createElement("div");
            actions.className = "row-actions";
            if (booking.status !== "cancelled") {
                actions.appendChild(makeButton(booking.status === "ready_to_inject" || booking.status === "completed" ? "Xem sÃ ng lá»c" : "Khai bÃ¡o", "screening", booking.id));
            }
            if (booking.can_edit) actions.appendChild(makeButton("Sá»­a", "edit", booking.id));
            if (booking.can_reschedule) actions.appendChild(makeButton("Äáº·t láº¡i lá»‹ch", "reschedule", booking.id));
            if (booking.can_cancel) actions.appendChild(makeButton("Há»§y lá»‹ch", "cancel", booking.id, "is-danger"));
            actionCell.appendChild(actions);

            row.append(customerCell, vaccineCell, dateCell, doseCell, statusCell, noteCell, actionCell);
            elements.bookingTableBody.appendChild(row);
        });

        updateBookingStats();
    }

    function syncScreeningFromBooking(booking) {
        const existing = screeningBookings.find((item) => item.id === booking.id);
        const declaration = booking.pre_screening || existing?.declaration || null;
        const nextItem = {
            id: booking.id,
            vaccine_name: booking.vaccine_name,
            vaccine_date: booking.vaccine_date,
            dose_number: booking.dose_number,
            status: booking.status,
            status_label: statusLabels[booking.status] || booking.status,
            can_declare: !declarationClosedStatuses.has(booking.status),
            declaration,
            online_review: booking.online_review || existing?.online_review || null,
            screening_result: existing?.screening_result || null,
        };

        if (existing) {
            Object.assign(existing, nextItem);
            if (currentScreeningBooking && currentScreeningBooking.id === booking.id) {
                currentScreeningBooking = existing;
            }
        } else {
            screeningBookings.push(nextItem);
        }
    }

    function syncScreeningFromBookings(nextBookings) {
        nextBookings.forEach(syncScreeningFromBooking);
        screeningBookings.sort((left, right) => {
            if (left.vaccine_date === right.vaccine_date) return right.id - left.id;
            return left.vaccine_date > right.vaccine_date ? 1 : -1;
        });
        renderScreeningList();
        renderScreeningDetails();
    }

    async function loadBookings() {
        const query = new URLSearchParams();
        const keyword = elements.filterKeyword?.value.trim();
        const status = elements.filterStatus?.value;
        const date = elements.filterDate?.value;
        if (keyword) query.set("q", keyword);
        if (status) query.set("status", status);
        if (date) query.set("date", date);

        const suffix = query.toString() ? "?" + query.toString() : "";
        const response = await fetch("/booking/" + suffix, { credentials: "same-origin" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(parseApiError(data, "KhÃ´ng thá»ƒ táº£i danh sÃ¡ch lá»‹ch háº¹n."));
        bookings = Array.isArray(data) ? data : [];
        syncScreeningFromBookings(bookings);
        renderBookingTable();
    }

    async function saveBooking(payload) {
        const isEditing = Boolean(editingBookingId);
        const response = await fetch(isEditing ? "/booking/" + editingBookingId + "/" : "/booking/", {
            method: isEditing ? "PATCH" : "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken(),
            },
            body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(parseApiError(data, "KhÃ´ng thá»ƒ lÆ°u lá»‹ch háº¹n."));

        upsertBooking(data);
        syncScreeningFromBooking(data);
        renderBookingTable();
        renderScreeningList();
        resetBookingForm();
        showAlert(elements.bookingAlert, isEditing ? "Cáº­p nháº­t lá»‹ch háº¹n thÃ nh cÃ´ng." : "Táº¡o lá»‹ch háº¹n thÃ nh cÃ´ng.", false);
        loadBookings().catch((error) => console.warn(error));
    }

    async function cancelBooking(bookingId) {
        const response = await fetch("/booking/" + bookingId + "/", {
            method: "PATCH",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken(),
            },
            body: JSON.stringify({ status: "cancelled" }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(parseApiError(data, "KhÃ´ng thá»ƒ há»§y lá»‹ch háº¹n."));
        upsertBooking(data);
        syncScreeningFromBooking(data);
        renderBookingTable();
        renderScreeningList();
    }

    function findVaccineOption(vaccineTitle) {
        if (!elements.vaccineName) return null;
        const options = Array.from(elements.vaccineName.options).filter((option) => option.value);
        const normalizedTitle = normalizeText(vaccineTitle);
        const directMatch = options.find((option) => {
            const optionName = normalizeText(option.value);
            return normalizedTitle.includes(optionName) || optionName.includes(normalizedTitle);
        });
        if (directMatch) return directMatch;

        const tokens = normalizedTitle.split(" ").filter((token) => token.length >= 3 && token !== "vac" && token !== "xin");
        return options.find((option) => {
            const optionName = normalizeText(option.value);
            return tokens.some((token) => optionName.includes(token));
        }) || null;
    }

    function openAppointmentForVaccine(vaccineTitle) {
        switchTab("appointments", { scroll: true });
        resetBookingForm();
        const matchedOption = findVaccineOption(vaccineTitle);
        if (matchedOption && elements.vaccineName) {
            setDashboardVaccineValue(matchedOption.value);
            showAlert(elements.bookingAlert, "ÄÃ£ chá»n " + matchedOption.value + ". Chá»n ngÃ y tiÃªm Ä‘á»ƒ hoÃ n táº¥t lá»‹ch háº¹n.", false);
            elements.vaccineDate?.focus();
        } else {
            showAlert(elements.bookingAlert, "ChÆ°a tÃ¬m tháº¥y váº¯c xin tÆ°Æ¡ng á»©ng trong kho. Vui lÃ²ng chá»n váº¯c xin cÃ²n hÃ ng trong danh sÃ¡ch.", true);
            elements.vaccineComboboxInput?.focus();
        }
    }

    function openRescheduleModal(bookingId) {
        const booking = bookings.find((item) => String(item.id) === String(bookingId));
        if (!elements.rescheduleModal || !elements.rescheduleDate) return;
        reschedulingBookingId = bookingId;
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        elements.rescheduleDate.min = tomorrow.toISOString().split("T")[0];
        elements.rescheduleDate.value = "";
        setText(elements.rescheduleInfo, booking ? booking.vaccine_name + " - ngÃ y cÅ© " + formatDate(booking.vaccine_date) : "Chá»n ngÃ y tiÃªm má»›i cho lá»‹ch nÃ y.");
        elements.rescheduleModal.hidden = false;
        elements.rescheduleModal.classList.add("is-open");
    }

    function closeRescheduleModal() {
        reschedulingBookingId = null;
        if (!elements.rescheduleModal) return;
        elements.rescheduleModal.classList.remove("is-open");
        elements.rescheduleModal.hidden = true;
    }

    async function submitReschedule() {
        const newDate = elements.rescheduleDate?.value;
        if (!reschedulingBookingId || !newDate) {
            window.alert("Vui lÃ²ng chá»n ngÃ y tiÃªm má»›i.");
            return;
        }

        const response = await fetch("/api/medical/" + reschedulingBookingId + "/reschedule/", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken(),
            },
            body: JSON.stringify({ vaccine_date: newDate }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(parseApiError(data, "KhÃ´ng thá»ƒ Ä‘áº·t láº¡i lá»‹ch."));

        upsertBooking(data);
        syncScreeningFromBooking(data);
        renderBookingTable();
        renderScreeningList();
        closeRescheduleModal();
        showAlert(elements.bookingAlert, "Äáº·t láº¡i lá»‹ch thÃ nh cÃ´ng. Lá»‹ch má»›i Ä‘Ã£ Ä‘Æ°á»£c thÃªm vÃ o danh sÃ¡ch.", false);
        loadBookings().catch((error) => console.warn(error));
    }

    function bindBooking() {
        elements.bookingForm?.addEventListener("submit", async (event) => {
            event.preventDefault();
            hideAlert(elements.bookingAlert);
            try {
                await saveBooking(collectBookingPayload());
            } catch (error) {
                showAlert(elements.bookingAlert, error.message || "KhÃ´ng thá»ƒ lÆ°u lá»‹ch háº¹n.", true);
            }
        });

        elements.cancelEditBtn?.addEventListener("click", resetBookingForm);
        elements.filterBtn?.addEventListener("click", () => {
            loadBookings().catch((error) => showAlert(elements.bookingAlert, error.message, true));
        });
        [elements.filterKeyword, elements.filterStatus, elements.filterDate].forEach((filter) => {
            filter?.addEventListener("keydown", (event) => {
                if (event.key === "Enter") {
                    event.preventDefault();
                    loadBookings().catch((error) => showAlert(elements.bookingAlert, error.message, true));
                }
            });
        });

        elements.bookingTableBody?.addEventListener("click", async (event) => {
            const button = event.target.closest("button[data-action]");
            if (!button) return;
            const bookingId = Number(button.dataset.id);
            const booking = bookings.find((item) => item.id === bookingId);
            if (!booking) return;

            if (button.dataset.action === "edit") {
                startEditBooking(booking);
                return;
            }
            if (button.dataset.action === "screening") {
                switchTab("screening", { scroll: true });
                selectScreeningBooking(bookingId, { fetchLatest: true });
                return;
            }
            if (button.dataset.action === "reschedule") {
                openRescheduleModal(bookingId);
                return;
            }
            if (button.dataset.action === "cancel") {
                if (!window.confirm("Báº¡n cháº¯c cháº¯n muá»‘n há»§y lá»‹ch háº¹n nÃ y?")) return;
                try {
                    await cancelBooking(bookingId);
                    showAlert(elements.bookingAlert, "ÄÃ£ há»§y lá»‹ch háº¹n thÃ nh cÃ´ng.", false);
                } catch (error) {
                    showAlert(elements.bookingAlert, error.message || "KhÃ´ng thá»ƒ há»§y lá»‹ch háº¹n.", true);
                }
            }
        });

        elements.rescheduleCancel?.addEventListener("click", closeRescheduleModal);
        elements.rescheduleSubmit?.addEventListener("click", async () => {
            try {
                await submitReschedule();
            } catch (error) {
                window.alert(error.message || "KhÃ´ng thá»ƒ Ä‘áº·t láº¡i lá»‹ch.");
            }
        });

        resetBookingForm();
        renderBookingTable();
        loadBookings().catch((error) => console.warn(error));
    }

    function canDeclare(status) {
        return !declarationClosedStatuses.has(status);
    }

    function getDeclarationLabel(booking) {
        if (booking.screening_result) {
            const decision = booking.screening_result.decision;
            if (decision === "eligible") return "Đã khám tại quầy - đủ điều kiện tiêm";
            if (decision === "delayed") return "Đã khám tại quầy - tạm hoãn tiêm";
            if (decision === "cancelled") return "Đã khám tại quầy - chống chỉ định";
            return booking.screening_result.is_eligible
                ? "Đã có kết quả sàng lọc tại quầy"
                : "Đã có kết quả cần theo dõi thêm";
        }
        if (booking.online_review) {
            if (booking.online_review.decision === "eligible") return "Đã được bác sĩ duyệt online";
            if (booking.online_review.decision === "delayed") return "Bác sĩ đã tạm hoãn lịch này";
            if (booking.online_review.decision === "ineligible") return "Bác sĩ kết luận không đủ điều kiện tiêm";
        }
        if (booking.declaration) return "Đã gửi khai báo trước tiêm";
        return "Chưa khai báo";
    }

    function renderScreeningList() {
        if (!elements.screeningList) return;
        clearNode(elements.screeningList);

        if (!screeningBookings.length) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Bạn chưa có lịch tiêm nào để khai báo y tế.";
            elements.screeningList.appendChild(empty);
            return;
        }

        screeningBookings.forEach((booking) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "screening-booking-card" + (currentScreeningBooking && currentScreeningBooking.id === booking.id ? " is-active" : "");

            const title = document.createElement("strong");
            title.textContent = booking.vaccine_name || "";
            const date = document.createElement("small");
            date.textContent = "Ngày tiêm: " + formatDate(booking.vaccine_date);
            const meta = document.createElement("span");
            meta.textContent = "Mũi " + (booking.dose_number || 1) + " - " + (booking.status_label || statusLabels[booking.status] || booking.status);
            const declaration = document.createElement("span");
            declaration.textContent = getDeclarationLabel(booking);

            button.append(title, date, meta, declaration);
            button.addEventListener("click", () => selectScreeningBooking(booking.id, { fetchLatest: true }));
            elements.screeningList.appendChild(button);
        });
    }

    function setScreeningNotice(message, type) {
        if (!elements.screeningNotice) return;
        elements.screeningNotice.hidden = false;
        elements.screeningNotice.textContent = message;
        elements.screeningNotice.className = "dashboard-alert " + (type || "");
    }

    function fillScreeningForm(declaration) {
        fillDeclarationFields(declaration);
        if (elements.declarationNote) elements.declarationNote.value = declaration?.note || "";
    }

    function setScreeningFormEnabled(enabled) {
        elements.screeningForm?.querySelectorAll("input, textarea, button").forEach((item) => {
            item.disabled = !enabled;
        });
        if (elements.screeningResetBtn) elements.screeningResetBtn.disabled = !enabled;
    }

    function renderScreeningDetails() {
        if (!currentScreeningBooking) {
            if (elements.screeningDetail) elements.screeningDetail.hidden = true;
            if (elements.onlineReview) elements.onlineReview.hidden = true;
            if (elements.screeningResult) elements.screeningResult.hidden = true;
            if (elements.screeningEmpty) elements.screeningEmpty.hidden = false;
            return;
        }

        if (elements.screeningEmpty) elements.screeningEmpty.hidden = true;
        if (elements.screeningDetail) elements.screeningDetail.hidden = false;
        hideAlert(elements.screeningNotice);

        setText(elements.screeningTitle, "Khai báo y tế cho " + currentScreeningBooking.vaccine_name);
        setText(elements.screeningDescription, "Bạn cần hoàn tất khai báo để bác sĩ duyệt online trước khi chuyển sang bước đặt cọc.");
        if (elements.screeningStatus) {
            elements.screeningStatus.textContent = currentScreeningBooking.status_label || statusLabels[currentScreeningBooking.status] || currentScreeningBooking.status;
            elements.screeningStatus.className = "status-pill status-" + safeStatusClass(currentScreeningBooking.status);
        }
        setText(elements.screeningDate, formatDate(currentScreeningBooking.vaccine_date));
        setText(elements.screeningVaccine, currentScreeningBooking.vaccine_name);
        setText(elements.screeningDose, "Mũi " + (currentScreeningBooking.dose_number || 1));
        setText(elements.screeningDeclaration, getDeclarationLabel(currentScreeningBooking));
        fillScreeningForm(currentScreeningBooking.declaration);
        setScreeningFormEnabled(Boolean(currentScreeningBooking.can_declare));

        if (!currentScreeningBooking.can_declare) {
            setScreeningNotice("Lịch này không còn mở để cập nhật khai báo thêm. Bạn vẫn có thể xem kết luận đã được cập nhật.", "is-warning");
        }

        if (elements.onlineReview) {
            if (currentScreeningBooking.online_review) {
                elements.onlineReview.hidden = false;
                setText(elements.onlineReviewSummary, getOnlineReviewSummary(currentScreeningBooking.online_review));
                const review = currentScreeningBooking.online_review;
                const meta = [review.reviewed_by_name, review.reviewed_at ? `Cập nhật ${new Date(review.reviewed_at).toLocaleString("vi-VN")}` : "", review.doctor_note || ""].filter(Boolean).join(" • ");
                setText(elements.onlineReviewMeta, meta || "Chưa có ghi chú thêm từ bác sĩ.");
            } else {
                elements.onlineReview.hidden = true;
            }
        }

        if (currentScreeningBooking.screening_result) {
            const result = currentScreeningBooking.screening_result;
            if (elements.screeningResult) elements.screeningResult.hidden = false;
            let summary = "";
            if (result.decision === "eligible") {
                summary = "Bác sĩ tại quầy đánh giá bạn đủ điều kiện tiếp tục quy trình tiêm.";
            } else if (result.decision === "delayed") {
                summary = "Bác sĩ tại quầy đánh giá cần tạm hoãn tiêm. Vui lòng đặt lại lịch mới.";
            } else if (result.decision === "cancelled") {
                summary = "Bác sĩ tại quầy xác nhận có chống chỉ định tiêm.";
            } else {
                summary = result.is_eligible
                    ? "Bác sĩ tại quầy đánh giá bạn đủ điều kiện tiếp tục quy trình tiêm."
                    : "Bác sĩ tại quầy đánh giá cần theo dõi thêm hoặc tạm hoãn tiêm.";
            }
            setText(elements.resultSummary, summary);
            setText(elements.resultTemperature, result.temperature ? result.temperature + "°C" : "");
            setText(elements.resultBloodPressure, result.blood_pressure || "");
            setText(elements.resultNote, result.doctor_note || "Chưa có ghi chú thêm từ bác sĩ tại quầy.");
        } else if (elements.screeningResult) {
            elements.screeningResult.hidden = true;
        }
    }

    async function refreshScreeningSnapshot(bookingId) {
        const booking = screeningBookings.find((item) => String(item.id) === String(bookingId));
        if (!booking) return;
        try {
            const response = await fetch("/api/medical/pre-screening/" + bookingId + "/", { credentials: "same-origin" });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) return;
            booking.declaration = data.declaration || null;
            booking.online_review = data.online_review || null;
            booking.screening_result = data.screening_result || null;
            booking.can_declare = canDeclare(booking.status);
            if (currentScreeningBooking && String(currentScreeningBooking.id) === String(bookingId)) {
                currentScreeningBooking = booking;
                renderScreeningList();
                renderScreeningDetails();
            }
        } catch (error) {
            console.warn(error);
        }
    }

    function selectScreeningBooking(bookingId, options) {
        currentScreeningBooking = screeningBookings.find((item) => String(item.id) === String(bookingId)) || null;
        renderScreeningList();
        renderScreeningDetails();
        if (currentScreeningBooking && options?.fetchLatest) {
            refreshScreeningSnapshot(bookingId);
        }
    }

    function collectScreeningPayload() {
        return {
            ...collectDeclarationFields(),
            note: elements.declarationNote?.value.trim() || "",
        };
    }

    function bindScreening() {
        renderScreeningList();

        const initialScreeningId = config.selectedScreeningBookingId || screeningBookings[0]?.id;
        if (initialScreeningId) {
            selectScreeningBooking(initialScreeningId, { fetchLatest: true });
        } else {
            renderScreeningDetails();
        }

        elements.screeningForm?.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!currentScreeningBooking || !currentScreeningBooking.can_declare) return;

            const initialLabel = elements.screeningSaveBtn?.textContent || "LÆ°u khai bÃ¡o";
            if (elements.screeningSaveBtn) {
                elements.screeningSaveBtn.disabled = true;
                elements.screeningSaveBtn.textContent = "Äang lÆ°u...";
            }

            try {
                const response = await fetch("/api/medical/pre-screening/" + currentScreeningBooking.id + "/", {
                    method: currentScreeningBooking.declaration ? "PATCH" : "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCSRFToken(),
                    },
                    body: JSON.stringify(collectScreeningPayload()),
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(parseApiError(data, "KhÃ´ng thá»ƒ lÆ°u khai bÃ¡o sÃ ng lá»c."));

                currentScreeningBooking.declaration = {
                    has_fever: Boolean(data.has_fever),
                    has_allergy_history: Boolean(data.has_allergy_history),
                    has_chronic_condition: Boolean(data.has_chronic_condition),
                    recent_symptoms: data.recent_symptoms || "",
                    current_medications: data.current_medications || "",
                    has_severe_allergy: Boolean(data.has_severe_allergy),
                    severe_allergy_details: data.severe_allergy_details || "",
                    has_current_health_issue: Boolean(data.has_current_health_issue),
                    current_health_issue_details: data.current_health_issue_details || "",
                    had_recent_vaccination: Boolean(data.had_recent_vaccination),
                    recent_vaccination_details: data.recent_vaccination_details || "",
                    uses_immunosuppressive_medication: Boolean(data.uses_immunosuppressive_medication),
                    immunosuppressive_medication_details: data.immunosuppressive_medication_details || "",
                    has_pregnancy_or_breastfeeding_consideration: Boolean(data.has_pregnancy_or_breastfeeding_consideration),
                    pregnancy_or_breastfeeding_details: data.pregnancy_or_breastfeeding_details || "",
                    note: data.note || "",
                    updated_at: data.updated_at || "",
                };
                await loadBookings();
                selectScreeningBooking(currentScreeningBooking.id, { fetchLatest: true });
                setScreeningNotice("Đã lưu khai báo y tế thành công.", "is-success");
            } catch (error) {
                setScreeningNotice(error.message || "KhÃ´ng thá»ƒ lÆ°u khai bÃ¡o sÃ ng lá»c.", "is-warning");
            } finally {
                if (elements.screeningSaveBtn) {
                    elements.screeningSaveBtn.disabled = false;
                    elements.screeningSaveBtn.textContent = initialLabel;
                }
            }
        });

        elements.screeningResetBtn?.addEventListener("click", () => {
            if (!currentScreeningBooking) return;
            fillScreeningForm(currentScreeningBooking.declaration);
            hideAlert(elements.screeningNotice);
        });
    }

    bindTabs();
    bindLogout();
    bindHeroSlider();
    bindSeasonalTabs();
    setupDashboardVaccineCombobox();
    setupScreeningQuestionGroup();
    bindBooking();
    syncScreeningFromBookings(bookings);
    bindScreening();
})();










