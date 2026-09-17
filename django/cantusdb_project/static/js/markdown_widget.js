var MarkdownWidget = (function () {
    // Apply a computed edit to the textarea. In the browser this routes through
    // execCommand("insertText") so the change joins the native undo stack — a
    // plain `textarea.value = ...` assignment wipes it, breaking Ctrl/Cmd+Z.
    // execCommand is deprecated but remains the only reliable way to preserve
    // native undo; we fall back to direct assignment when it's unavailable
    // (older browsers, and the Node unit tests, which have no `document`).
    function setValue(textarea, value, selectionStart, selectionEnd) {
        if (textarea.value !== value) {
            var applied = false;
            if (typeof document !== "undefined" && document.execCommand) {
                textarea.focus();
                textarea.select();
                applied = document.execCommand("insertText", false, value);
            }
            if (!applied) {
                textarea.value = value;
            }
        }
        textarea.selectionStart = selectionStart;
        textarea.selectionEnd = selectionEnd;
        textarea.focus();
    }

    // Toggle an emphasis marker around the selection, matching GitHub's
    // bold/italic buttons. Both buttons share one run of asterisks on each side
    // of the text — one asterisk is italic, two are bold, three are both — so
    // each button measures the whole run and then adds or removes only its own
    // asterisks, leaving the other button's alone. With nothing to mark, insert
    // the placeholder and select it so the user can type over it.
    function wrapInline(textarea, marker, placeholder) {
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        var value = textarea.value;
        var width = marker.length; // 1 for italic, 2 for bold

        // Markdown only applies a marker that sits flush against its text, so
        // keep whitespace at the edges of the selection outside the markers, as
        // GitHub does. A selection of nothing but whitespace has no text to
        // mark, so treat it as no selection at all.
        var selected = value.substring(start, end);
        var lead = /^\s*/.exec(selected)[0].length;
        if (lead === selected.length) {
            end = start;
        } else {
            start += lead;
            end -= /\s*$/.exec(selected)[0].length;
        }

        // Asterisks the user happened to select belong to the run rather than
        // to the text being marked, so step over those too.
        selected = value.substring(start, end);
        var leadStars = /^\**/.exec(selected)[0].length;
        start += leadStars;
        if (leadStars < selected.length) {
            end -= /\**$/.exec(selected)[0].length;
        } else {
            end = start; // the selection was nothing but asterisks
        }

        var text = value.substring(start, end);
        if (text === "") {
            setValue(
                textarea,
                value.substring(0, start) +
                    marker +
                    placeholder +
                    marker +
                    value.substring(end),
                start + width,
                start + width + placeholder.length
            );
            return;
        }

        // start/end now bracket the text exactly, so each side's run of
        // asterisks is whatever sits immediately beyond it.
        var before = /\**$/.exec(value.substring(0, start))[0].length;
        var after = /^\**/.exec(value.substring(end))[0].length;
        var run = Math.min(before, after);
        // An odd run carries italic; two or more carry bold.
        var applied = width === 1 ? run % 2 === 1 : run >= 2;
        var stars = "*".repeat(applied ? run - width : run + width);
        // Only consume the paired run. Extra asterisks on either side can
        // belong to formatting around a larger span of text.
        setValue(
            textarea,
            value.substring(0, start - run) +
                stars +
                text +
                stars +
                value.substring(end + run),
            start - run + stars.length,
            start - run + stars.length + text.length
        );
    }

    // Turn the selection into a markdown link. The URL is left selected so the
    // user can paste over it immediately.
    function insertLink(textarea) {
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        var value = textarea.value;
        var text = value.substring(start, end) || "text";
        var before = "[" + text + "](";
        var url = "url";
        setValue(
            textarea,
            value.substring(0, start) + before + url + ")" + value.substring(end),
            start + before.length,
            start + before.length + url.length
        );
    }

    // Toggle a line-level marker (heading, quote, list) across every line the
    // selection touches. If all lines already have it, strip it; otherwise
    // normalize and (re)apply so clicking twice never stacks markers. Each
    // line's indentation is held aside so markers toggle without flattening or
    // displacing the nesting level.
    function toggleLinePrefix(textarea, strip, marker) {
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        var value = textarea.value;
        var blockStart = value.lastIndexOf("\n", start - 1) + 1;
        var blockEnd = value.indexOf("\n", end);
        if (blockEnd === -1) {
            blockEnd = value.length;
        }
        var block = value.substring(blockStart, blockEnd);
        var lines = block.split("\n").map(function (line) {
            var indent = line.match(/^\s*/)[0];
            return { indent: indent, rest: line.substring(indent.length) };
        });
        var allMarked = lines.every(function (line) {
            return strip.test(line.rest);
        });
        var result = lines
            .map(function (line, i) {
                var bare = line.rest.replace(strip, "");
                return line.indent + (allMarked ? bare : marker(bare, i));
            })
            .join("\n");
        var newValue =
            value.substring(0, blockStart) + result + value.substring(blockEnd);
        if (start === end) {
            // A caret that arrived collapsed stays collapsed and keeps its place
            // in the text, as GitHub's buttons do. Selecting the whole line
            // instead would make the user's next keystroke replace it. With no
            // selection the block is just the caret's own line, so that line's
            // change in length is the offset to apply.
            var caret = Math.min(
                blockStart + result.length,
                Math.max(blockStart, start + result.length - block.length)
            );
            setValue(textarea, newValue, caret, caret);
            return;
        }
        setValue(textarea, newValue, blockStart, blockStart + result.length);
    }

    // Indent (or outdent, on Shift+Tab) every line the selection touches by one
    // level of two spaces, so Tab nests list items like GitHub.
    function indentLines(textarea, outdent) {
        var indent = "  ";
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        var value = textarea.value;
        var blockStart = value.lastIndexOf("\n", start - 1) + 1;
        var blockEnd = value.indexOf("\n", end);
        if (blockEnd === -1) {
            blockEnd = value.length;
        }
        var firstDelta = 0; // change before the caret on the first line
        var totalDelta = 0; // change before the selection end
        var newLines = value
            .substring(blockStart, blockEnd)
            .split("\n")
            .map(function (line, i) {
                var delta;
                if (outdent) {
                    var removed = (line.match(/^(\t| {1,2})/) || [""])[0].length;
                    line = line.slice(removed);
                    delta = -removed;
                } else {
                    line = indent + line;
                    delta = indent.length;
                }
                if (i === 0) {
                    firstDelta = delta;
                }
                totalDelta += delta;
                return line;
            });
        setValue(
            textarea,
            value.substring(0, blockStart) + newLines.join("\n") + value.substring(blockEnd),
            Math.max(blockStart, start + firstDelta),
            Math.max(blockStart, end + totalDelta)
        );
    }

    var actions = {
        heading: function (textarea) {
            toggleLinePrefix(textarea, /^#{1,6}\s+/, function (line) {
                return "# " + line;
            });
        },
        bold: function (textarea) {
            wrapInline(textarea, "**", "bold text");
        },
        italic: function (textarea) {
            wrapInline(textarea, "*", "italic text");
        },
        quote: function (textarea) {
            toggleLinePrefix(textarea, /^>\s?/, function (line) {
                return "> " + line;
            });
        },
        link: function (textarea) {
            insertLink(textarea);
        },
        "unordered-list": function (textarea) {
            toggleLinePrefix(textarea, /^[-*+]\s+/, function (line) {
                return "- " + line;
            });
        },
        "ordered-list": function (textarea) {
            toggleLinePrefix(textarea, /^\d+[.)]\s+/, function (line, i) {
                return i + 1 + ". " + line;
            });
        },
    };

    // Ctrl/Cmd shortcuts that mirror GitHub's markdown input.
    var shortcuts = { b: "bold", i: "italic", k: "link" };

    // Keys that only ever accompany another keystroke.
    var MODIFIER_KEYS = { Shift: true, Control: true, Meta: true, Alt: true };

    // Tab indents inside the textarea, so on its own it never moves focus and a
    // keyboard user cannot leave the field — a WCAG 2.1.2 keyboard trap. Escape
    // hands Tab back to the browser for one keypress, the way GitHub does.
    //
    // `released` is whether Escape has already been pressed and `key` is the key
    // just pressed. The returned `released` carries forward; `movesFocus` says
    // the browser should handle this Tab itself. Bare modifiers leave the state
    // alone because Shift+Tab reports the Shift press first; any other key means
    // the user went back to editing, so Tab indents again.
    function tabRelease(released, key) {
        if (key === "Escape") {
            return { released: true, movesFocus: false };
        }
        if (key === "Tab") {
            return { released: false, movesFocus: released };
        }
        return { released: released && !!MODIFIER_KEYS[key], movesFocus: false };
    }

    // Continuation markers for pressing Enter inside a list or blockquote.
    var continuations = [
        {
            re: /^(\s*)([-*+])(\s+)(.*)$/,
            next: function (m) {
                return m[1] + m[2] + m[3];
            },
            content: 4,
        },
        {
            re: /^(\s*)(\d+)([.)])(\s+)(.*)$/,
            next: function (m) {
                return m[1] + (parseInt(m[2], 10) + 1) + m[3] + m[4];
            },
            content: 5,
        },
        {
            re: /^((?:\s*>\s?)+)(.*)$/,
            next: function (m) {
                return m[1];
            },
            content: 2,
        },
    ];

    // On Enter, continue the current list/quote with the next marker. Pressing
    // Enter on an empty item removes the marker and exits the list, matching
    // GitHub. Returns true when handled so the caller suppresses the newline.
    function continueList(textarea) {
        var start = textarea.selectionStart;
        if (start !== textarea.selectionEnd) {
            return false;
        }
        var value = textarea.value;
        var lineStart = value.lastIndexOf("\n", start - 1) + 1;
        var line = value.substring(lineStart, start);
        for (var i = 0; i < continuations.length; i++) {
            var m = line.match(continuations[i].re);
            if (!m) {
                continue;
            }
            if (m[continuations[i].content].trim() === "") {
                setValue(
                    textarea,
                    value.substring(0, lineStart) + value.substring(start),
                    lineStart,
                    lineStart
                );
            } else {
                var insert = "\n" + continuations[i].next(m);
                setValue(
                    textarea,
                    value.substring(0, start) + insert + value.substring(start),
                    start + insert.length,
                    start + insert.length
                );
            }
            return true;
        }
        return false;
    }

    // When a URL is pasted over selected text, wrap it as a markdown link
    // instead of replacing the selection, matching GitHub.
    function handlePaste(textarea, e) {
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        if (start === end) {
            return;
        }
        var pasted = (e.clipboardData || window.clipboardData).getData("text").trim();
        if (!/^https?:\/\/\S+$/.test(pasted)) {
            return;
        }
        e.preventDefault();
        var value = textarea.value;
        var link = "[" + value.substring(start, end) + "](" + pasted + ")";
        setValue(
            textarea,
            value.substring(0, start) + link + value.substring(end),
            start + link.length,
            start + link.length
        );
    }

    // The server uses the same sanitizer and renderer as saved source pages.
    async function requestPreview(text, url, csrfToken, signal) {
        var response = await fetch(url, {
            method: "POST",
            mode: "same-origin",
            credentials: "same-origin",
            headers: { "X-CSRFToken": csrfToken },
            body: new URLSearchParams({ text: text }),
            signal: signal,
        });
        if (!response.ok) {
            throw new Error("Preview request failed");
        }
        var result = await response.json();
        if (typeof result.html !== "string") {
            throw new Error("Invalid preview response");
        }
        return result.html;
    }

    // Initialize each markdown widget on the page, wiring up the toolbar,
    // keyboard shortcuts, list continuation, and preview rendering.
    function init() {
        var markdownFields = document.getElementsByClassName("markdown-field");
        for (var i = 0; i < markdownFields.length; i++) {
            // let (not var) so each field's listeners close over its own elements.
            let field = markdownFields[i];
            let textarea = field.getElementsByClassName("markdown-textarea")[0];
            let preview = field.getElementsByClassName("markdown-preview")[0];
            let previewTab = field.getElementsByClassName("preview-tab")[0];
            let editTab = field.getElementsByClassName("edit-tab")[0];
            let toolbar = field.getElementsByClassName("markdown-toolbar")[0];

            let buttons = toolbar.getElementsByClassName("markdown-toolbar-btn");
            for (var j = 0; j < buttons.length; j++) {
                buttons[j].addEventListener("click", function () {
                    var action = actions[this.getAttribute("data-md-action")];
                    if (action) {
                        action(textarea);
                    }
                });
            }

            let previewRequest = null;
            // An earlier response must not overwrite a newer preview. Abort
            // requests when returning to Write, and check their identity too.
            previewTab.addEventListener("show.bs.tab", async function () {
                if (previewRequest) previewRequest.abort();
                const request = new AbortController();
                previewRequest = request;
                preview.textContent = "Loading preview…";
                preview.setAttribute("aria-busy", "true");
                preview.style.height = textarea.clientHeight + "px";
                toolbar.style.visibility = "hidden";
                try {
                    const token = textarea.form.querySelector(
                        '[name="csrfmiddlewaretoken"]'
                    ).value;
                    const html = await requestPreview(
                        textarea.value,
                        field.getAttribute("data-preview-url"),
                        token,
                        request.signal
                    );
                    if (previewRequest === request && !request.signal.aborted) {
                        preview.innerHTML = html;
                    }
                } catch (error) {
                    if (previewRequest === request && !request.signal.aborted) {
                        preview.textContent =
                            "Preview could not be loaded. Your text is unchanged. Try Preview again.";
                    }
                } finally {
                    if (previewRequest === request) {
                        preview.removeAttribute("aria-busy");
                    }
                }
            });
            editTab.addEventListener("show.bs.tab", function () {
                if (previewRequest) previewRequest.abort();
                toolbar.style.visibility = "visible";
            });

            textarea.addEventListener("paste", function (e) {
                handlePaste(this, e);
            });

            // Escape releases Tab for one keypress so the field is escapable.
            // Leaving the field re-arms Tab for indenting.
            let tabReleased = false;
            textarea.addEventListener("blur", function () {
                tabReleased = false;
            });

            textarea.addEventListener("keydown", function (e) {
                let tab = tabRelease(tabReleased, e.key);
                tabReleased = tab.released;
                if (tab.movesFocus || e.key === "Escape") {
                    return; // the browser moves focus; Escape does nothing else
                }
                if (e.key === "Tab") {
                    e.preventDefault();
                    indentLines(this, e.shiftKey);
                } else if (e.key === "Enter" && !e.shiftKey) {
                    if (continueList(this)) {
                        e.preventDefault();
                    }
                } else if ((e.ctrlKey || e.metaKey) && shortcuts[e.key.toLowerCase()]) {
                    e.preventDefault();
                    actions[shortcuts[e.key.toLowerCase()]](this);
                }
            });
        }
    }

    // Node (unit tests): export the pure helpers from inside the closure, where
    // they're in scope. Harmless in the browser, where `module` is undefined.
    if (typeof module !== "undefined" && module.exports) {
        module.exports = {
            requestPreview: requestPreview,
            wrapInline: wrapInline,
            insertLink: insertLink,
            toggleLinePrefix: toggleLinePrefix,
            indentLines: indentLines,
            continueList: continueList,
            handlePaste: handlePaste,
            tabRelease: tabRelease,
            actions: actions,
            continuations: continuations,
        };
    }

    return {
        init: function () {
            return init();
        },
    };
})();

if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", function () {
        MarkdownWidget.init();
    });
}
