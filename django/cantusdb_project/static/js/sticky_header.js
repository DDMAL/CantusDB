document.addEventListener("DOMContentLoaded", function () {
    var stickyHeaderToggle = document.getElementById("sticky-navbar-toggle");
    var collapsingHeader = document.getElementById("collapsing-navbar");
    let lastScrollY = 0;

    window.addEventListener("scroll", function () {
        // if we scroll down below 80px, then collapse the header
        // and show the toggle button
        if (lastScrollY < 80 && window.scrollY >= 80) {
            stickyHeaderToggle.classList.remove("d-none");
        }
        // if we scroll up to the top, then remove the toggle button
        else if (window.scrollY < 80 && lastScrollY >= 80) {
            stickyHeaderToggle.classList.add("d-none");
            collapsingHeader.classList.remove("collapsing-navbar-show");
        }
        lastScrollY = window.scrollY;
    });

    stickyHeaderToggle.addEventListener("click", function () {
        collapsingHeader.classList.toggle("collapsing-navbar-show");
    });
});