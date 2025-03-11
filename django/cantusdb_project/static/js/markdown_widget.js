MarkdownWidget = (function () {
    // Initialize the markdown widget, attaching the necessary event listeners
    // to the textarea and preview elements
    function init() {
        var markdownFields = document.getElementsByClassName('markdown-field');
        for (var i = 0; i < markdownFields.length; i++) {
            let field = markdownFields[i]
            let textarea = field.getElementsByClassName('markdown-textarea')[0];
            let preview = field.getElementsByClassName('markdown-preview')[0];
            let previewTab = field.getElementsByClassName('preview-tab')[0];
            previewTab.addEventListener("show.bs.tab", function (event) {
                var markdownText = textarea.value;
                var parsed = marked.parse(markdownText);
                preview.innerHTML = parsed;
                // Set height of preview to match height of textarea
                preview.style.height = textarea.clientHeight + "px";
            });

            textarea.addEventListener('keydown', function (e) {
                if (e.key == 'Tab') {
                    e.preventDefault();
                    var start = this.selectionStart;
                    var end = this.selectionEnd;

                    // set textarea value to: text before caret + tab + text after caret
                    this.value = this.value.substring(0, start) +
                        "\t" + this.value.substring(end);

                    // put caret at right position again
                    this.selectionStart =
                        this.selectionEnd = start + 1;
                }
            });
        }
    }

    return {
        init: function () {
            return init();
        }
    };
})();

document.addEventListener("DOMContentLoaded", function () {
    MarkdownWidget.init();
});

