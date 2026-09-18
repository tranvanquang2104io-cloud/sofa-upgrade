/*
 * Give the user back what they typed when a save fails.
 *
 * WHY THIS EXISTS
 * A create/edit handler that hits a validation error re-renders the same
 * template. It used to re-render EMPTY: every line item, description and
 * amount the user had typed was gone. On a bespoke sofa order that can be ten
 * minutes of careful typing, and the people using this product are not
 * confident with computers — losing their work is the most punishing thing we
 * can do to them, and it makes them distrust the whole system.
 *
 * HOW
 * The server already knows what was submitted (Flask exposes `request` to the
 * template), so the base layout writes it into a JSON block on any POST that
 * re-renders. This script reads that block and puts the values back. One
 * place, no route changes, works on every form in the app.
 *
 * WHAT IT CANNOT DO
 * File inputs. A browser will not let a page re-select a file the user chose,
 * for good security reasons. So instead of silently dropping them we say so —
 * see the notice this adds when the lost form had file fields.
 */
(function () {
    'use strict';

    function restore() {
        var block = document.getElementById('submitted-form-data');
        if (!block) { return; }

        var data;
        try {
            data = JSON.parse(block.textContent || '{}');
        } catch (e) {
            return;                       // never break a page over this
        }
        if (!data || !Object.keys(data).length) { return; }

        var form = document.querySelector('form[method="POST"], form[method="post"]');
        if (!form) { return; }

        var repeated = {};
        var scalars = {};
        Object.keys(data).forEach(function (key) {
            if (key.slice(-2) === '[]') { repeated[key] = data[key]; }
            else { scalars[key] = data[key]; }
        });

        // --- repeated fields (line items) need their rows to exist first ---
        var rowsNeeded = 0;
        Object.keys(repeated).forEach(function (key) {
            rowsNeeded = Math.max(rowsNeeded, repeated[key].length);
        });

        if (rowsNeeded > 1) {
            var addRow = window.addRow || window.addItemRow || window.addLine;
            if (typeof addRow === 'function') {
                var firstKey = Object.keys(repeated)[0];
                var guard = 0;
                while (form.querySelectorAll('[name="' + firstKey + '"]').length < rowsNeeded
                       && guard < 200) {
                    addRow();
                    guard += 1;
                }
            }
        }

        Object.keys(repeated).forEach(function (key) {
            var fields = form.querySelectorAll('[name="' + CSS.escape(key) + '"]');
            repeated[key].forEach(function (value, i) {
                var field = fields[i];
                if (field && field.type !== 'file') { field.value = value; }
            });
        });

        // --- scalar fields -------------------------------------------------
        Object.keys(scalars).forEach(function (key) {
            var value = scalars[key][0];
            var fields = form.querySelectorAll('[name="' + CSS.escape(key) + '"]');
            for (var i = 0; i < fields.length; i++) {
                var field = fields[i];
                if (field.type === 'file') { continue; }
                if (field.type === 'checkbox') { field.checked = true; }
                else if (field.type === 'radio') { field.checked = (field.value === value); }
                else { field.value = value; }
            }
        });

        // --- tell the user about the one thing we could not restore --------
        var hadFile = form.querySelector('input[type="file"]');
        if (hadFile) {
            var notice = document.createElement('div');
            notice.className = 'alert alert-warning py-2 px-3 small';
            notice.setAttribute('role', 'status');
            notice.textContent = block.dataset.fileNotice
                || 'Your text was restored. Please choose any images again.';
            form.insertBefore(notice, form.firstChild);
        }

        // Totals were computed from the old values; recompute if the page can.
        if (typeof window.recalcAll === 'function') {
            try { window.recalcAll(); } catch (e) { /* not fatal */ }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', restore);
    } else {
        restore();
    }
})();
