(function () {
    function getCsrfToken(form) {
        const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput) return csrfInput.value;
        const cookie = document.cookie
            .split('; ')
            .find((row) => row.startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

    function setMessage(box, text, type) {
        box.hidden = false;
        box.className = 'alert ' + type;
        box.textContent = text;
    }

    function normalizeError(payload) {
        if (!payload) return 'Có lỗi xảy ra. Vui lòng thử lại.';
        if (typeof payload === 'string') return payload;
        if (payload.detail) return payload.detail;

        const entries = [];
        Object.entries(payload).forEach(([key, value]) => {
            if (Array.isArray(value)) {
                entries.push(key + ': ' + value.join(', '));
            } else if (typeof value === 'string') {
                entries.push(key + ': ' + value);
            }
        });
        return entries.length ? entries.join(' | ') : 'Dữ liệu không hợp lệ.';
    }

    function bindPasswordToggles() {
        document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
            btn.addEventListener('click', function () {
                const target = document.querySelector(this.dataset.togglePassword);
                if (!target) return;
                const isPassword = target.type === 'password';
                target.type = isPassword ? 'text' : 'password';
                this.textContent = isPassword ? 'Ẩn' : 'Hiện';
            });
        });
    }

    async function submitForm({ form, messageBox, submitBtn, endpoint, successRedirect }) {
        const formData = new FormData(form);
        const payload = Object.fromEntries(formData.entries());

        submitBtn.disabled = true;
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Đang xử lý...';
        messageBox.hidden = true;

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(form),
                },
                body: JSON.stringify(payload),
            });

            let data = null;
            try {
                data = await response.json();
            } catch (error) {
                data = null;
            }

            if (!response.ok) {
                setMessage(messageBox, normalizeError(data), 'error');
                return;
            }

            setMessage(messageBox, data.message || 'Thành công.', 'success');
            if (successRedirect) {
                window.setTimeout(() => {
                    window.location.href = successRedirect;
                }, 700);
            }
        } catch (error) {
            setMessage(messageBox, 'Không kết nối được tới server.', 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    }

    function initLogin(config) {
        bindPasswordToggles();
        const form = document.getElementById(config.formId);
        const messageBox = document.getElementById(config.messageId);
        const submitBtn = document.getElementById(config.submitId);
        if (!form || !messageBox || !submitBtn) return;

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            submitForm({
                form,
                messageBox,
                submitBtn,
                endpoint: config.endpoint,
                successRedirect: config.successRedirect,
            });
        });
    }

    function initRegister(config) {
        bindPasswordToggles();
        const form = document.getElementById(config.formId);
        const messageBox = document.getElementById(config.messageId);
        const submitBtn = document.getElementById(config.submitId);
        if (!form || !messageBox || !submitBtn) return;

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            const password = form.querySelector('[name="password"]').value;
            const confirmPassword = form.querySelector('[name="confirm_password"]').value;
            if (password !== confirmPassword) {
                setMessage(messageBox, 'Mật khẩu xác nhận không khớp.', 'error');
                return;
            }
            submitForm({
                form,
                messageBox,
                submitBtn,
                endpoint: config.endpoint,
                successRedirect: config.successRedirect,
            });
        });
    }

    window.AuthPages = {
        initLogin,
        initRegister,
    };
})();
