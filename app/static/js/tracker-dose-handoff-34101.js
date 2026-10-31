(() => {
  'use strict';

  function initialize() {
    const panel = document.getElementById(
      'tracker-planned-handoff'
    );

    if (!panel) return;

    const params = new URLSearchParams(
      window.location.search
    );

    const compoundId = params.get('compound_id');
    const plannedDate = params.get('planned_date');
    const plannedTime = params.get('planned_time');
    const plannedAmount = params.get('planned_amount');
    const plannedUnit = params.get('planned_unit');

    if (!compoundId || !plannedDate) return;

    const datePattern = /^\d{4}-\d{2}-\d{2}$/;

    if (!datePattern.test(plannedDate)) return;

    const date = new Date(plannedDate + 'T12:00:00');

    if (
      Number.isNaN(date.getTime()) ||
      date.getFullYear() !== Number(plannedDate.slice(0, 4)) ||
      date.getMonth() + 1 !== Number(plannedDate.slice(5, 7)) ||
      date.getDate() !== Number(plannedDate.slice(8, 10))
    ) {
      return;
    }

    const setText = (selector, value) => {
      const element = panel.querySelector(selector);
      if (element) element.textContent = value;
    };

    const vialSelect = document.querySelector(
      'select[name="vial_id"]'
    );

    const compoundOption = vialSelect
      ? Array.from(vialSelect.options).find(
          option =>
            option.dataset.compoundId === compoundId
        )
      : null;

    setText(
      '[data-planned-compound]',
      compoundOption?.dataset.compoundName ||
        'Compound #' + compoundId
    );

    setText(
      '[data-planned-date]',
      plannedDate
    );

    setText(
      '[data-planned-time]',
      /^\d{2}:\d{2}$/.test(plannedTime || '')
        ? plannedTime
        : 'Not specified'
    );

    const validAmount =
      plannedAmount !== null &&
      plannedAmount.trim() !== '' &&
      Number.isFinite(Number(plannedAmount)) &&
      Number(plannedAmount) > 0;

    setText(
      '[data-planned-amount]',
      validAmount
        ? `${plannedAmount} ${plannedUnit || ''}`.trim()
        : 'Not specified'
    );

    const calendar = panel.querySelector(
      '[data-planned-calendar]'
    );

    calendar.href =
      '/calendar?month=' +
      encodeURIComponent(plannedDate.slice(0, 7));

    const workspace = panel.querySelector(
      '[data-planned-workspace]'
    );

    const context = new URLSearchParams();

    context.set('compound_id', compoundId);
    context.set('planned_date', plannedDate);

    if (/^\d{2}:\d{2}$/.test(plannedTime || '')) {
      context.set('planned_time', plannedTime);
    }

    if (validAmount) {
      context.set('planned_amount', plannedAmount);
    }

    if (plannedUnit) {
      context.set('planned_unit', plannedUnit);
    }

    workspace.href =
      '/dose-workspace?' + context.toString();

    const warning = panel.querySelector(
      '[data-planned-vial-warning]'
    );

    function checkVial() {
      if (!vialSelect) {
        warning.textContent =
          'No vial selector was found.';
        warning.hidden = false;
        return;
      }

      const selected = vialSelect.selectedOptions[0];

      if (
        selected &&
        selected.dataset.compoundId &&
        selected.dataset.compoundId !== compoundId
      ) {
        warning.textContent =
          'The selected vial belongs to a different ' +
          'compound than the planned entry.';
        warning.hidden = false;
      } else {
        warning.textContent = '';
        warning.hidden = true;
      }
    }

    vialSelect?.addEventListener(
      'change',
      checkVial
    );

    checkVial();

    const amountInput = document.querySelector(
      'input[name="amount"]'
    );

    const unitSelect = document.querySelector(
      'select[name="unit"]'
    );

    const timeInput = document.querySelector(
      'input[name="taken_at"]'
    );

    const discrepancy = panel.querySelector(
      '[data-planned-discrepancy]'
    );

    function checkChanges() {
      const changes = [];

      if (
        validAmount &&
        amountInput &&
        Number(amountInput.value) !== Number(plannedAmount)
      ) {
        changes.push('amount');
      }

      if (
        plannedUnit &&
        unitSelect &&
        unitSelect.value !== plannedUnit
      ) {
        changes.push('unit');
      }

      if (
        timeInput &&
        plannedTime &&
        timeInput.value !==
          `${plannedDate}T${plannedTime}`
      ) {
        changes.push('administration time');
      }

      discrepancy.hidden = changes.length === 0;

      discrepancy.textContent = changes.length
        ? 'The entered ' + changes.join(', ') +
          ' differs from the planned entry.'
        : '';
    }

    for (const element of [
      amountInput,
      unitSelect,
      timeInput
    ]) {
      element?.addEventListener('input', checkChanges);
      element?.addEventListener('change', checkChanges);
    }

    checkChanges();

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
