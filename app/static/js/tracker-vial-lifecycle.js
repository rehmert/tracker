/*
 * Tracker Stage 34.38.1
 * Vial Lifecycle Overview
 *
 * Reads the existing vial table.
 * Does not modify inventory data.
 */

(() => {
  'use strict';

  function text(value) {
    return String(value || '').trim();
  }

  function parseDate(value) {
    const match = text(value).match(
      /^(\d{4})-(\d{2})-(\d{2})$/
    );

    if (!match) return null;

    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);

    const date = new Date(year, month - 1, day);

    if (
      date.getFullYear() !== year ||
      date.getMonth() !== month - 1 ||
      date.getDate() !== day
    ) {
      return null;
    }

    return date;
  }

  function daysUntil(value) {
    const date = parseDate(value);
    if (!date) return null;

    const now = new Date();

    const today = Date.UTC(
      now.getFullYear(),
      now.getMonth(),
      now.getDate()
    );

    const target = Date.UTC(
      date.getFullYear(),
      date.getMonth(),
      date.getDate()
    );

    return Math.round(
      (target - today) / 86400000
    );
  }

  function node(tag, className, value) {
    const result = document.createElement(tag);

    if (className) {
      result.className = className;
    }

    if (value !== undefined) {
      result.textContent = value;
    }

    return result;
  }

  function initialize() {
    const source = document.getElementById(
      'tracker-vials-sortable'
    );

    const panel = document.getElementById(
      'tracker-vial-lifecycle'
    );

    if (!source || !panel) return;

    const filter = document.getElementById(
      'tracker-lifecycle-filter'
    );

    const summary = document.getElementById(
      'tracker-lifecycle-summary'
    );

    const compoundFilter = document.createElement('select');
    compoundFilter.id = 'tracker-lifecycle-compound';
    compoundFilter.setAttribute(
      'aria-label',
      'Filter lifecycle review by compound'
    );

    const compoundLabel = document.createElement('label');
    compoundLabel.className = 'field';
    const compoundCaption = document.createElement('span');
    compoundCaption.textContent = 'Compound';
    compoundLabel.append(compoundCaption, compoundFilter);

    const controls = panel.querySelector(
      '.tracker-lifecycle-controls'
    );

    if (controls) controls.append(compoundLabel);

    const results = document.getElementById(
      'tracker-lifecycle-results'
    );

    if (!filter || !summary || !results) return;

    const records = Array.from(
      source.querySelectorAll('tbody tr')
    ).map(row => {
      const cells = row.querySelectorAll('td');

      if (cells.length < 9) return null;

      const status = text(
        row.dataset.attentionStatus
      );

      if (!['sealed', 'in_use'].includes(status)) {
        return null;
      }

      const link = cells[2].querySelector('a[href]');

      if (!link) return null;

      const href = link.getAttribute('href');

      if (
        !href ||
        !/^\/vials\/\d+(?:[?#].*)?$/.test(href)
      ) {
        return null;
      }

      const compound = text(cells[1].textContent);
      const label = text(link.textContent);

      const remaining = text(
        Array.from(cells[4].childNodes)
          .filter(child => child.nodeType === Node.TEXT_NODE)
          .map(child => child.textContent)
          .join(' ')
      );
      const coa = text(
        cells[7].textContent
      ).toLowerCase() === 'yes';

      const expires = text(
        row.dataset.attentionExpires
      );

      const beyondUse = text(
        row.dataset.attentionBeyondUse
      );

      const issues = [];

      [
        ['Expiration', expires],
        ['Beyond-use', beyondUse]
      ].forEach(([name, value]) => {
        const days = daysUntil(value);

        if (days === null) return;

        if (days < 0) {
          issues.push(`${name} date passed`);
        } else if (days === 0) {
          issues.push(`${name} date today`);
        } else if (days <= 30) {
          issues.push(`${name} in ${days} days`);
        }
      });

      if (!coa) {
        issues.push('COA missing');
      }

      return {
        compound,
        label,
        status,
        remaining,
        coa,
        expires,
        beyondUse,
        href,
        issues
      };
    }).filter(Boolean);

    const attentionCount = records.filter(
      record => record.issues.length > 0
    ).length;

    const compounds = new Map();

    records.forEach(record => {
      if (!compounds.has(record.compound)) {
        compounds.set(record.compound, {
          name: record.compound,
          total: 0,
          sealed: 0,
          inUse: 0,
          missingCOA: 0,
          needsReview: 0,
          dateWarnings: 0
        });
      }

      const entry = compounds.get(record.compound);

      entry.total++;

      if (record.status === 'sealed') entry.sealed++;
      if (record.status === 'in_use') entry.inUse++;
      if (!record.coa) entry.missingCOA++;

      if (record.issues.length) {
        entry.needsReview++;
      }

      if (record.issues.some(issue =>
        issue.startsWith('Expiration') ||
        issue.startsWith('Beyond-use')
      )) {
        entry.dateWarnings++;
      }
    });

    const compoundOptions = [
      ...compounds.keys()
    ].sort((a, b) => a.localeCompare(b));

    const allOption = document.createElement('option');
    allOption.value = '';
    allOption.textContent = 'All compounds';
    compoundFilter.append(allOption);

    compoundOptions.forEach(name => {
      const option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      compoundFilter.append(option);
    });

    const compoundOverview = document.createElement('div');
    compoundOverview.id = 'tracker-lifecycle-compounds';
    compoundOverview.className = 'tracker-lifecycle-compounds';

    const compoundHeading = document.createElement('h3');
    compoundHeading.textContent = 'Compounds needing review';

    const compoundCards = document.createElement('div');
    compoundCards.className = 'tracker-lifecycle-compound-grid';

    const flaggedCompounds = [
      ...compounds.values()
    ].filter(entry => entry.needsReview > 0)
      .sort((a, b) =>
        b.needsReview - a.needsReview ||
        a.name.localeCompare(b.name)
      );

    flaggedCompounds.forEach(entry => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'tracker-lifecycle-compound-card';

      const title = document.createElement('strong');
      title.textContent = entry.name;

      const detail = document.createElement('span');
      detail.textContent =
        `${entry.needsReview} of ${entry.total} need review`;

      const meta = document.createElement('small');
      meta.textContent =
        `${entry.sealed} sealed · ` +
        `${entry.inUse} in use · ` +
        `${entry.missingCOA} missing COA · ` +
        `${entry.dateWarnings} date warnings`;

      button.append(title, detail, meta);

      button.addEventListener('click', () => {
        compoundFilter.value = entry.name;
        filter.value = 'attention';
        render();

        panel.querySelector(
          '.tracker-lifecycle-controls'
        )?.scrollIntoView({
          block: 'nearest',
          behavior: 'smooth'
        });
      });

      compoundCards.append(button);
    });

    if (flaggedCompounds.length) {
      compoundOverview.append(
        compoundHeading,
        compoundCards
      );

      const controls = panel.querySelector(
        '.tracker-lifecycle-controls'
      );

      if (controls) {
        controls.before(compoundOverview);
      }
    }

    // Do not waste space when there are no issues.
    if (!attentionCount) {
      panel.hidden = true;
      return;
    }

    function render() {
      const choice = filter.value;

      const matching = records.filter(record => {
        if (
          compoundFilter.value &&
          record.compound !== compoundFilter.value
        ) {
          return false;
        }

        switch (choice) {
          case 'attention':
            return record.issues.length > 0;
          case 'sealed':
            return record.status === 'sealed';
          case 'in_use':
            return record.status === 'in_use';
          case 'missing_coa':
            return !record.coa;
          default:
            return true;
        }
      });

      summary.textContent =
        `${matching.length} of ${records.length} vials`;

      results.replaceChildren();

      if (!matching.length) {
        results.append(
          node(
            'p',
            'note',
            'No vials match this filter.'
          )
        );
        return;
      }

      const scroll = node(
        'div',
        'scroll tracker-lifecycle-scroll'
      );

      const table = node(
        'table',
        'tracker-lifecycle-table'
      );

      const thead = document.createElement('thead');
      const headingRow = document.createElement('tr');

      [
        'Compound / vial',
        'Status',
        'Remaining',
        'Expiration',
        'Beyond use',
        'COA',
        'Review'
      ].forEach(label => {
        headingRow.append(
          node('th', '', label)
        );
      });

      thead.append(headingRow);

      const tbody = document.createElement('tbody');

      matching.forEach(record => {
        const row = document.createElement('tr');

        if (record.issues.length) {
          row.classList.add(
            'tracker-lifecycle-attention'
          );
        }

        const nameCell = document.createElement('td');
        const link = document.createElement('a');

        link.href = record.href;
        link.textContent =
          `${record.compound} — ${record.label}`;

        nameCell.append(link);
        row.append(nameCell);

        [
          record.status.replace('_', ' '),
          record.remaining,
          record.expires || '—',
          record.beyondUse || '—',
          record.coa ? 'Yes' : 'Missing'
        ].forEach(value => {
          row.append(
            node('td', '', value)
          );
        });

        const review = document.createElement('td');

        if (record.issues.length) {
          const list = node(
            'ul',
            'tracker-lifecycle-issues'
          );

          record.issues.forEach(issue => {
            list.append(
              node('li', '', issue)
            );
          });

          review.append(list);
        } else {
          review.textContent = 'No flagged items';
        }

        row.append(review);
        tbody.append(row);
      });

      table.append(thead, tbody);
      scroll.append(table);
      results.append(scroll);
    }

    filter.addEventListener('change', render);
    compoundFilter.addEventListener('change', render);

    panel.hidden = false;
    render();

    window.trackerVialLifecycleDiagnostics = () => ({
      total: records.length,
      sealed: records.filter(
        record => record.status === 'sealed'
      ).length,
      inUse: records.filter(
        record => record.status === 'in_use'
      ).length,
      missingCOA: records.filter(
        record => !record.coa
      ).length,
      needsReview: attentionCount,
      compounds: [...compounds.values()]
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
