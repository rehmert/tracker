/*
 * Lab-entry navigation helpers.
 * No network calls, persistence, form submission,
 * or changes to measured laboratory values.
 */
(() => {
  'use strict';

  function setupSourceSearch() {
    const input = document.querySelector(
      '[data-lab-source-search]'
    );
    const select = document.querySelector(
      '#lab-source-report'
    );
    const count = document.querySelector(
      '[data-lab-source-count]'
    );

    if (!input || !select || !count) return;

    const originals = Array.from(select.options)
      .map(option => option.cloneNode(true));
    const total = originals.filter(
      option => option.value
    ).length;

    function update() {
      const query = input.value
        .trim()
        .toLocaleLowerCase();

      const selected = select.value;
      const matching = originals.filter(
        option =>
          !option.value ||
          option.textContent.toLocaleLowerCase()
            .includes(query)
      );

      select.replaceChildren(
        ...matching.map(option =>
          option.cloneNode(true)
        )
      );

      // Keep the original selection when still
      // visible. Never pick another source silently.
      const stillAvailable = matching.some(
        option => option.value === selected
      );

      select.value = stillAvailable ? selected : '';

      const visible = matching.filter(
        option => option.value
      ).length;

      count.textContent =
        'Showing ' + visible +
        ' of ' + total + ' source reports';

      if (!visible) {
        count.textContent +=
          '. No matching reports; change the search.';
      }
    }

    input.addEventListener('input', update);
    update();
  }

  function setupIncompleteNavigation() {
    const form = document.querySelector(
      'form[data-lab-manual-entry]'
    );
    if (!form) return;

    const tbody = form.querySelector('#lab-rows');
    const button = form.querySelector(
      '[data-lab-find-incomplete]'
    );
    const message = form.querySelector(
      '[data-lab-navigation-message]'
    );
    if (!tbody || !button || !message) return;

    function field(row, name) {
      return row.querySelector(
        '[name="' + name + '"]'
      );
    }

    function findProblem(row) {
      const analyte = field(row, 'analyte');
      const value = field(row, 'value');
      const unit = field(row, 'unit');
      const low = field(row, 'ref_low');
      const high = field(row, 'ref_high');

      const inputs = [
        analyte, value, unit, low, high
      ];

      if (inputs.some(input => !input)) {
        return null;
      }

      const hasAny = inputs.some(
        input => input.value.trim() !== ''
      );

      if (!hasAny) return null;

      if (!analyte.value.trim()) {
        return [analyte, 'Analyte name'];
      }
      if (!value.value.trim() ||
          !value.validity.valid) {
        return [value, 'Measured value'];
      }
      if (!unit.value.trim()) {
        return [unit, 'Unit'];
      }

      const hasLow = low.value.trim() !== '';
      const hasHigh = high.value.trim() !== '';

      if (hasLow && !low.validity.valid) {
        return [low, 'Printed range low'];
      }
      if (hasHigh && !high.validity.valid) {
        return [high, 'Printed range high'];
      }
      if (hasLow !== hasHigh) {
        return [
          hasLow ? high : low,
          'Complete both printed-range endpoints'
        ];
      }
      if (hasLow &&
          Number(low.value) > Number(high.value)) {
        return [high, 'Printed range order'];
      }

      return null;
    }

    let previous = -1;

    button.addEventListener('click', () => {
      const rows = Array.from(
        tbody.querySelectorAll('tr')
      );

      const problems = rows.map(
        (row, index) => ({
          index,
          problem: findProblem(row)
        })
      ).filter(item => item.problem);

      if (!problems.length) {
        message.textContent =
          'No incomplete entered rows found. ' +
          'Review duplicates and the report before saving.';
        previous = -1;
        return;
      }

      const next = problems.find(
        item => item.index > previous
      ) || problems[0];

      previous = next.index;

      const [target, reason] = next.problem;
      target.focus();
      target.scrollIntoView({
        block: 'center',
        behavior: 'auto'
      });

      message.textContent =
        'Row ' + (next.index + 1) +
        ': ' + reason +
        ' (' + problems.length +
        ' incomplete entered rows total).';
    });

    tbody.addEventListener('input', () => {
      previous = -1;
    });
    tbody.addEventListener('change', () => {
      previous = -1;
    });
  }

  function initialize() {
    setupSourceSearch();
    setupIncompleteNavigation();
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded', initialize, { once: true }
    );
  } else {
    initialize();
  }
})();
