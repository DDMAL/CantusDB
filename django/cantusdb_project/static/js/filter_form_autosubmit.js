/*
 * Instant filtering for list/search filter forms (#2218).
 *
 * Radio buttons and dropdowns are "pick one and you're done" controls, so
 * having to click "Apply" afterwards is surprising — the filter is expected to
 * take effect as soon as the choice is made.
 *
 * Only those single-choice controls submit on their own. Text inputs are left
 * alone (people expect to finish typing first), and so are checkbox groups,
 * where reloading between each toggle would get in the way of picking several.
 * The "Apply" button therefore stays: it is what submits those fields, and it
 * is the fallback when JavaScript is unavailable.
 *
 * Opt a form in with `data-instant-filter` on the <form>. A control may carry
 * `data-autosubmit-requires="<selector>"` to hold off until the companion
 * field it qualifies has something in it — used for the operator dropdowns
 * ("Contains" / "Starts with"), which mean nothing on their own.
 */
(function () {
    "use strict";

    const INSTANT_SELECTOR = 'input[type="radio"], select';

    function isRadio(element) {
        return element.tagName === "INPUT" && element.type === "radio";
    }

    function shouldSubmit(form, control) {
        if (!control.matches || !control.matches(INSTANT_SELECTOR)) {
            return false;
        }
        const companionSelector = control.dataset.autosubmitRequires;
        if (companionSelector) {
            const companion = form.querySelector(companionSelector);
            if (!companion || !companion.value.trim()) {
                return false;
            }
        }
        return true;
    }

    function enableInstantFilter(form) {
        // Navigation has already started by the time a second change event
        // could arrive, so ignore everything after the first submission. This
        // also covers dropdowns that fire change both natively and via jQuery.
        let submitted = false;
        // Set while the arrow keys are walking a radio group (see below).
        let arrowKeyNavigating = false;
        let deferredRadio = null;

        function submitForm() {
            if (submitted) {
                return;
            }
            submitted = true;
            if (typeof form.requestSubmit === "function") {
                form.requestSubmit();
            } else {
                form.submit();
            }
        }

        function handleChange(event) {
            if (submitted || !shouldSubmit(form, event.target)) {
                return;
            }
            // Arrow keys move through a radio group one option at a time,
            // firing a change event at every stop. Submitting on each of those
            // would make the group impossible to traverse with the keyboard,
            // so wait for the choice to settle — the browser submits on Enter,
            // and focus leaving the group is handled below.
            if (arrowKeyNavigating && isRadio(event.target)) {
                deferredRadio = event.target;
                return;
            }
            submitForm();
        }

        form.addEventListener("keydown", function (event) {
            arrowKeyNavigating = event.key.indexOf("Arrow") === 0;
        });
        form.addEventListener("pointerdown", function () {
            arrowKeyNavigating = false;
        });

        form.addEventListener("focusout", function (event) {
            const movingTo = event.relatedTarget;
            if (
                !deferredRadio ||
                (movingTo &&
                    isRadio(movingTo) &&
                    movingTo.name === deferredRadio.name)
            ) {
                return;
            }
            submitForm();
        });

        form.addEventListener("change", handleChange);

        // Select2-backed dropdowns (django-autocomplete-light) fire their
        // change event through jQuery, which native listeners never see.
        if (window.jQuery) {
            window.jQuery(form).on("change", handleChange);
        }
    }

    // Deliberately on "load" rather than "DOMContentLoaded": widgets that
    // initialise themselves earlier can fire a change event while setting up
    // their initial value, and binding afterwards keeps those out of the way.
    window.addEventListener("load", function () {
        document
            .querySelectorAll("form[data-instant-filter]")
            .forEach(enableInstantFilter);
    });
})();
