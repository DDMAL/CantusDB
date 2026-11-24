// The identifiers table on the source create and edit pages (issue #2015).
//
// - "Add another identifier" adds a blank row to the formset.
// - The × on a row marks it for removal: the row greys out, and the same
//   button brings it back. Nothing is removed until the form is saved.

/**
 * Marks a row for removal, or brings it back.
 *
 * @param {Element} row - an identifier row (<tr>)
 * @param {boolean} removed - whether the row should be removed on save
 */
function setRemoved(row, removed) {
    row.querySelector('input[name$="-DELETE"]').checked = removed;
    row.classList.toggle('identifier-removed', removed);
    const button = row.querySelector('.identifier-remove');
    const label = removed ? 'Bring this identifier back' : 'Remove this identifier';
    button.title = label;
    button.setAttribute('aria-label', label);
    button.setAttribute('aria-pressed', String(removed));
    const icon = button.querySelector('i');
    icon.className = removed ? 'bi bi-arrow-counterclockwise' : 'bi bi-x-lg';
}

function initializeIdentifierRows() {
    const rows = document.getElementById('identifier-rows');
    if (!rows) {
        return;
    }
    // Rows sent back after a failed save keep their removal mark.
    rows.querySelectorAll('tr').forEach((row) => {
        setRemoved(row, row.querySelector('input[name$="-DELETE"]').checked);
    });
    rows.addEventListener('click', (event) => {
        const button = event.target.closest('.identifier-remove');
        if (!button) {
            return;
        }
        const row = button.closest('tr');
        setRemoved(row, !row.classList.contains('identifier-removed'));
    });

    document.getElementById('add-identifier').addEventListener('click', () => {
        const total = document.getElementById('id_identifiers-TOTAL_FORMS');
        const emptyRow = document.getElementById('identifier-empty-row');
        const index = Number(total.value);
        rows.insertAdjacentHTML(
            'beforeend',
            emptyRow.innerHTML.replace(/__prefix__/g, String(index)),
        );
        total.value = String(index + 1);
        rows.lastElementChild.querySelector('select')?.focus();
    });
}

if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', initializeIdentifierRows);
}

// Exported for the Node tests; the browser loads this file as a plain script.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { setRemoved };
}
