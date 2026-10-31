(() => {
  'use strict';

  const PREFIX = 'tracker-workspace-34107';

  function getContext() {
    const params = new URLSearchParams(
      window.location.search
    );

    const compoundId = params.get('compound_id');
    const plannedDate = params.get('planned_date');
    const plannedTime = params.get('planned_time');
    const plannedAmount = params.get('planned_amount');
    const plannedUnit = params.get('planned_unit');

    const dateValid =
      /^\d{4}-\d{2}-\d{2}$/.test(plannedDate || '') &&
      (() => {
        const date = new Date(
          plannedDate + 'T12:00:00'
        );

        return (
          !Number.isNaN(date.getTime()) &&
          date.getFullYear() ===
            Number(plannedDate.slice(0, 4)) &&
          date.getMonth() + 1 ===
            Number(plannedDate.slice(5, 7)) &&
          date.getDate() ===
            Number(plannedDate.slice(8, 10))
        );
      })();

    const compoundValid =
      /^\d+$/.test(compoundId || '') &&
      Number(compoundId) > 0;

    if (!compoundValid || !dateValid) {
      return null;
    }

    const timeValid =
      /^\d{2}:\d{2}$/.test(plannedTime || '') &&
      Number(plannedTime.slice(0, 2)) <= 23 &&
      Number(plannedTime.slice(3, 5)) <= 59;

    const amountValid =
      plannedAmount !== null &&
      plannedAmount.trim() !== '' &&
      Number.isFinite(Number(plannedAmount)) &&
      Number(plannedAmount) > 0;

    const allowedUnits = new Set([
      'mg', 'mcg', 'g', 'mL', 'IU', 'units'
    ]);

    return {
      compoundId,
      plannedDate,
      plannedTime: timeValid ? plannedTime : '',
      plannedAmount: amountValid
        ? plannedAmount
        : '',
      plannedUnit: allowedUnits.has(plannedUnit)
        ? plannedUnit
        : ''
    };
  }

  function setText(root, selector, value) {
    const target = root.querySelector(selector);

    if (target) {
      target.textContent = value;
    }
  }

  function compoundName(context) {
    const candidates = document.querySelectorAll(
      '[data-compound-id]'
    );

    for (const candidate of candidates) {
      if (
        candidate.dataset.compoundId ===
        context.compoundId
      ) {
        const name =
          candidate.dataset.compoundName;

        if (name) return name;
      }
    }

    return `Compound #${context.compoundId}`;
  }

  function applyContextToDoseLinks(context) {
    const links = document.querySelectorAll(
      'a[href]'
    );

    let updated = 0;

    for (const link of links) {
      const url = new URL(
        link.getAttribute('href'),
        window.location.href
      );

      if (
        url.origin !== window.location.origin ||
        url.pathname !== '/doses'
      ) {
        continue;
      }

      // Do not replace an existing compound or
      // planned value supplied by the original link.
      const values = {
        compound_id: context.compoundId,
        planned_date: context.plannedDate,
        planned_time: context.plannedTime,
        planned_amount: context.plannedAmount,
        planned_unit: context.plannedUnit
      };

      for (const [key, value] of Object.entries(values)) {
        if (
          value &&
          !url.searchParams.has(key)
        ) {
          url.searchParams.set(key, value);
        }
      }

      link.href = url.pathname + url.search + url.hash;

      link.dataset.trackerWorkspaceHandoff = '1';

      updated++;
    }

    return updated;
  }

  function initialize() {
    const panel = document.getElementById(
      `${PREFIX}-context`
    );

    if (!panel) return;

    const context = getContext();

    if (!context) {
      panel.hidden = true;
      return;
    }

    setText(
      panel,
      '[data-workspace-compound]',
      compoundName(context)
    );

    setText(
      panel,
      '[data-workspace-date]',
      context.plannedDate
    );

    setText(
      panel,
      '[data-workspace-time]',
      context.plannedTime || 'Not specified'
    );

    setText(
      panel,
      '[data-workspace-amount]',
      context.plannedAmount
        ? `${context.plannedAmount} ${context.plannedUnit}`.trim()
        : 'Not specified'
    );

    const calendarLink = panel.querySelector(
      '[data-workspace-calendar]'
    );

    calendarLink.href =
      '/calendar?month=' +
      encodeURIComponent(
        context.plannedDate.slice(0, 7)
      );

    const doseLink = panel.querySelector(
      '[data-workspace-dose]'
    );

    const doseParams = new URLSearchParams();

    doseParams.set(
      'compound_id',
      context.compoundId
    );

    doseParams.set(
      'planned_date',
      context.plannedDate
    );

    for (const [key, value] of Object.entries({
      planned_time: context.plannedTime,
      planned_amount: context.plannedAmount,
      planned_unit: context.plannedUnit
    })) {
      if (value) doseParams.set(key, value);
    }

    doseLink.href =
      '/doses?' + doseParams.toString();

    const updated = applyContextToDoseLinks(context);

    setText(
      panel,
      '[data-workspace-link-count]',
      updated
        ? `${updated} existing Dose Log link(s) retain schedule context.`
        : 'Use Record dose to continue.'
    );

    panel.hidden = false;
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
