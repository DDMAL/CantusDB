MarkdownWidget = (function () {
    // True when `text` is already wrapped in `marker`. The single-'*' italic
    // marker deliberately does not match a '**' bold run.
    function isWrapped(text, marker) {
        var len = marker.length;
        if (text.length < len * 2) {
            return false;
        }
        if (text.slice(0, len) !== marker || text.slice(-len) !== marker) {
            return false;
        }
        if (marker === "*" && (text[1] === "*" || text[text.length - 2] === "*")) {
            return false;
        }
        return true;
    }

    // Wrap the selection in an inline marker, or unwrap it if already wrapped
    // (toggle), matching GitHub's bold/italic buttons. With no selection, insert
    // the placeholder and select it so the user can type over it.
    function wrapInline(textarea, marker, placeholder) {
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        var value = textarea.value;
        var selected = value.substring(start, end);
        var len = marker.length;

        // Selection already includes the markers, e.g. "**text**".
        if (isWrapped(selected, marker)) {
            var inner = selected.slice(len, -len);
            textarea.value = value.substring(0, start) + inner + value.substring(end);
            textarea.selectionStart = start;
            textarea.selectionEnd = start + inner.length;
            textarea.focus();
            return;
        }

        // Markers sit just outside the selection, e.g. **[text]**.
        var italicInBold =
            marker === "*" && (value[start - 2] === "*" || value[end + 1] === "*");
        if (
            value.substring(start - len, start) === marker &&
            value.substring(end, end + len) === marker &&
            !italicInBold
        ) {
            textarea.value =
                value.substring(0, start - len) + selected + value.substring(end + len);
            textarea.selectionStart = start - len;
            textarea.selectionEnd = end - len;
            textarea.focus();
            return;
        }

        var text = selected || placeholder;
        textarea.value =
            value.substring(0, start) + marker + text + marker + value.substring(end);
        textarea.selectionStart = start + len;
        textarea.selectionEnd = start + len + text.length;
        textarea.focus();
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
        textarea.value =
            value.substring(0, start) + before + url + ")" + value.substring(end);
        textarea.selectionStart = start + before.length;
        textarea.selectionEnd = start + before.length + url.length;
        textarea.focus();
    }

    // Toggle a line-level marker (heading, quote, list) across every line the
    // selection touches. If all lines already have it, strip it; otherwise
    // normalize and (re)apply so clicking twice never stacks markers.
    function toggleLinePrefix(textarea, strip, marker) {
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        var value = textarea.value;
        var blockStart = value.lastIndexOf("\n", start - 1) + 1;
        var blockEnd = value.indexOf("\n", end);
        if (blockEnd === -1) {
            blockEnd = value.length;
        }
        var lines = value.substring(blockStart, blockEnd).split("\n");
        var allMarked = lines.every(function (line) {
            return strip.test(line);
        });
        var result = lines
            .map(function (line, i) {
                var bare = line.replace(strip, "");
                return allMarked ? bare : marker(bare, i);
            })
            .join("\n");
        textarea.value =
            value.substring(0, blockStart) + result + value.substring(blockEnd);
        textarea.selectionStart = blockStart;
        textarea.selectionEnd = blockStart + result.length;
        textarea.focus();
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
        textarea.value =
            value.substring(0, blockStart) + newLines.join("\n") + value.substring(blockEnd);
        textarea.selectionStart = Math.max(blockStart, start + firstDelta);
        textarea.selectionEnd = Math.max(blockStart, end + totalDelta);
        textarea.focus();
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
            toggleLinePrefix(textarea, /^\s*>\s?/, function (line) {
                return "> " + line;
            });
        },
        link: function (textarea) {
            insertLink(textarea);
        },
        "unordered-list": function (textarea) {
            toggleLinePrefix(textarea, /^\s*[-*+]\s+/, function (line) {
                return "- " + line;
            });
        },
        "ordered-list": function (textarea) {
            toggleLinePrefix(textarea, /^\s*\d+[.)]\s+/, function (line, i) {
                return i + 1 + ". " + line;
            });
        },
    };

    // Ctrl/Cmd shortcuts that mirror GitHub's markdown input.
    var shortcuts = { b: "bold", i: "italic", k: "link" };

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
            re: /^(\s*>\s?)(.*)$/,
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
                textarea.value = value.substring(0, lineStart) + value.substring(start);
                textarea.selectionStart = textarea.selectionEnd = lineStart;
            } else {
                var insert = "\n" + continuations[i].next(m);
                textarea.value =
                    value.substring(0, start) + insert + value.substring(start);
                textarea.selectionStart = textarea.selectionEnd = start + insert.length;
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
        textarea.value = value.substring(0, start) + link + value.substring(end);
        textarea.selectionStart = textarea.selectionEnd = start + link.length;
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

            // The toolbar only makes sense while editing; hide it on Preview.
            previewTab.addEventListener("show.bs.tab", function () {
                preview.innerHTML = marked.parse(textarea.value);
                preview.style.height = textarea.clientHeight + "px";
                toolbar.style.visibility = "hidden";
            });
            editTab.addEventListener("show.bs.tab", function () {
                toolbar.style.visibility = "visible";
            });

            textarea.addEventListener("paste", function (e) {
                handlePaste(this, e);
            });

            textarea.addEventListener("keydown", function (e) {
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

    return {
        init: function () {
            return init();
        },
    };
})();

document.addEventListener("DOMContentLoaded", function () {
    MarkdownWidget.init();
});
