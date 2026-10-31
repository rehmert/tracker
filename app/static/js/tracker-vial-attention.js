/*
 * Tracker Stage 34.2 — Inventory attention indicators.
 * Display-only: no requests, forms, or inventory mutations.
 */
(() => {
  'use strict';

  const SOON_DAYS = 30;
  const LOW_PERCENT = 20;

  function init() {
    const table = document.getElementById(
      'tracker-vials-sortable'
    );
    const panel = document.getElementById(
      'tracker-vial-attention'
    );

    if (!table || !panel) return;

    const totals = {
      expired: 0,
      soon: 0,
      low: 0,
      depleted: 0
    };

    const today = new Date();
    const todayUTC = Date.UTC(
      today.getFullYear(),
      today.getMonth(),
      today.getDate()
    );

    function daysUntil(value) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) {
        return null;
      }

      const [year, month, day] = value
        .split('-')
        .map(Number);

      const date = Date.UTC(year, month - 1, day);
      const valid = new Date(date);

      if (
        valid.getUTCFullYear() !== year ||
        valid.getUTCMonth() !== month - 1 ||
        valid.getUTCDate() !== day
      ) {
        return null;
      }

      return Math.round(
        (date - todayUTC) / 86400000
      );
    }

    function badge(cell, label, kind) {
      const element = document.createElement('span');
      element.className =
        'tracker-attention-badge ' + kind;
      element.textContent = label;
      cell.appendChild(element);
    }

    table.querySelectorAll(
      'tbody tr[data-attention-status]'
    ).forEach(row => {
      const cell = row.cells[2];
      if (!cell) return;

      const status = row.dataset.attentionStatus;
      const closed = (
        status === 'finished' ||
        status === 'discarded'
      );

      const remaining = Number(
        row.dataset.attentionRemaining
      );

      const percentText = row.dataset.attentionPercent;
      const percent = percentText === ''
        ? NaN
        : Number(percentText);

      if (closed) return;

      const dates = [
        {
          label: 'Expiration',
          value: row.dataset.attentionExpires
        },
        {
          label: 'Beyond-use',
          value: row.dataset.attentionBeyondUse
        }
      ];

      let past = false;
      let approaching = false;

      dates.forEach(entry => {
        const days = daysUntil(entry.value);

        if (days === null) return;

        if (days < 0) {
          past = true;
          badge(
            cell,
            entry.label + ' date passed',
            'critical'
          );
        } else if (days <= SOON_DAYS) {
          approaching = true;
          badge(
            cell,
            entry.label + ': ' +
              (days === 0 ? 'today' : days + ' days'),
            'warning'
          );
        }
      });

      if (past) {
        totals.expired++;
      } else if (approaching) {
        totals.soon++;
      }

      if (
        Number.isFinite(remaining) &&
        remaining <= 0
      ) {
        totals.depleted++;
        badge(cell, 'Depleted', 'critical');
      } else if (
        Number.isFinite(percent) &&
        percent >= 0 &&
        percent <= LOW_PERCENT
      ) {
        totals.low++;
        badge(cell, 'Low inventory', 'warning');
      }
    });

    const labels = {
      expired: 'past date',
      soon: 'approaching date',
      low: 'low',
      depleted: 'depleted'
    };

    Object.entries(labels).forEach(([key, label]) => {
      const element = document.getElementById(
        'tracker-attention-' + key
      );
      if (element) {
        element.textContent =
          totals[key].toLocaleString() + ' ' + label;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      init,
      { once: true }
    );
  } else {
    init();
  }
})();
