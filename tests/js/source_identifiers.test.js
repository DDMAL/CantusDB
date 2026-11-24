// Tests for the × on rows of the source identifiers table (issue #2015).
//
// Run with: node --test "tests/js/**/*.test.js"
//
// The page script is a plain browser script, so these tests stand a small
// stub in for one table row: the hidden DELETE checkbox, the button and its
// icon.

const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { setRemoved } = require(path.join(
    __dirname, '..', '..', 'django', 'cantusdb_project',
    'static', 'js', 'source_identifiers.js'
));

function makeRow() {
    const classes = new Set();
    const checkbox = { checked: false };
    const icon = { className: 'bi bi-x-lg' };
    const attributes = {};
    const button = {
        title: '',
        setAttribute: (name, value) => { attributes[name] = value; },
        querySelector: () => icon,
    };
    const row = {
        classList: {
            toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)),
            contains: (name) => classes.has(name),
        },
        querySelector: (selector) =>
            selector === '.identifier-remove' ? button : checkbox,
    };
    return { row, checkbox, icon, button, attributes, classes };
}

test('the × marks the row for removal and greys it out', () => {
    const { row, checkbox, icon, button, attributes, classes } = makeRow();
    setRemoved(row, true);
    assert.equal(checkbox.checked, true);
    assert.ok(classes.has('identifier-removed'));
    assert.equal(icon.className, 'bi bi-arrow-counterclockwise');
    assert.equal(button.title, 'Bring this identifier back');
    assert.equal(attributes['aria-pressed'], 'true');
});

test('clicking again brings the row back', () => {
    const { row, checkbox, icon, button, attributes, classes } = makeRow();
    setRemoved(row, true);
    setRemoved(row, false);
    assert.equal(checkbox.checked, false);
    assert.ok(!classes.has('identifier-removed'));
    assert.equal(icon.className, 'bi bi-x-lg');
    assert.equal(button.title, 'Remove this identifier');
    assert.equal(attributes['aria-pressed'], 'false');
});
