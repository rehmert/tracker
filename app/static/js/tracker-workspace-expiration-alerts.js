/*
 * Tracker Stage 34.26
 * Read-only inventory expiration alerts.
 *
 * Checks all loaded vial rows, including rows hidden
 * by the smart vial display limit.
 */

(() => {
  'use strict';

  function init() {
    const container = document.getElementById(
      'tracker-available-vials'
    );

    if (!container) return;

    const table = container.querySelector(
      '[data-tracker-sortable-vials]'
    );

    if (!table) return;

    const rows = Array.from(
      table.querySelectorAll('[data-tracker-vial-row]')
    );

    if (!rows.length) return;

    const MS_PER_DAY = 86400000;

    function parseDate(value) {
      if (!value) return null;

      const match = String(value).match(
        /^(\d{4})-(\d{2})-(\d{2})$/
      );

      if (!match) return null;

      const year = Number(match[1]);
      const month = Number(match[2]);
      const day = Number(match[3]);

      const timestamp = Date.UTC(year, month - 1, day);
      const parsed = new Date(timestamp);

      if (
        parsed.getUTCFullYear() !== year ||
        parsed.getUTCMonth() !== month - 1 ||
        parsed.getUTCDate() !== day
      ) {
        return null;
      }

      return timestamp;
    }

    function todayUTC() {
      const now = new Date();

      return Date.UTC(
        now.getFullYear(),
        now.getMonth(),
        now.getDate()
      );
    }

    function summarize() {
      const today = todayUTC();

      const summary = {
        expired: 0,
        expiring: 0,
        beyondUse: 0,
        approachingBeyondUse: 0,
        unknown: 0,
        affected: new Set()
      };

      rows.forEach(row => {
        const id = row.dataset.trackerId || '';

        const expires = parseDate(
          row.dataset.trackerExpires
        );

        const beyondUse = parseDate(
          row.dataset.trackerBeyondUse
        );

        const status = (
          row.dataset.trackerStatus || ''
        ).toLowerCase();

        // Don't count vials already consumed or discarded.
        if (
          [
            'empty',
            'depleted',
            'discarded',
            'disposed'
          ].includes(status)
        ) {
          return;
        }

        if (expires === null && beyondUse === null) {
          summary.unknown++;
        }

        if (expires !== null) {
          const days = Math.round(
            (expires - today) / MS_PER_DAY
          );

          if (days < 0) {
            summary.expired++;
            summary.affected.add(id);
          } else if (days <= 30) {
            summary.expiring++;
            summary.affected.add(id);
          }
        }

        if (beyondUse !== null) {
          const days = Math.round(
            (beyondUse - today) / MS_PER_DAY
          );

          if (days < 0) {
            summary.beyondUse++;
            summary.affected.add(id);
          } else if (days <= 30) {
            summary.approachingBeyondUse++;
            summary.affected.add(id);
          }
        }
      });

      return summary;
    }

    const alert = document.createElement('div');
    alert.id = 'tracker-workspace-expiration-alerts';
    alert.className = 'card';
    alert.setAttribute('role', 'status');
    alert.setAttribute('aria-live', 'polite');

    alert.style.marginBottom = '0.8rem';
    alert.style.padding = '0.85rem 1rem';

    const title = document.createElement('strong');
    title.textContent = 'Inventory date alerts';

    const details = document.createElement('p');
    details.style.margin = '0.4rem 0';

    const note = document.createElement('small');
    note.className = 'note';

    note.textContent =
      'Includes vials hidden by the display limit. ' +
      'Dates are informational; verify vial labels ' +
      'and storage conditions before use.';

    const actions = document.createElement('div');
    actions.style.marginTop = '0.6rem';

    const reveal = document.createElement('button');
    reveal.type = 'button';
    reveal.textContent = 'Show all inventory';
    reveal.style.marginRight = '0.5rem';

    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.textContent = 'Refresh alerts';

    actions.append(reveal, refresh);
    alert.append(title, details, note, actions);

    container.parentNode.insertBefore(alert, container);

    function render() {
      const result = summarize();

      const messages = [];

      if (result.expired) {
        messages.push(
          `${result.expired} expired`
        );
      }

      if (result.expiring) {
        messages.push(
          `${result.expiring} expiring within 30 days`
        );
      }

      if (result.beyondUse) {
        messages.push(
          `${result.beyondUse} past beyond-use date`
        );
      }

      if (result.approachingBeyondUse) {
        messages.push(
          `${result.approachingBeyondUse} approaching ` +
          'beyond-use date'
        );
      }

      if (!messages.length) {
        details.textContent =
          'No recorded expiration or beyond-use dates ' +
          'fall within the next 30 days.';
      } else {
        details.textContent = messages.join(' · ');
      }

      if (result.unknown) {
        details.textContent +=
          ` · ${result.unknown} without recorded dates`;
      }

      const hasAlerts =
        result.expired ||
        result.expiring ||
        result.beyondUse ||
        result.approachingBeyondUse;

      alert.style.borderLeft = hasAlerts
        ? '4px solid #d97706'
        : '4px solid #16a34a';

      window.trackerExpirationDiagnostics = () => ({
        loadedVials: rows.length,
        expired: result.expired,
        expiringWithin30Days: result.expiring,
        pastBeyondUse: result.beyondUse,
        approachingBeyondUse: result.approachingBeyondUse,
        missingDates: result.unknown,
        uniqueAffectedVials: result.affected.size
      });
    }

    reveal.addEventListener('click', () => {
      const limit = document.getElementById(
        'tracker-vial-display-limit'
      );

      const search = document.getElementById(
        'tracker-vial-search'
      );

      if (search && search.value) {
        search.value = '';
        search.dispatchEvent(
          new Event('input', { bubbles: true })
        );
      }

      if (limit) {
        limit.value = 'all';
        limit.dispatchEvent(
          new Event('change', { bubbles: true })
        );
      }

      container.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      });
    });

    refresh.addEventListener('click', render);

    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
