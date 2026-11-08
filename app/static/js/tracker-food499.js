/* Release 499: non-destructive completeness and serving review before logging. */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  const form = document.getElementById('food-entry-form');
  const status = document.getElementById('food499-review-status');
  const preview = document.getElementById('food499-macro-preview');
  if (!form || !status || !preview) return;

  const nutrients = [
    ['energy', 'Cal'],
    ['proteins', 'P'],
    ['carbohydrates', 'C'],
    ['fat', 'F']
  ];

  function refresh() {
    const serving = form.querySelector('#food-serving')?.value.trim() || 'unspecified serving';
    const quantity = form.querySelector('input[name="servings"]');
    const rawQuantity = quantity?.value.trim() || '';
    const amount = Number(rawQuantity);
    const validAmount = rawQuantity !== '' &&
      Number.isFinite(amount) && amount > 0 && amount <= 100;

    preview.replaceChildren();
    const missing = [];

    for (const [key, label] of nutrients) {
      const raw = form.querySelector('#food-nutrient-' + key)?.value.trim() || '';
      const value = raw === '' ? NaN : Number(raw);
      const reported = raw !== '' && Number.isFinite(value) && value >= 0;
      if (!reported) missing.push(label);

      const cell = document.createElement('span');
      const total = reported && validAmount
        ? Math.round(value * amount * 10) / 10
        : null;
      cell.textContent = label + ' ' + (total === null ? '?' : String(total));
      preview.appendChild(cell);
    }

    const counted = nutrients.length - missing.length;
    status.textContent =
      'Review ' + serving + ' × ' + (validAmount ? rawQuantity : '?') +
      ': ' + counted + ' of 4 core values reported. ' +
      (missing.length
        ? 'Unknown: ' + missing.join(', ') + '. Unknown is not zero.'
        : 'All four core values are reported.') +
      ' Check the package label and serving basis before saving.';
  }

  form.addEventListener('input', refresh);
  form.addEventListener('change', refresh);
  form.addEventListener('food:nutrition-loaded', refresh);
  refresh();
});
