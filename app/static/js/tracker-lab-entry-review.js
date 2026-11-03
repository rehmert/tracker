/*
 * Lab manual-entry completeness review.
 *
 * Informational only: does not change input values,
 * submit forms, or replace server validation.
 */
(() => {
  'use strict';

  function initialize() {
    const form = document.querySelector(
      'form[data-lab-manual-entry]'
    );
    if (!form || form.dataset.reviewEnhanced) return;

    const tbody = form.querySelector('#lab-rows');
    const review = form.querySelector(
      '[data-lab-entry-review]'
    );
    const count = form.querySelector(
      '[data-lab-complete-count]'
    );
    const message = form.querySelector(
      '[data-lab-review-message]'
    );

    if (!tbody || !review || !count || !message) {
      return;
    }

    form.dataset.reviewEnhanced = 'true';

    function field(row, name) {
      return row.querySelector(
        '[name="' + name + '"]'
      )?.value.trim() || '';
    }

    function reviewRows() {
      const rows = Array.from(
        tbody.querySelectorAll('tr')
      );

      let complete = 0;
      let incomplete = 0;
      let partialRanges = 0;
      let reversedRanges = 0;
      let blank = 0;

      rows.forEach(row => {
        const analyte = field(row, 'analyte');
        const value = field(row, 'value');
        const unit = field(row, 'unit');
        const low = field(row, 'ref_low');
        const high = field(row, 'ref_high');

        const hasAny = [
          analyte, value, unit, low, high
        ].some(Boolean);

        if (!hasAny) {
          blank++;
          row.removeAttribute('data-lab-review-state');
          return;
        }

        const rangePartial =
          Boolean(low) !== Boolean(high);

        const rangeReversed =
          Boolean(low) &&
          Boolean(high) &&
          Number(low) > Number(high);

        if (rangePartial) partialRanges++;
        if (rangeReversed) reversedRanges++;

        const ready =
          Boolean(analyte) &&
          value !== '' &&
          Boolean(unit) &&
          !rangePartial &&
          !rangeReversed;

        if (ready) {
          complete++;
        } else {
          incomplete++;
        }

        row.dataset.labReviewState =
          ready ? 'complete' : 'incomplete';
      });

      count.textContent =
        complete + ' complete result' +
        (complete === 1 ? '' : 's');

      const details = [];

      if (incomplete) {
        details.push(
          incomplete + ' incomplete row' +
          (incomplete === 1 ? '' : 's')
        );
      }

      if (partialRanges) {
        details.push(
          partialRanges + ' partial reference range' +
          (partialRanges === 1 ? '' : 's')
        );
      }

      if (reversedRanges) {
        details.push(
          reversedRanges + ' reversed reference range' +
          (reversedRanges === 1 ? '' : 's')
        );
      }

      if (blank) {
        details.push(
          blank + ' empty row' +
          (blank === 1 ? '' : 's') +
          ' ignored'
        );
      }

      if (!complete && !incomplete) {
        details.unshift('No results entered');
      }

      message.textContent = details.length
        ? details.join(' · ')
        : 'All entered rows appear complete.';

      review.dataset.labReviewStatus =
        incomplete ? 'review' : 'ready';
    }

    // Delegation covers rows inserted by HTMX.
    tbody.addEventListener('input', reviewRows);
    tbody.addEventListener('change', reviewRows);

    // Removing a row happens through an existing
    // HTMX inline click handler.
    tbody.addEventListener('click', event => {
      if (event.target.closest('button')) {
        queueMicrotask(reviewRows);
      }
    });

    // The Add row button uses HTMX beforeend.
    document.body.addEventListener(
      'htmx:afterSwap',
      event => {
        if (
          event.detail?.target === tbody ||
          tbody.contains(event.detail?.target)
        ) {
          reviewRows();
        }
      }
    );

    reviewRows();
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded', initialize, { once: true }
    );
  } else {
    initialize();
  }
})();
