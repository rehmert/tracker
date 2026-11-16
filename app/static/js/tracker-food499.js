/* Release 499: non-destructive completeness and serving review before logging. */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  const form = document.getElementById('food-entry-form');
  const status = document.getElementById('food499-review-status');
  const preview = document.getElementById('food499-macro-preview');
  if (!form || !status || !preview) return;

  const nutrients = [
    ['energy', 'Calories'], ['proteins', 'Protein'],
    ['carbohydrates', 'Carbs'], ['fat', 'Fat'],
    ['fiber', 'Fiber'], ['sugars', 'Sugar'],
    ['saturated-fat', 'Saturated fat'], ['sodium', 'Sodium'],
    ['potassium', 'Potassium'], ['calcium', 'Calcium'],
    ['iron', 'Iron'], ['magnesium', 'Magnesium'],
    ['vitamin-c', 'Vitamin C'], ['vitamin-d', 'Vitamin D'],
    ['vitamin-b12', 'Vitamin B12'], ['cholesterol', 'Cholesterol']
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
      if (['energy', 'proteins', 'carbohydrates', 'fat'].includes(key)) {
        preview.appendChild(cell);
      }
    }

    const counted = nutrients.length - missing.length;
    status.textContent =
      'Review ' + serving + ' × ' + (validAmount ? rawQuantity : '?') +
      ': ' + counted + ' of ' + nutrients.length + ' required nutrients entered. ' +
      (missing.length
        ? 'Still required: ' + missing.join(', ') + '.'
        : 'All tracked nutrients are entered.') +
      ' Unknown/missing values default to 0 as an accounting assumption; verify any known label values.';
  }

  form.addEventListener('input', refresh);
  form.addEventListener('change', refresh);
  form.addEventListener('food:nutrition-loaded', refresh);
  refresh();
});
