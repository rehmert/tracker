/*
 * Tracker Stage 34.35
 * Read-only inventory alert triage.
 *
 * Existing server-side alerts remain authoritative.
 * Filtering affects display only.
 */

(() => {
  'use strict';

  const STORAGE_KEY = 'tracker.inventory-alert-triage.v1';

  function normalize(value) {
    return String(value || '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function makeElement(tag, className, text) {
    const element = document.createElement(tag);

    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;

    return element;
  }

  function createSelect(labelText, id, options) {
    const label = makeElement('label', 'tracker-triage-field');
    const caption = makeElement('span', '', labelText);
    const select = document.createElement('select');

    select.id = id;

    options.forEach(([value, text]) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = text;
      select.append(option);
    });

    label.append(caption, select);

    return { label, select };
  }

  function initialize() {
    const table = document.querySelector(
      'table.alert-table'
    );

    if (!table || table.dataset.trackerTriageReady) {
      return;
    }

    const tbody = table.tBodies[0];
    if (!tbody) return;

    const headers = Array.from(
      table.querySelectorAll('thead th')
    ).map(cell => normalize(cell.textContent).toLowerCase());

    const priorityIndex = headers.indexOf('priority');
    const categoryIndex = headers.indexOf('category');

    if (priorityIndex < 0 || categoryIndex < 0) {
      console.warn(
        'Tracker triage: expected alert columns not found.'
      );
      return;
    }

    const rows = Array.from(tbody.rows)
      .filter(row => {
        return row.cells.length === headers.length;
      });

    // Avoid displaying a toolbar for an empty alert list.
    if (!rows.length) return;

    const records = rows.map(row => {
      const priority = normalize(
        row.cells[priorityIndex].textContent
      );

      const category = normalize(
        row.cells[categoryIndex].textContent
      );

      return {
        row,
        priority,
        category,
        search: normalize(row.textContent).toLowerCase()
      };
    });

    const priorities = [...new Set(
      records.map(record => record.priority)
    )].sort((a, b) => a.localeCompare(b));

    const categories = [...new Set(
      records.map(record => record.category)
    )].sort((a, b) => a.localeCompare(b));

    const toolbar = makeElement(
      'section',
      'tracker-triage-toolbar'
    );

    toolbar.setAttribute(
      'aria-label',
      'Inventory alert filters'
    );

    const heading = makeElement(
      'div',
      'tracker-triage-heading'
    );

    const title = makeElement(
      'strong',
      '',
      'Review alerts'
    );

    const count = makeElement(
      'span',
      'tracker-triage-count'
    );
    const breakdown = makeElement(
      'span',
      'tracker-triage-breakdown'
    );
    breakdown.setAttribute('aria-label', 'Visible alerts by priority');

    count.setAttribute('role', 'status');
    count.setAttribute('aria-live', 'polite');

    const headingStatus = makeElement('div', 'tracker-triage-status');
    headingStatus.append(count, breakdown);
    heading.append(title, headingStatus);

    const controls = makeElement(
      'div',
      'tracker-triage-controls'
    );

    const searchLabel = makeElement(
      'label',
      'tracker-triage-field tracker-triage-search'
    );

    const searchCaption = makeElement(
      'span',
      '',
      'Search alerts'
    );

    const search = document.createElement('input');
    search.type = 'search';
    search.id = 'tracker-triage-search';
    search.placeholder = 'Item, reason, date…';
    search.autocomplete = 'off';

    searchLabel.append(searchCaption, search);

    const priority = createSelect(
      'Priority',
      'tracker-triage-priority',
      [
        ['', 'All priorities'],
        ...priorities.map(value => [value, value])
      ]
    );

    const category = createSelect(
      'Category',
      'tracker-triage-category',
      [
        ['', 'All categories'],
        ...categories.map(value => [value, value])
      ]
    );

    const reset = makeElement(
      'button',
      'tracker-triage-reset',
      'Clear filters'
    );

    reset.type = 'button';

    const exportButton = makeElement(
      'button',
      'tracker-triage-export',
      'Export filtered CSV'
    );
    exportButton.id = 'tracker-triage-export';
    exportButton.type = 'button';
    exportButton.title = 'Download only alerts visible with the current filters';

    controls.append(
      searchLabel,
      priority.label,
      category.label,
      reset,
      exportButton
    );

    toolbar.append(heading, controls);

    const tableContainer = table.closest('.scroll') || table;
    tableContainer.before(toolbar);

    const empty = makeElement(
      'p',
      'tracker-triage-empty',
      'No alerts match these filters.'
    );

    empty.hidden = true;
    tableContainer.after(empty);

    function savePreferences() {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            priority: priority.select.value,
            category: category.select.value
          })
        );
      } catch (_) {
        // Filtering still works if storage is unavailable.
      }
    }

    function restorePreferences() {
      try {
        const saved = JSON.parse(
          localStorage.getItem(STORAGE_KEY) || '{}'
        );

        if (
          priorities.includes(saved.priority)
        ) {
          priority.select.value = saved.priority;
        }

        if (
          categories.includes(saved.category)
        ) {
          category.select.value = saved.category;
        }
      } catch (_) {
        // Ignore invalid or inaccessible saved preferences.
      }
    }

    function applyFilters() {
      const query = normalize(
        search.value
      ).toLowerCase();

      const selectedPriority = priority.select.value;
      const selectedCategory = category.select.value;

      let visible = 0;
      const priorityCounts = new Map();

      records.forEach(record => {
        const matches =
          (!query || record.search.includes(query)) &&
          (!selectedPriority ||
            record.priority === selectedPriority) &&
          (!selectedCategory ||
            record.category === selectedCategory);

        record.row.hidden = !matches;

        // Some existing table rules override the browser's
        // default [hidden] behavior.
        record.row.style.display = matches ? '' : 'none';

        if (matches) {
          visible++;
          priorityCounts.set(
            record.priority,
            (priorityCounts.get(record.priority) || 0) + 1
          );
        }
      });

      count.textContent =
        `${visible} of ${records.length} alerts shown`;
      breakdown.textContent = [...priorityCounts]
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(([name, amount]) => `${amount} ${name.toLowerCase()}`)
        .join(' · ') || 'None matching';

      exportButton.disabled = visible === 0;
      empty.hidden = visible !== 0;
      tableContainer.hidden = visible === 0;

      reset.disabled =
        !query &&
        !selectedPriority &&
        !selectedCategory;

      return visible;
    }

    function csvCell(value) {
      const valueText = String(value ?? '');
      // Spreadsheet programs can execute formulas embedded in exported text.
      // Export priority/category/name/reason/date as literal strings.
      const safe = /^[\s\u0000-\u001f]*[=+\-@]/.test(valueText) ||
                   /^[\t\r\n]/.test(valueText)
        ? "'" + valueText : valueText;
      return '"' + safe.replaceAll('"', '""') + '"';
    }

    function exportFilteredCsv() {
      const visible = records.filter(record => !record.row.hidden);
      if (!visible.length) return;
      const heading = ['Priority', 'Category', 'Item', 'Reason', 'Relevant date'];
      const content = [heading, ...visible.map(record =>
        Array.from(record.row.cells, cell => normalize(cell.textContent))
      )];
      const csv = '\uFEFF' + content.map(line => line.map(csvCell).join(','))
        .join('\r\n') + '\r\n';
      const blob = new Blob([csv], {type: 'text/csv;charset=utf-8'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'tracker-inventory-alerts-filtered.csv';
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    exportButton.addEventListener('click', exportFilteredCsv);
    search.addEventListener('input', applyFilters);

    priority.select.addEventListener('change', () => {
      savePreferences();
      applyFilters();
    });

    category.select.addEventListener('change', () => {
      savePreferences();
      applyFilters();
    });

    reset.addEventListener('click', () => {
      search.value = '';
      priority.select.value = '';
      category.select.value = '';

      savePreferences();
      applyFilters();
      search.focus();
    });

    records.forEach(record => {
      const level = record.priority.toLowerCase();

      if (
        /critical|urgent|error|high/.test(level)
      ) {
        record.row.classList.add(
          'tracker-triage-high'
        );
      } else if (
        /warning|medium|moderate/.test(level)
      ) {
        record.row.classList.add(
          'tracker-triage-warning'
        );
      }
    });

    restorePreferences();
    applyFilters();

    table.dataset.trackerTriageReady = '1';

    window.trackerInventoryTriageDiagnostics = () => ({
      totalAlerts: records.length,
      visibleAlerts: records.filter(
        record => !record.row.hidden
      ).length,
      priorities,
      categories,
      priorityFilter: priority.select.value,
      categoryFilter: category.select.value,
      search: search.value
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initialize,
      { once: true }
    );
  } else {
    initialize();
  }
})();
