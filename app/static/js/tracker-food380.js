document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  const form = document.getElementById('food380-search-form');
  const input = document.getElementById('food380-query');
  const status = document.getElementById('food380-status');
  const results = document.getElementById('food380-results');
  const button = document.getElementById('food380-search-button');

  if (!form || !input || !status || !results || !button) return;

  const nutrientKeys = [
    'energy', 'proteins', 'carbohydrates', 'fat',
    'fiber', 'sugars', 'saturated-fat', 'sodium',
    'potassium', 'calcium', 'iron', 'magnesium',
    'vitamin-c', 'vitamin-d', 'vitamin-b12',
    'cholesterol'
  ];

  function clearNutrition() {
    for (const key of nutrientKeys) {
      const field = document.getElementById('food-nutrient-' + key);
      if (field) field.value = '';
    }
  }

  function applyProduct(product) {
    clearNutrition();

    const barcode = document.getElementById('food-barcode');
    const name = document.getElementById('food-name');
    const serving = document.getElementById('food-serving');
    const source = document.getElementById('food-source');

    if (barcode) barcode.value = product.barcode || '';
    if (name) name.value = product.name || '';
    if (serving) {
      serving.value = product.serving_description || '100 g';
    }
    if (source) {
      source.value = product.source || 'Open Food Facts';
    }

    for (const [key, value] of Object.entries(
      product.nutrients || {}
    )) {
      const field = document.getElementById('food-nutrient-' + key);

      if (
        field &&
        value !== null &&
        Number.isFinite(Number(value))
      ) {
        field.value = value;
      }
    }

    const entryForm = document.getElementById('food-entry-form');

    if (entryForm) {
      entryForm.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      });
    }

    if (name) name.focus({preventScroll: true});
  }

  async function selectProduct(barcode, selectButton) {
    selectButton.disabled = true;
    status.textContent = 'Loading nutrition information…';

    try {
      const response = await fetch(
        '/food/barcode/' + encodeURIComponent(barcode),
        {credentials: 'same-origin'}
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail || 'Product lookup failed');
      }

      applyProduct(payload);

      status.textContent =
        'Product loaded into Add Food. Review the serving ' +
        'basis and nutrition values, then save when ready.';

      const scanStatus = document.getElementById('food-scan-status');

      if (scanStatus) {
        scanStatus.textContent =
          'Food selected by name. Verify all values before saving.';
      }
    } catch (error) {
      status.textContent =
        (error.message || 'Lookup failed') +
        '. Try another result or enter the food manually.';
    } finally {
      selectButton.disabled = false;
    }
  }

  function renderProducts(products) {
    results.replaceChildren();

    if (!products.length) {
      status.textContent =
        'No matching products with usable barcodes were found. ' +
        'Try a more specific name or use manual entry.';
      return;
    }

    status.textContent =
      'Found ' + products.length +
      ' matching products. Choose the correct product.';

    for (const product of products) {
      const card = document.createElement('article');
      card.className = 'food380-result';

      const info = document.createElement('div');
      info.className = 'food380-result-info';

      const title = document.createElement('strong');
      title.textContent = product.name;

      const details = document.createElement('small');
      details.textContent = [
        product.brand,
        product.serving,
        product.barcode
      ].filter(Boolean).join(' · ');

      const choose = document.createElement('button');
      choose.type = 'button';
      choose.textContent = 'Use Food';

      choose.addEventListener('click', () => {
        selectProduct(product.barcode, choose);
      });

      info.append(title, details);
      card.append(info, choose);
      results.append(card);
    }
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();

    const query = input.value.trim();

    if (query.length < 2 || query.length > 80) {
      status.textContent = 'Enter 2–80 characters.';
      return;
    }

    button.disabled = true;
    results.replaceChildren();
    status.textContent = 'Searching foods…';

    try {
      const response = await fetch(
        '/food/search-name?q=' + encodeURIComponent(query),
        {credentials: 'same-origin'}
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail || 'Search failed');
      }

      renderProducts(payload.products || []);
    } catch (error) {
      status.textContent =
        (error.message || 'Search unavailable') +
        '. You can still use barcode scanning or manual entry.';
    } finally {
      button.disabled = false;
    }
  });
});
