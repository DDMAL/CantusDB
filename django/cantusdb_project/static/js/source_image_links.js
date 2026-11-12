"use strict";

document.querySelectorAll("[data-image-links]").forEach((fieldset) => {
    const rows = fieldset.querySelector("[data-image-link-rows]");
    const template = fieldset.querySelector("[data-image-link-template]");
    const total = fieldset.querySelector('input[name$="-TOTAL_FORMS"]');
    const addButton = fieldset.querySelector("[data-add-image-link]");
    addButton.hidden = false;
    addButton.addEventListener("click", () => {
        const index = Number(total.value);
        const fragment = template.content.cloneNode(true);
        fragment.querySelectorAll("[name], [id], [for], [aria-describedby]").forEach((element) => {
            for (const attr of ["name", "id", "for", "aria-describedby"]) {
                if (element.hasAttribute(attr)) {
                    element.setAttribute(attr, element.getAttribute(attr).replaceAll("__prefix__", index));
                }
            }
        });
        const input = fragment.querySelector('input[name$="-url"]');
        rows.append(fragment);
        total.value = index + 1;
        input.focus();
    });
});
