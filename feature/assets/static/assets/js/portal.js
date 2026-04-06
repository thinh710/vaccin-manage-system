(function () {
    const items = document.querySelectorAll(".portal-hero, .portal-stat, .portal-card");

    items.forEach(function (item, index) {
        window.setTimeout(function () {
            item.classList.add("is-visible");
        }, index * 80);
    });
})();
