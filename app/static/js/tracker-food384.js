document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  function formatNumber(value) {
    const rounded = Math.round(value * 10) / 10;
    return Number.isFinite(rounded)
      ? String(rounded)
      : '?';
  }

  function updatePreview(container) {
    const form = container.parentElement?.querySelector(
      'form.food375-quick-form'
    );

    if (!form) return;

    const servingInput = form.querySelector(
      'input[name="servings"]'
    );

    if (!servingInput) return;

    const servings = Number(servingInput.value);

    container.querySelectorAll(
      '[data-food384-value]'
    ).forEach(item => {
      const raw = item.dataset.perServing;
      const label = item.dataset.label || '';

      if (
        raw === '' ||
        !Number.isFinite(servings) ||
        servings <= 0 ||
        servings > 100
      ) {
        item.textContent = label + ' ?';
        return;
      }

      const perServing = Number(raw);

      item.textContent = label + ' ' +
        (Number.isFinite(perServing)
          ? formatNumber(perServing * servings)
          : '?');
    });
  }

  document.querySelectorAll(
    '[data-food384-preview]'
  ).forEach(container => {
    const form = container.parentElement?.querySelector(
      'form.food375-quick-form'
    );

    const quantity = form?.querySelector(
      'input[name="servings"]'
    );

    if (!quantity) return;

    quantity.addEventListener(
      'input',
      () => updatePreview(container)
    );

    updatePreview(container);
  });

  // Open the relevant accordion after a redirect with a
  // section fragment. Release 382 handles opening the section;
  // this script also scrolls it into view after page layout.
  const sectionId = location.hash.slice(1);

  const allowed = new Set([
    'food-recorded',
    'food-quick-log',
    'food-templates',
    'food-add',
    'food-search',
  ]);

  if (!allowed.has(sectionId)) return;

  const section = document.getElementById(sectionId);

  if (!section || !section.matches(
    'details.food382-accordion'
  )) return;

  section.open = true;

  requestAnimationFrame(() => {
    section.scrollIntoView({
      behavior: 'auto',
      block: 'start',
    });
  });
});
