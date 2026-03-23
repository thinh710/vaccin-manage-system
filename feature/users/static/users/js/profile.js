(function () {
    const avatarInput = document.getElementById('avatarFile');
    const avatarDataInput = document.getElementById('avatar_data');
    const removeAvatarInput = document.getElementById('remove_avatar');
    const avatarPreview = document.getElementById('avatarPreview');
    const removeAvatarBtn = document.getElementById('removeAvatarBtn');
    const fullNameInput = document.getElementById('full_name');

    function initialLetter() {
        const value = (fullNameInput?.value || 'U').trim();
        return value ? value.charAt(0).toUpperCase() : 'U';
    }

    function renderFallbackAvatar() {
        avatarPreview.innerHTML = '<div class="profile-avatar profile-avatar--large">' + initialLetter() + '</div>';
    }

    function renderImageAvatar(src) {
        avatarPreview.innerHTML = '<img class="profile-avatar-image profile-avatar-image--large" src="' + src + '" alt="Avatar">';
    }

    if (avatarInput) {
        avatarInput.addEventListener('change', function (event) {
            const file = event.target.files && event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function (loadEvent) {
                const result = loadEvent.target && loadEvent.target.result;
                if (!result || typeof result !== 'string') return;
                avatarDataInput.value = result;
                removeAvatarInput.value = '0';
                renderImageAvatar(result);
            };
            reader.readAsDataURL(file);
        });
    }

    if (removeAvatarBtn) {
        removeAvatarBtn.addEventListener('click', function () {
            avatarDataInput.value = '';
            removeAvatarInput.value = '1';
            if (avatarInput) {
                avatarInput.value = '';
            }
            renderFallbackAvatar();
        });
    }

    if (fullNameInput) {
        fullNameInput.addEventListener('input', function () {
            if (!avatarDataInput.value) {
                renderFallbackAvatar();
            }
        });
    }
})();
