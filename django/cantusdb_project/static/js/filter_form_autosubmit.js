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

    // How long keyboard input must pause before a choice made with it is
    // applied. Chromium resets dropdown type-ahead after one second, so a
    // shorter pause would submit a half-typed option name.
    const KEYBOARD_SETTLE_MS = 1000;

    // Keys that confirm the focused control's current choice.
    const CONFIRM_KEYS = ["Enter", " "];

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

    function isCheckable(control) {
        return control.type === "radio" || control.type === "checkbox";
    }

    function sameRadioGroup(a, b) {
        return Boolean(
            a && b &&
            a.type === "radio" && b.type === "radio" &&
            a.name === b.name && a.form === b.form
        );
    }

    function snapshotControls(form) {
        return Array.prototype.map.call(form.elements, function (control) {
            return {
                control: control,
                value: control.value,
                checked: control.checked,
            };
        });
    }

    function enableInstantFilter(form) {
        // Navigation has already started by the time a second change event
        // could arrive, so ignore everything after the first submission. This
        // also covers dropdowns that fire change both natively and via jQuery.
        let submitted = false;
        // A keyboard-made choice waiting to be applied (see handleChange).
        let pending = false;
        // Counts keyboard changes, so a delayed check can tell whether the
        // pending choice is still the one it was scheduled for.
        let pendingChoice = 0;
        let settleTimer = null;
        // The key whose default action is still running. A change event fired
        // while this is set was caused by that key on a closed control.
        let currentKey = null;
        let pointerDown = false;
        let pointerOpensList = false;
        let restoring = false;
        // The values that match this page's URL and results, after the page
        // scripts have restored them from the query string.
        const loadedState = snapshotControls(form);

        function submitForm() {
            if (submitted) {
                return;
            }
            submitted = true;
            pending = false;
            clearTimeout(settleTimer);
            if (typeof form.requestSubmit === "function") {
                form.requestSubmit();
            } else {
                form.submit();
            }
        }

        function waitForKeyboardToSettle() {
            pending = true;
            pendingChoice += 1;
            clearTimeout(settleTimer);
            settleTimer = setTimeout(submitForm, KEYBOARD_SETTLE_MS);
        }

        function handleChange(event) {
            if (restoring || submitted || !shouldSubmit(form, event.target)) {
                return;
            }
            // Arrow keys walk a radio group one option at a time. On a closed
            // dropdown, arrow keys and typed letters (type-ahead) also change
            // the value as they go, firing a change event at every stop.
            // Submitting on each of those would make the control impossible
            // to traverse with the keyboard, so wait until the keys stop.
            // Changes made with the mouse, or by confirming an option in an
            // open dropdown list, are final and apply immediately.
            if (currentKey !== null && CONFIRM_KEYS.indexOf(currentKey) === -1) {
                waitForKeyboardToSettle();
                return;
            }
            submitForm();
        }

        form.addEventListener("keydown", function (event) {
            if (pending && CONFIRM_KEYS.indexOf(event.key) !== -1) {
                // Apply the choice now rather than letting Enter open the
                // dropdown or Space do nothing.
                event.preventDefault();
                submitForm();
                return;
            }
            currentKey = event.key;
            setTimeout(function () {
                currentKey = null;
            }, 0);
            if (pending) {
                // Still choosing: keep waiting.
                waitForKeyboardToSettle();
            }
        });

        // Clicking a label blurs the focused control before the click selects
        // the label's radio. Hold a pending choice until the button is
        // released, so the submission includes what the click selected.
        form.addEventListener("pointerdown", function (event) {
            pointerDown = true;
            pointerOpensList = Boolean(
                event.target.closest && event.target.closest("select")
            );
            clearTimeout(settleTimer);
        });
        document.addEventListener("pointerup", function () {
            if (!pointerDown) {
                return;
            }
            pointerDown = false;
            if (pointerOpensList) {
                // Pressing on a dropdown opens its list. Picking an option
                // applies it; otherwise leaving the control or Enter does.
                return;
            }
            if (!pending) {
                return;
            }
            // The click, and the change it causes, are dispatched after
            // pointerup. If that change already submitted, this does nothing.
            // Only a choice already pending now is applied: browsers can run
            // input events before this timer, and a key pressed in between
            // starts its own wait.
            const choice = pendingChoice;
            setTimeout(function () {
                if (pending && pendingChoice === choice) {
                    submitForm();
                }
            }, 0);
        });

        // Leaving the control with Tab applies a pending keyboard choice
        // without waiting for the pause. An arrow key in a radio group moves
        // focus to the next radio before checking it; that move is a focusout
        // too, but stays within the choice being made.
        form.addEventListener("focusout", function (event) {
            if (!pending || pointerDown) {
                return;
            }
            if (sameRadioGroup(event.target, event.relatedTarget)) {
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

        // On Back, Chrome restores this page from the back/forward cache
        // without re-running "load". It keeps the choice that navigated away,
        // which no longer matches the restored URL and results, so choosing
        // that option again would fire no change event. Restore the values
        // the page loaded with, and clear the submission guard.
        window.addEventListener("pageshow", function (event) {
            if (!event.persisted) {
                return;
            }
            submitted = false;
            pending = false;
            pointerDown = false;
            currentKey = null;
            clearTimeout(settleTimer);
            restoring = true;
            try {
                loadedState.forEach(function (state) {
                    if (isCheckable(state.control)) {
                        state.control.checked = state.checked;
                    } else {
                        state.control.value = state.value;
                    }
                    if (window.jQuery && state.control.tagName === "SELECT") {
                        // Redraw a Select2 widget without notifying change
                        // listeners; plain dropdowns ignore this event.
                        window.jQuery(state.control).trigger("change.select2");
                    }
                });
            } finally {
                restoring = false;
            }
        });
    }

    // Deliberately on "load" rather than "DOMContentLoaded": widgets that
    // initialise themselves earlier can fire a change event while setting up
    // their initial value, and binding afterwards keeps those out of the way.
    // Page scripts restore their filters from the URL on "load" too, and are
    // included before this file, so their listeners run first.
    window.addEventListener("load", function () {
        document
            .querySelectorAll("form[data-instant-filter]")
            .forEach(enableInstantFilter);
    });
})();
