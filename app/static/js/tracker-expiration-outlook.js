/*
 * Tracker Stage 34.36
 * Inventory Expiration Outlook
 *
 * Read-only view of existing inventory alerts.
 * Does not calculate or modify vial expiration dates.
 */

(() => {
  'use strict';

  const GROUPS = [
    {
      key: 'overdue',
      label: 'Past date',
      description: 'Recorded date has passed'
    },
    {
      key: 'week',
      label: 'Next 7 days',
      description: 'Immediate review'
    },
    {
      key: 'month',
      label: '8–30 days',
      description: 'Approaching'
    },
    {
      key: 'sixty',
      label: '31–60 days',
      description: 'Upcoming'
    },
    {
      key: 'ninety',
      label: '61–90 days',
      description: 'Longer-term outlook'
    }
  ];

  function element(tag, className, content) {
    const node = document.createElement(tag);

    if (className) {
      node.className = className;
    }

    if (content !== undefined) {
      node.textContent = content;
    }

    return node;
  }

  function normalize(value) {
    return String(value || '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function parseDate(value) {
    const text = normalize(value);

    // Accept ISO dates and dates beginning with ISO dates.
    const iso = text.match(
      /^(\d{4})-(\d{1,2})-(\d{1,2})(?:$|[T\s])/
    );

    let year;
    let month;
    let day;

    if (iso) {
      year = Number(iso[1]);
      month = Number(iso[2]);
      day = Number(iso[3]);
    } else {
      // Also accept common US-formatted dates.
      const us = text.match(
        /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/
      );

      if (!us) return null;

      month = Number(us[1]);
      day = Number(us[2]);
      year = Number(us[3]);
    }

    const result = new Date(
      year,
      month - 1,
      day
    );

    // Reject normalized invalid dates such as February 30.
    if (
      result.getFullYear() !== year ||
      result.getMonth() !== month - 1 ||
      result.getDate() !== day
    ) {
      return null;
    }

    return result;
  }

  function daysUntil(date) {
    const now = new Date();

    const todayUTC = Date.UTC(
      now.getFullYear(),
      now.getMonth(),
      now.getDate()
    );

    const targetUTC = Date.UTC(
      date.getFullYear(),
      date.getMonth(),
      date.getDate()
    );

    return Math.round(
      (targetUTC - todayUTC) / 86400000
    );
  }

  function classify(days) {
    if (days < 0) return 'overdue';
    if (days <= 7) return 'week';
    if (days <= 30) return 'month';
    if (days <= 60) return 'sixty';
    if (days <= 90) return 'ninety';

    return null;
  }

  function expirationRelated(category, reason) {
    const text = `${category} ${reason}`.toLowerCase();

    return (
      /\bexpir(?:e|ed|es|ing|ation|y)\b/.test(text) ||
      /\bbeyond[\s-]*use\b/.test(text) ||
      /\b(?:bud|b\.u\.d\.)\b/.test(text)
    );
  }

  function createRecord(record) {
    const item = element(
      'li',
      'tracker-expiry-item'
    );

    const link = element(
      'a',
      'tracker-expiry-link'
    );

    link.href = record.href;

    const name = element(
      'strong',
      'tracker-expiry-name',
      record.name
    );

    const detail = element(
      'span',
      'tracker-expiry-detail',
      `${record.reason} · ${record.dateText}`
    );

    const remaining = element(
      'span',
      'tracker-expiry-days'
    );

    if (record.days < 0) {
      remaining.textContent =
        `${Math.abs(record.days)}d past`;
    } else if (record.days === 0) {
      remaining.textContent = 'Today';
    } else {
      remaining.textContent = `${record.days}d`;
    }

    const text = element(
      'span',
      'tracker-expiry-text'
    );

    text.append(name, detail);

    link.append(text, remaining);
    item.append(link);

    return item;
  }

  function initialize() {
    const table = document.querySelector(
      'table.alert-table'
    );

    if (!table) return;

    if (document.getElementById(
      'tracker-expiration-outlook'
    )) {
      return;
    }

    const headers = Array.from(
      table.querySelectorAll('thead th')
    ).map(cell =>
      normalize(cell.textContent).toLowerCase()
    );

    const categoryIndex = headers.indexOf('category');
    const itemIndex = headers.indexOf('item');
    const reasonIndex = headers.indexOf('reason');
    const dateIndex = headers.indexOf('relevant date');

    if (
      categoryIndex < 0 ||
      itemIndex < 0 ||
      reasonIndex < 0 ||
      dateIndex < 0
    ) {
      return;
    }

    const records = [];

    Array.from(table.tBodies[0]?.rows || [])
      .forEach(row => {
        if (row.cells.length !== headers.length) {
          return;
        }

        const category = normalize(
          row.cells[categoryIndex].textContent
        );

        const reason = normalize(
          row.cells[reasonIndex].textContent
        );

        if (!expirationRelated(category, reason)) {
          return;
        }

        const dateText = normalize(
          row.cells[dateIndex].textContent
        );

        const date = parseDate(dateText);

        if (!date) return;

        const days = daysUntil(date);
        const group = classify(days);

        if (!group) return;

        const itemCell = row.cells[itemIndex];
        const originalLink = itemCell.querySelector(
          'a[href]'
        );

        if (!originalLink) return;

        const href = originalLink.getAttribute('href');

        // Only link to internal Tracker paths.
        if (!href || !href.startsWith('/') ||
            href.startsWith('//')) {
          return;
        }

        records.push({
          category,
          reason,
          dateText,
          days,
          group,
          name: normalize(originalLink.textContent),
          href
        });
      });

    // Do not consume page space if there are no
    // qualifying expiration or beyond-use alerts.
    if (!records.length) return;

    records.sort((a, b) => a.days - b.days);

    const section = element(
      'section',
      'tracker-expiry-outlook'
    );

    section.id = 'tracker-expiration-outlook';
    section.setAttribute(
      'aria-labelledby',
      'tracker-expiry-heading'
    );

    const header = element(
      'div',
      'tracker-expiry-header'
    );

    const heading = element(
      'h2',
      '',
      'Expiration outlook'
    );

    heading.id = 'tracker-expiry-heading';

    const summary = element(
      'span',
      'tracker-expiry-summary',
      `${records.length} dated alert${
        records.length === 1 ? '' : 's'
      }`
    );

    header.append(heading, summary);
    section.append(header);

    const grid = element(
      'div',
      'tracker-expiry-grid'
    );

    GROUPS.forEach(group => {
      const matching = records.filter(
        record => record.group === group.key
      );

      if (!matching.length) return;

      const card = element(
        'div',
        'tracker-expiry-group'
      );

      card.dataset.group = group.key;

      const cardHeader = element(
        'div',
        'tracker-expiry-group-header'
      );

      const title = element(
        'strong',
        '',
        group.label
      );

      const count = element(
        'span',
        'tracker-expiry-group-count',
        String(matching.length)
      );

      cardHeader.append(title, count);

      const description = element(
        'p',
        'tracker-expiry-group-description',
        group.description
      );

      const list = element(
        'ul',
        'tracker-expiry-list'
      );

      matching.forEach(record => {
        list.append(createRecord(record));
      });

      card.append(
        cardHeader,
        description,
        list
      );

      grid.append(card);
    });

    section.append(grid);

    const note = element(
      'p',
      'tracker-expiry-note',
      'Based on dated expiration and beyond-use alerts ' +
      'within the selected alert horizon. ' +
      'Records without usable dates are not shown.'
    );

    section.append(note);

    const form = document.querySelector(
      'form[action="/inventory-alerts"]'
    );

    if (form) {
      form.after(section);
    } else {
      table.closest('.scroll')?.before(section);
    }

    window.trackerExpirationOutlookDiagnostics = () => ({
      total: records.length,
      groups: Object.fromEntries(
        GROUPS.map(group => [
          group.key,
          records.filter(
            record => record.group === group.key
          ).length
        ])
      )
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
