(function () {
    const animatedItems = document.querySelectorAll(
        ".overview-hero, .summary-card, .feature-card"
    );

    animatedItems.forEach(function (item, index) {
        item.classList.add("reveal-on-load");
        item.style.animationDelay = index * 0.08 + "s";
    });
})();
