/*
 * Tracker Stages 34.43–34.46
 *
 * Inventory review productivity enhancements.
 *
 * Read-only:
 * - Browser-local review preferences
 * - Keyboard shortcuts
 * - Detailed vial CSV
 * - Data-quality review
 */

(() => {
  'use strict';

  const STORAGE_KEY = 'tracker.inventory.review.v1';

  const $ = id => document.getElementById(id);

  const clean = value =>
    String(value ?? '').trim();

  function make(tag, value, className) {
    const node = document.createElement(tag);

    if (value !== undefined) {
      node.textContent = value;
    }

    if (className) {
      node.className = className;
    }

    return node;
  }

  function readPreference() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const value = JSON.parse(raw || '{}');

      return value && typeof value === 'object'
        ? value
        : {};
    } catch (_) {
      return {};
    }
  }

  function writePreference(value) {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(value)
      );
    } catch (_) {
      // Storage may be disabled.
      // The controls remain usable for this session.
    }
  }

  function validDate(value) {
    const raw = clean(value);

    if (!raw) return null;

    const match = raw.match(
      /^(\d{4})-(\d{2})-(\d{2})$/
    );

    if (!match) return null;

    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);

    const check = new Date(year, month - 1, day);

    if (
      check.getFullYear() !== year ||
      check.getMonth() !== month - 1 ||
      check.getDate() !== day
    ) {
      return null;
    }

    return raw;
  }

  function readVials() {
    const table = $('tracker-vials-sortable');

    if (!table) return [];

    return Array.from(
      table.querySelectorAll('tbody tr')
    ).map(row => {
      const cells = row.querySelectorAll('td');

      if (cells.length < 9) return null;

      const checkbox = cells[0].querySelector(
        'input.bulk-vial-check'
      );

      const link = cells[2].querySelector(
        'a[href]'
      );

      if (!checkbox || !link) return null;

      const status = clean(
        row.dataset.attentionStatus
      );

      if (!['sealed', 'in_use'].includes(status)) {
        return null;
      }

      const href = link.getAttribute('href') || '';

      if (!/^\/vials\/\d+(?:[?#].*)?$/.test(href)) {
        return null;
      }

      const remainingCell = cells[4].cloneNode(true);

      remainingCell.querySelectorAll('small').forEach(
        node => node.remove()
      );

      const remaining = clean(
        remainingCell.textContent
      );

      const coaText = clean(
        cells[7].textContent
      ).toLowerCase();

      const coaKnown = ['yes', 'none'].includes(coaText);
      const coa = coaText === 'yes';

      const expiration = clean(
        row.dataset.attentionExpires
      );

      const beyondUse = clean(
        row.dataset.attentionBeyondUse
      );

      const quantityRecognized =
        /^(?:\d+(?:\.\d*)?|\.\d+)\s*(?:mcg|µg|μg|mg|g|iu|ml|units?)\s*$/i
          .test(remaining.replace(/,/g, ''));

      const issues = [];

      if (!coa && coaKnown) {
        issues.push('Missing COA');
      }

      if (!expiration) {
        issues.push('Expiration not recorded');
      } else if (!validDate(expiration)) {
        issues.push('Invalid expiration date');
      }

      if (!beyondUse && status === 'in_use') {
        issues.push('Beyond-use date not recorded');
      } else if (beyondUse && !validDate(beyondUse)) {
        issues.push('Invalid beyond-use date');
      }

      if (!quantityRecognized) {
        issues.push('Quantity not interpreted');
      }

      return {
        id: clean(checkbox.value),
        compound: clean(cells[1].textContent),
        vial: clean(link.textContent),
        href,
        status,
        remaining,
        expiration,
        beyondUse,
        coa: coaKnown ? (coa ? 'Yes' : 'No') : 'Unknown',
        issues
      };
    }).filter(Boolean);
  }

  function csvCell(value) {
    const raw = String(value ?? '');

    // Prevent formula execution when opened
    // in spreadsheet applications.
    const safe = /^[\s]*[=+\-@\t\r]/.test(raw)
      ? "'" + raw
      : raw;

    return '"' + safe.replace(/"/g, '""') + '"';
  }

  function downloadCSV(filename, rows) {
    const csv = rows
      .map(row => row.map(csvCell).join(','))
      .join('\r\n');

    const blob = new Blob(
      ['\uFEFF', csv],
      { type: 'text/csv;charset=utf-8' }
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = filename;

    document.body.append(link);
    link.click();
    link.remove();

    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function exportVials(records) {
    const rows = [[
      'Vial ID',
      'Compound',
      'Vial',
      'Status',
      'Remaining as displayed',
      'Expiration date',
      'Beyond-use date',
      'COA associated',
      'Data-quality issues',
      'Vial path'
    ]];

    records.forEach(record => {
      rows.push([
        record.id,
        record.compound,
        record.vial,
        record.status,
        record.remaining,
        record.expiration,
        record.beyondUse,
        record.coa,
        record.issues.join('; '),
        record.href
      ]);
    });

    downloadCSV(
      'tracker-vial-review-detail.csv',
      rows
    );
  }

  function initialize() {
    const panel = $('tracker-compound-inventory');
    const search = $('tracker-ci-search');
    const sort = $('tracker-ci-sort');
    const table = $('tracker-vials-sortable');

    if (!panel || !search || !sort || !table) {
      return;
    }

    const records = readVials();

    if (!records.length) return;

    const controls = panel.querySelector(
      '.tracker-ci-controls'
    );

    if (!controls) return;

    if ($('tracker-review-tools')) return;

    const preferences = readPreference();

    /*
     * Stage 34.43
     * Restore search and sort preferences.
     */
    if (typeof preferences.search === 'string') {
      search.value = preferences.search.slice(0, 150);
    }

    if (
      typeof preferences.sort === 'string' &&
      Array.from(sort.options).some(
        option => option.value === preferences.sort
      )
    ) {
      sort.value = preferences.sort;
    }

    function savePreferences() {
      writePreference({
        search: search.value,
        sort: sort.value
      });
    }

    search.addEventListener(
      'input',
      savePreferences
    );

    sort.addEventListener(
      'change',
      savePreferences
    );

    /*
     * Re-render the existing summary after
     * restoring browser preferences.
     */
    search.dispatchEvent(
      new Event('input', { bubbles: true })
    );

    sort.dispatchEvent(
      new Event('change', { bubbles: true })
    );

    /*
     * Stage 34.44
     * Keyboard shortcuts.
     */
    document.addEventListener('keydown', event => {
      if (
        event.ctrlKey ||
        event.altKey ||
        event.metaKey
      ) {
        return;
      }

      const target = event.target;

      const typing = target instanceof HTMLElement &&
        (
          target.matches(
            'input, textarea, select'
          ) ||
          target.isContentEditable
        );

      if (
        event.key === '/' &&
        !typing &&
        !event.repeat &&
        !event.defaultPrevented
      ) {
        event.preventDefault();
        search.focus();
        search.select();
      }

      if (
        event.key === 'Escape' &&
        document.activeElement === search
      ) {
        if (search.value) {
          search.value = '';

          search.dispatchEvent(
            new Event('input', { bubbles: true })
          );
        } else {
          search.blur();
        }
      }
    });

    /*
     * Stage 34.45
     * Detailed vial-level export.
     */
    const tools = make(
      'div',
      undefined,
      'tracker-review-tools'
    );

    tools.id = 'tracker-review-tools';

    const exportButton = make(
      'button',
      'Export vial details CSV'
    );

    exportButton.type = 'button';

    exportButton.addEventListener('click', () => {
      exportVials(records);
    });

    tools.append(exportButton);
    controls.append(tools);

    /*
     * Stage 34.46
     * Data-quality review.
     */
    const flagged = records.filter(
      record => record.issues.length > 0
    );

    const issueCounts = {
      coa: records.filter(
        record => record.issues.includes('Missing COA')
      ).length,
      expiration: records.filter(
        record => record.issues.some(
          issue => issue.includes('expiration')
        )
      ).length,
      beyondUse: records.filter(
        record => record.issues.some(
          issue => issue.includes('Beyond-use')
        )
      ).length,
      quantity: records.filter(
        record => record.issues.includes(
          'Quantity not interpreted'
        )
      ).length
    };

    const review = make(
      'details',
      undefined,
      'tracker-review-quality'
    );

    review.id = 'tracker-review-quality';

    const heading = make(
      'summary',
      `${flagged.length} of ${records.length} vials ` +
      'have incomplete review metadata'
    );

    review.append(heading);

    const description = make(
      'p',
      'Missing dates indicate incomplete records, not ' +
      'necessarily an expired vial. A missing COA ' +
      'association does not independently establish ' +
      'product quality.',
      'note'
    );

    review.append(description);

    const counts = make(
      'p',
      `${issueCounts.coa} missing COA · ` +
      `${issueCounts.expiration} expiration gaps · ` +
      `${issueCounts.beyondUse} beyond-use gaps · ` +
      `${issueCounts.quantity} quantity-format issues`,
      'tracker-review-counts'
    );

    review.append(counts);

    const qualityControls = make(
      'div',
      undefined,
      'tracker-review-quality-controls'
    );

    const qualitySearch = make('input');
    qualitySearch.type = 'search';
    qualitySearch.placeholder = 'Filter flagged vials…';
    qualitySearch.setAttribute(
      'aria-label',
      'Filter flagged vials by compound or vial'
    );

    const exportFlagged = make(
      'button',
      'Export flagged vials'
    );

    exportFlagged.type = 'button';

    qualityControls.append(
      qualitySearch,
      exportFlagged
    );

    review.append(qualityControls);

    const results = make(
      'div',
      undefined,
      'tracker-review-quality-results'
    );

    review.append(results);

    function matchingFlagged() {
      const query = qualitySearch.value
        .trim()
        .toLocaleLowerCase();

      return flagged.filter(record => {
        const haystack = [
          record.compound,
          record.vial,
          record.id,
          record.issues.join(' ')
        ].join(' ').toLocaleLowerCase();

        return haystack.includes(query);
      });
    }

    function renderFlagged() {
      results.replaceChildren();

      const matching = matchingFlagged();

      if (!matching.length) {
        results.append(
          make(
            'p',
            'No matching records.',
            'note'
          )
        );

        return;
      }

      const list = make('ul');

      matching.forEach(record => {
        const item = make('li');

        const link = make(
          'a',
          `${record.compound} — ${record.vial}`
        );

        link.href = record.href;

        const detail = make(
          'small',
          record.issues.join(' · ')
        );

        item.append(link, detail);
        list.append(item);
      });

      results.append(list);
    }

    qualitySearch.addEventListener(
      'input',
      renderFlagged
    );

    exportFlagged.addEventListener('click', () => {
      exportVials(matchingFlagged());
    });

    if (flagged.length) {
      controls.after(review);
      renderFlagged();
    }

    window.trackerInventoryReviewDiagnostics = () => ({
      currentVials: records.length,
      flaggedVials: flagged.length,
      issueCounts,
      savedPreferences: readPreference(),
      detailedExportAvailable: true,
      keyboardShortcuts: ['/', 'Escape']
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
