/*
 * Client-side "Save anyway?" confirmation for invalid chant text (see #1681).
 *
 * When a chant create/edit form is submitted, the text fields are sent to the
 * `validate-chant-text` endpoint. If the server reports no problems, the form
 * submits normally. If it reports problems, a Bootstrap modal lists them (with
 * the offending characters marked), the affected fields are highlighted with a
 * marked echo below them, and the user can either go back and fix the text or
 * save anyway. Saving anyway re-submits with `confirm_invalid_text=1` so the
 * server knows the warning was acknowledged.
 *
 * An echo shows the text as it was when the check ran, so editing a field drops
 * that field's echo rather than leaving a stale marking on screen; submitting
 * again re-runs the check.
 *
 * If the endpoint is unreachable or JavaScript is unavailable, saving is never
 * blocked: the server still saves and surfaces a non-blocking warning message.
 */
(function () {
    "use strict";

    // Must stay in sync with the keys of ``CHANT_TEXT_FIELDS`` in
    // main_app/forms.py, which is the source of truth for which fields the
    // server checks. Only fields actually present on the page are sent.
    var FIELD_NAMES = [
        "manuscript_full_text_std_spelling",
        "manuscript_full_text",
        "manuscript_syllabized_full_text",
    ];

    function init() {
        var modalEl = document.getElementById("chant-text-warning-modal");
        if (!modalEl || typeof bootstrap === "undefined") {
            return;
        }

        // Find the chant form as the one containing a known text field.
        var form = null;
        for (var i = 0; i < FIELD_NAMES.length; i++) {
            var el = document.querySelector('[name="' + FIELD_NAMES[i] + '"]');
            if (el) {
                form = el.form || el.closest("form");
                break;
            }
        }
        if (!form) {
            return;
        }

        var validateUrl = modalEl.getAttribute("data-validate-url");
        var modalBody = document.getElementById("chant-text-warning-modal-body");
        var saveAnywayBtn = document.getElementById(
            "chant-text-warning-save-anyway"
        );
        var bsModal = new bootstrap.Modal(modalEl);
        var pendingSubmitter = null;
        var bypassValidation = false;
        var checkInFlight = false;

        function csrfToken() {
            var input = form.querySelector('[name="csrfmiddlewaretoken"]');
            return input ? input.value : "";
        }

        function escapeHtml(str) {
            var div = document.createElement("div");
            div.textContent = str == null ? "" : str;
            return div.innerHTML;
        }

        function eachField(callback) {
            FIELD_NAMES.forEach(function (name) {
                var field = form.querySelector('[name="' + name + '"]');
                if (field) {
                    callback(field, name);
                }
            });
        }

        // Keep the save buttons disabled while a check is in flight, so that
        // repeated clicks can't fire a request each.
        function setSubmitDisabled(disabled) {
            var buttons = form.querySelectorAll('[type="submit"]');
            for (var i = 0; i < buttons.length; i++) {
                buttons[i].disabled = disabled;
            }
        }

        function clearFieldMarks(name) {
            var field = form.querySelector('[name="' + name + '"]');
            if (field) {
                field.classList.remove("chant-text-warning-field");
            }
            var echo = form.querySelector(
                '.chant-text-warning-echo[data-field="' + name + '"]'
            );
            if (echo) {
                echo.remove();
            }
        }

        function clearMarks() {
            FIELD_NAMES.forEach(clearFieldMarks);
        }

        function renderInlineEchoes(problems) {
            clearMarks();
            // A field can have more than one problem (disallowed characters
            // *and* something structural), so gather them into one echo each.
            var byField = {};
            var order = [];
            problems.forEach(function (p) {
                if (!byField[p.field]) {
                    byField[p.field] = [];
                    order.push(p.field);
                }
                byField[p.field].push(p);
            });
            order.forEach(function (name) {
                var field = form.querySelector('[name="' + name + '"]');
                if (!field) {
                    return;
                }
                field.classList.add("chant-text-warning-field");
                var echo = document.createElement("div");
                echo.className = "chant-text-warning-echo small mt-1";
                echo.setAttribute("data-field", name);
                echo.innerHTML = byField[name]
                    .map(function (p) {
                        return (
                            "&#9888; " +
                            escapeHtml(p.message) +
                            '<div class="chant-text-warning-marked">' +
                            p.marked_html +
                            "</div>"
                        );
                    })
                    .join("");
                field.insertAdjacentElement("afterend", echo);
            });
        }

        function renderModal(problems) {
            if (!modalBody) {
                return;
            }
            var parts = [
                "<p>The text you entered may not syllabify or align with the " +
                    "melody correctly:</p>",
                '<ul class="chant-text-warning-list">',
            ];
            problems.forEach(function (p) {
                parts.push(
                    "<li><strong>" +
                        escapeHtml(p.label) +
                        "</strong> " +
                        escapeHtml(p.message) +
                        '<div class="chant-text-warning-marked mt-1">' +
                        p.marked_html +
                        "</div></li>"
                );
            });
            parts.push("</ul>");
            modalBody.innerHTML = parts.join("");
        }

        // Submit the form, bypassing this script's own interception.
        // ``acknowledged`` records whether the user actually saw and dismissed
        // the warning modal; it posts `confirm_invalid_text=1`, which tells the
        // server to skip its non-blocking warning message. When we submit for
        // any other reason -- nothing to warn about, or the validation request
        // failed -- we leave it unset so the server-side warning still fires.
        function submitForm(acknowledged) {
            var hidden = form.querySelector('[name="confirm_invalid_text"]');
            if (!hidden) {
                hidden = document.createElement("input");
                hidden.type = "hidden";
                hidden.name = "confirm_invalid_text";
                form.appendChild(hidden);
            }
            hidden.value = acknowledged ? "1" : "";
            // Release the guard before submitting: if the browser blocks the
            // submit on native constraint validation, the user is still on the
            // page and must be able to try again.
            checkInFlight = false;
            setSubmitDisabled(false);
            // Scoped to this one programmatic submit: the submit event fires
            // synchronously from requestSubmit(), so if the browser instead
            // blocks it on native constraint validation, the next attempt gets
            // validated again rather than silently skipping the check.
            bypassValidation = true;
            if (form.requestSubmit) {
                form.requestSubmit(pendingSubmitter || undefined);
            } else {
                form.submit();
            }
            bypassValidation = false;
        }

        function collectBody() {
            var params = new URLSearchParams();
            FIELD_NAMES.forEach(function (name) {
                var field = form.querySelector('[name="' + name + '"]');
                if (field) {
                    params.append(name, field.value);
                }
            });
            return params.toString();
        }

        form.addEventListener("submit", function (event) {
            if (bypassValidation) {
                return; // our own re-submit -> let it proceed
            }
            event.preventDefault();
            if (checkInFlight) {
                return; // a check is already running for this form
            }
            checkInFlight = true;
            setSubmitDisabled(true);
            pendingSubmitter = event.submitter || null;
            fetch(validateUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                body: collectBody(),
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("validation request failed");
                    }
                    return response.json();
                })
                .then(function (data) {
                    var problems = (data && data.problems) || [];
                    if (!problems.length) {
                        clearMarks();
                        submitForm(false);
                        return;
                    }
                    renderInlineEchoes(problems);
                    renderModal(problems);
                    checkInFlight = false;
                    setSubmitDisabled(false);
                    bsModal.show();
                })
                .catch(function () {
                    // Never block saving if validation can't be reached. Submit
                    // without the acknowledgement flag, so the server's own
                    // non-blocking warning still reaches the user -- they never
                    // saw a dialog to acknowledge.
                    submitForm(false);
                });
        });

        if (saveAnywayBtn) {
            saveAnywayBtn.addEventListener("click", function () {
                bsModal.hide();
                submitForm(true);
            });
        }

        // The echo shows the text as it was when the check last ran, so drop it
        // as soon as the user starts editing that field rather than leaving a
        // stale marking on screen. Submitting again re-runs the check.
        eachField(function (field, name) {
            field.addEventListener("input", function () {
                clearFieldMarks(name);
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
