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
 * If the endpoint is unreachable, stalls, or JavaScript is unavailable, saving
 * is never blocked: the server still saves and surfaces a non-blocking warning
 * message.
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

    // How long to wait for the check before giving up on it. The check is a
    // convenience, not a gate: while it runs, the save buttons are disabled, so
    // a request that never settles would leave the user unable to save at all
    // -- the very thing #1681 asks us not to do.
    var VALIDATION_TIMEOUT_MS = 5000;

    /*
     * Settle as ``request`` does, or reject once the deadline passes, whichever
     * happens first; ``abort`` cancels the underlying request on the deadline.
     *
     * ``request`` must cover reading the response as well as making it: `fetch`
     * resolves as soon as the headers arrive, so a deadline that stopped there
     * would leave a stalled *body* to hang forever with the save buttons still
     * disabled.
     *
     * A result that arrives after the deadline is ignored, because the returned
     * promise has already rejected: the caller has moved on and must not act on
     * the late result a second time.
     */
    function withDeadline(request, abort) {
        return new Promise(function (resolve, reject) {
            var timer = setTimeout(function () {
                abort();
                reject(new Error("chant text validation timed out"));
            }, VALIDATION_TIMEOUT_MS);
            request.then(
                function (value) {
                    clearTimeout(timer);
                    resolve(value);
                },
                function (error) {
                    clearTimeout(timer);
                    reject(error);
                }
            );
        });
    }

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
        // The field values the last check was given, in the encoded form
        // ``collectBody()`` produces. A response only describes the text it was
        // sent, and the fields stay editable while it is in flight, so anything
        // that acts on the result -- the modal, the echoes, and above all the
        // acknowledgement -- first compares this with what the fields say now.
        // Comparing the values themselves rather than watching for edits also
        // catches the page's own helpers (the Cantus Index suggestion buttons,
        // for instance), which assign to `.value` without firing an input
        // event.
        var checkedBody = null;

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
            var controller =
                typeof AbortController === "undefined"
                    ? null
                    : new AbortController();
            checkedBody = collectBody();
            var request = fetch(validateUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                body: checkedBody,
                signal: controller ? controller.signal : undefined,
            }).then(function (response) {
                if (!response.ok) {
                    throw new Error("validation request failed");
                }
                return response.json();
            });
            withDeadline(request, function () {
                if (controller) {
                    controller.abort();
                }
            })
                .then(function (data) {
                    var problems = (data && data.problems) || [];
                    // Nothing to warn about, or the text moved on while the
                    // check was running and these problems no longer describe
                    // it. Either way, save without the acknowledgement flag:
                    // the server checks what it actually receives, so anything
                    // the user hasn't seen still reaches them as a warning.
                    if (!problems.length || collectBody() !== checkedBody) {
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
                    // Never block saving when the check can't be reached or
                    // takes too long. Submit without the acknowledgement flag,
                    // so the server's own non-blocking warning still reaches the
                    // user -- they never saw a dialog to acknowledge.
                    submitForm(false);
                });
        });

        if (saveAnywayBtn) {
            saveAnywayBtn.addEventListener("click", function () {
                bsModal.hide();
                // The fields are still editable behind the dialog. Acknowledge
                // only the warning the user was actually shown: if the text has
                // changed since, drop the markings and save unacknowledged, so
                // the server warns about the text it receives.
                var acknowledged = collectBody() === checkedBody;
                if (!acknowledged) {
                    clearMarks();
                }
                submitForm(acknowledged);
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
