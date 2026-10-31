(() => {
  'use strict';

  const byId = id => document.getElementById(id);
  const clean = value => String(value ?? '').trim();

  const format = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 4
  });

  function make(tag, value, className) {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = value;
    if (className) node.className = className;
    return node;
  }

  function daysUntil(value) {
    const match = clean(value).match(
      /^(\d{4})-(\d{2})-(\d{2})$/
    );

    if (!match) return null;

    const y = Number(match[1]);
    const m = Number(match[2]);
    const d = Number(match[3]);

    const check = new Date(y, m - 1, d);

    if (
      check.getFullYear() !== y ||
      check.getMonth() !== m - 1 ||
      check.getDate() !== d
    ) return null;

    const today = new Date();

    const start = Date.UTC(
      today.getFullYear(),
      today.getMonth(),
      today.getDate()
    );

    return Math.round(
      (Date.UTC(y, m - 1, d) - start) / 86400000
    );
  }

  function parseQuantity(value) {
    const normalized = clean(value).replace(/,/g, '');

    const match = normalized.match(
      /^(\d+(?:\.\d+)?|\.\d+)\s*(mcg|µg|μg|mg|g|iu|ml|units?)\b/i
    );

    if (!match) return null;

    const amount = Number(match[1]);
    const unit = match[2].toLowerCase();

    if (!Number.isFinite(amount)) return null;

    if (['mcg', 'µg', 'μg'].includes(unit)) {
      return { amount: amount / 1000, unit: 'mg' };
    }

    if (unit === 'g') {
      return { amount: amount * 1000, unit: 'mg' };
    }

    if (unit === 'mg') {
      return { amount, unit: 'mg' };
    }

    if (unit === 'ml') {
      return { amount, unit: 'mL' };
    }

    if (unit === 'iu') {
      return { amount, unit: 'IU' };
    }

    return { amount, unit: 'units' };
  }

  function readRecords() {
    const table = byId('tracker-vials-sortable');
    if (!table) return [];

    return Array.from(table.querySelectorAll('tbody tr'))
      .map(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 9) return null;

        const status = clean(row.dataset.attentionStatus);
        if (!['sealed', 'in_use'].includes(status)) return null;

        const link = cells[2].querySelector('a[href]');
        if (!link) return null;

        const href = link.getAttribute('href') || '';
        if (!/^\/vials\/\d+(?:[?#].*)?$/.test(href)) return null;

        const remainingCell = cells[4].cloneNode(true);
        remainingCell.querySelectorAll('small').forEach(
          node => node.remove()
        );

        const rawRemaining = clean(remainingCell.textContent);
        const quantity = parseQuantity(rawRemaining);

        const expiry = daysUntil(
          row.dataset.attentionExpires
        );

        const bud = daysUntil(
          row.dataset.attentionBeyondUse
        );

        const dates = [expiry, bud].filter(
          value => value !== null
        );

        const earliest = dates.length
          ? Math.min(...dates)
          : null;

        const coa = clean(
          cells[7].textContent
        ).toLowerCase() === 'yes';

        return {
          compound: clean(cells[1].textContent),
          href,
          status,
          coa,
          quantity,
          rawRemaining,
          earliest,
          needsReview:
            !coa || (earliest !== null && earliest <= 30)
        };
      })
      .filter(Boolean);
  }

  function summarize(records) {
    const groups = new Map();

    for (const record of records) {
      if (!groups.has(record.compound)) {
        groups.set(record.compound, {
          name: record.compound,
          records: [],
          sealed: 0,
          inUse: 0,
          missingCOA: 0,
          needsReview: 0,
          past: 0,
          days7: 0,
          days30: 0,
          days90: 0,
          totals: new Map(),
          exposed: new Map(),
          unknown: 0
        });
      }

      const group = groups.get(record.compound);
      group.records.push(record);

      if (record.status === 'sealed') group.sealed++;
      if (record.status === 'in_use') group.inUse++;
      if (!record.coa) group.missingCOA++;
      if (record.needsReview) group.needsReview++;

      if (record.earliest !== null) {
        if (record.earliest < 0) group.past++;
        else if (record.earliest <= 7) group.days7++;
        else if (record.earliest <= 30) group.days30++;
        else if (record.earliest <= 90) group.days90++;
      }

      if (!record.quantity) {
        group.unknown++;
        continue;
      }

      const { amount, unit } = record.quantity;

      group.totals.set(
        unit,
        (group.totals.get(unit) || 0) + amount
      );

      if (
        record.earliest !== null &&
        record.earliest <= 30
      ) {
        group.exposed.set(
          unit,
          (group.exposed.get(unit) || 0) + amount
        );
      }
    }

    return Array.from(groups.values());
  }

  function totals(map) {
    if (!map.size) return 'Not available';

    return Array.from(map.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([unit, amount]) =>
        `${format.format(amount)} ${unit}`
      )
      .join(' + ');
  }

  function csvValue(value) {
    const str = String(value ?? '');
    const safe = /^[\s]*[=+\-@\t\r]/.test(str)
      ? "'" + str
      : str;

    return '"' + safe.replace(/"/g, '""') + '"';
  }

  function exportCSV(groups) {
    const rows = [[
      'Compound', 'Vials', 'Sealed', 'In use',
      'Remaining', 'Missing COA', 'Needs review',
      'Past date', '0–7 days', '8–30 days',
      '31–90 days', 'Quantity dated within 30 days',
      'Unparsed quantities'
    ]];

    for (const group of groups) {
      rows.push([
        group.name,
        group.records.length,
        group.sealed,
        group.inUse,
        totals(group.totals),
        group.missingCOA,
        group.needsReview,
        group.past,
        group.days7,
        group.days30,
        group.days90,
        totals(group.exposed),
        group.unknown
      ]);
    }

    const csv = rows
      .map(row => row.map(csvValue).join(','))
      .join('\r\n');

    const blob = new Blob(
      ['\uFEFF', csv],
      { type: 'text/csv;charset=utf-8' }
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = 'tracker-compound-inventory.csv';

    document.body.append(link);
    link.click();
    link.remove();

    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function initialize() {
    const panel = byId('tracker-compound-inventory');
    const search = byId('tracker-ci-search');
    const sort = byId('tracker-ci-sort');
    const results = byId('tracker-ci-results');
    const count = byId('tracker-ci-count');
    const empty = byId('tracker-ci-empty');
    const exportButton = byId('tracker-ci-export');

    if (
      !panel || !search || !sort || !results ||
      !count || !empty || !exportButton
    ) return;

    const records = readRecords();
    const groups = summarize(records);

    if (!groups.length) return;

    function visible() {
      const query = search.value.trim().toLowerCase();

      const selected = groups.filter(group =>
        group.name.toLowerCase().includes(query)
      );

      const key = sort.value;

      selected.sort((a, b) => {
        if (key === 'review') {
          return b.needsReview - a.needsReview ||
            a.name.localeCompare(b.name);
        }

        if (key === 'date') {
          const warnings = group =>
            group.past + group.days7 + group.days30;

          return warnings(b) - warnings(a) ||
            a.name.localeCompare(b.name);
        }

        if (key === 'coa') {
          return b.missingCOA - a.missingCOA ||
            a.name.localeCompare(b.name);
        }

        return a.name.localeCompare(b.name);
      });

      return selected;
    }

    function render() {
      const groupsToShow = visible();

      count.textContent =
        `${groupsToShow.length} compounds · ` +
        `${records.length} current vials`;

      results.replaceChildren();

      empty.hidden = groupsToShow.length > 0;
      results.hidden = groupsToShow.length === 0;

      if (!groupsToShow.length) return;

      const table = make('table', undefined, 'tracker-ci-table');
      const thead = make('thead');
      const headings = make('tr');

      [
        'Compound', 'Vials', 'Remaining',
        'COA gaps', 'Date exposure', 'Review'
      ].forEach(label => {
        headings.append(make('th', label));
      });

      thead.append(headings);

      const tbody = make('tbody');

      for (const group of groupsToShow) {
        const row = make('tr');

        if (group.needsReview) {
          row.className = 'tracker-ci-attention';
        }

        const nameCell = make('td');
        nameCell.append(make('strong', group.name));
        nameCell.append(
          make(
            'small',
            `${group.sealed} sealed · ${group.inUse} in use`
          )
        );

        row.append(nameCell);
        row.append(make('td', group.records.length));

        const quantityCell = make('td');
        quantityCell.append(
          make('strong', totals(group.totals))
        );

        if (group.unknown) {
          quantityCell.append(
            make('small', `${group.unknown} unparsed`)
          );
        }

        row.append(quantityCell);

        row.append(
          make(
            'td',
            group.missingCOA
              ? `${group.missingCOA} missing`
              : 'Complete'
          )
        );

        const exposure = make('td');

        exposure.append(
          make(
            'span',
            `${group.past} past · ` +
            `${group.days7} ≤7d · ` +
            `${group.days30} 8–30d · ` +
            `${group.days90} 31–90d`
          )
        );

        if (group.exposed.size) {
          exposure.append(
            make(
              'small',
              `${totals(group.exposed)} dated ≤30 days`
            )
          );
        }

        row.append(exposure);

        const action = make('td');
        const button = make(
          'button',
          `Review ${group.needsReview}`,
          'tracker-ci-review'
        );

        button.type = 'button';

        button.addEventListener('click', () => {
          const lifecycle = byId('tracker-vial-lifecycle');
          const compoundFilter = byId(
            'tracker-lifecycle-compound'
          );
          const statusFilter = byId(
            'tracker-lifecycle-filter'
          );

          if (
            lifecycle && !lifecycle.hidden &&
            compoundFilter && statusFilter
          ) {
            compoundFilter.value = group.name;
            statusFilter.value = 'all';

            compoundFilter.dispatchEvent(
              new Event('change', { bubbles: true })
            );

            lifecycle.scrollIntoView({
              behavior: 'smooth',
              block: 'start'
            });

            return;
          }

          if (group.records.length) {
            location.assign(group.records[0].href);
          }
        });

        action.append(button);
        row.append(action);
        tbody.append(row);
      }

      table.append(thead, tbody);
      results.append(table);
    }

    search.addEventListener('input', render);
    sort.addEventListener('change', render);

    exportButton.addEventListener('click', () => {
      exportCSV(visible());
    });

    window.trackerCompoundInventoryDiagnostics = () => ({
      displayedCurrentVials: records.length,
      compounds: groups.length,
      unparsedQuantities: records.filter(
        record => !record.quantity
      ).length,
      missingCOA: records.filter(
        record => !record.coa
      ).length,
      needsReview: records.filter(
        record => record.needsReview
      ).length
    });

    panel.hidden = false;
    render();
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
