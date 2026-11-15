/* Release 639: structured supplement facts on existing Add/Edit forms. */
(() => {
  'use strict';
  const empty = () => ({
    brand: '', source: '', source_id: '', serving_quantity: '',
    serving_unit: '', servings_per_container: '', upc_sku: '',
    other_ingredients: '', ingredients: []
  });
  document.querySelectorAll('form[data-reg636-catalog]').forEach(form => {
    const root = form.querySelector('[data-reg639-facts]');
    if (!root) return;
    const hidden = root.querySelector('[name="label_facts_json"]');
    const brand = root.querySelector('[data-reg639-brand]');
    const servingQty = root.querySelector('[data-reg639-serving-quantity]');
    const servingUnit = root.querySelector('[data-reg639-serving-unit]');
    const servingsContainer = root.querySelector('[data-reg639-servings-container]');
    const upc = root.querySelector('[data-reg639-upc]');
    const others = root.querySelector('[data-reg639-other-ingredients]');
    const body = root.querySelector('[data-reg639-ingredients]');
    const provenance = root.querySelector('[data-reg639-provenance]');
    const status = root.querySelector('[data-reg639-status]');
    const add = root.querySelector('[data-reg639-add-ingredient]');
    let data = empty();
    let loading = false;
    let changedSinceSelection = false;
    let selectionId = '';

    try {
      if (hidden.value.trim()) {
        const saved = JSON.parse(hidden.value);
        if (saved && typeof saved === 'object' &&
            Array.isArray(saved.ingredients)) {
          data = {...empty(), ...saved};
        }
      }
    } catch (_) {
      status.textContent = 'Stored label data could not be parsed; save is blocked.';
      form.addEventListener('submit', event => event.preventDefault());
      return;
    }

    function updateHidden() {
      data.brand = brand.value;
      data.serving_quantity = servingQty.value;
      data.serving_unit = servingUnit.value;
      data.servings_per_container = servingsContainer.value;
      data.upc_sku = upc.value;
      data.other_ingredients = others.value;
      data.ingredients = Array.from(body.querySelectorAll('tr')).map(row => ({
        name: row.querySelector('[data-key="name"]').value.trim(),
        amount: row.querySelector('[data-key="amount"]').value.trim(),
        unit: row.querySelector('[data-key="unit"]').value.trim(),
        basis: row.querySelector('[data-key="basis"]').value.trim(),
        daily_value: row.querySelector('[data-key="daily_value"]').value.trim()
      })).filter(row => row.name);
      hidden.value = JSON.stringify(data);
      provenance.textContent = data.source && data.source_id
        ? data.source + ' label #' + data.source_id + ' (editable product label)'
        : 'Manual product information';
    }

    function makeRow(row) {
      const tr = document.createElement('tr');
      for (const [field, max] of [['name',160],['amount',40],['unit',40],
                                  ['basis',100],['daily_value',160]]) {
        const td = document.createElement('td');
        const input = document.createElement('input');
        input.setAttribute('data-key', field);
        input.setAttribute('aria-label', 'Ingredient ' + field);
        input.maxLength = max;
        input.value = typeof row[field] === 'string' ? row[field] : '';
        input.addEventListener('input', () => {
          changedSinceSelection = true;
          updateHidden();
        });
        td.append(input);
        tr.append(td);
      }
      const td = document.createElement('td');
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = 'Remove';
      remove.setAttribute('aria-label', 'Remove ingredient');
      remove.addEventListener('click', () => {
        tr.remove();
        changedSinceSelection = true;
        updateHidden();
      });
      td.append(remove);
      tr.append(td);
      body.append(tr);
    }

    function draw() {
      brand.value = data.brand || '';
      servingQty.value = data.serving_quantity || '';
      servingUnit.value = data.serving_unit || '';
      servingsContainer.value = data.servings_per_container || '';
      upc.value = data.upc_sku || '';
      others.value = data.other_ingredients || '';
      body.replaceChildren();
      (data.ingredients || []).forEach(makeRow);
      updateHidden();
    }

    [brand, servingQty, servingUnit, servingsContainer, upc, others].forEach(input =>
      input.addEventListener('input', () => {
        changedSinceSelection = true;
        updateHidden();
      })
    );
    add.addEventListener('click', () => {
      changedSinceSelection = true;
      makeRow({name: '', amount: '', unit: '', basis: '', daily_value: ''});
      updateHidden();
    });
    const manual = root.querySelector('[data-reg639-manual]');
    if (manual) manual.addEventListener('click', () => {
      loading = false;
      selectionId = '';
      data.source = '';
      data.source_id = '';
      changedSinceSelection = true;
      updateHidden();
      status.textContent = 'Manual product facts selected. Review or edit the ingredient rows before saving.';
    });

    form.addEventListener('regimen:catalog-cleared639', () => {
      // Keep user-entered ingredients/serving intact, but never associate
      // them silently with a product label after the name changes.
      if (data.source || data.source_id) {
        data.source = '';
        data.source_id = '';
        loading = false;
        selectionId = '';
        updateHidden();
        status.textContent = 'Product name changed. Existing facts retained as manual; select a catalog match to link a new label.';
      }
    });

    form.addEventListener('regimen:catalog-selected639', event => {
      const selected = event.detail || {};
      const source = String(selected.source || '');
      if (!source) return;
      data = {
        ...empty(), brand: String(selected.brand || ''),
        source, source_id: String(selected.source_id || '')
      };
      selectionId = data.source_id;
      changedSinceSelection = false;
      loading = source === 'NIH DSLD';
      status.textContent = loading
        ? 'Loading complete manufacturer label before saving…'
        : 'Catalog product selected. Confirm the product label and strength before saving.';
      draw();
    });
    form.addEventListener('regimen:label-loaded639', event => {
      const label = event.detail || {};
      if (!loading || label.source_id !== selectionId) return;
      loading = false;
      if (changedSinceSelection) {
        status.textContent = 'Label loaded after your edits. Existing edits preserved; select the product again to import its facts.';
        return;
      }
      if (label.ingredient_rows_truncated ||
          !Array.isArray(label.ingredient_rows) ||
          label.ingredient_rows.length === 0) {
        status.textContent = 'NIH label facts are incomplete or ambiguous. Use manual product facts or select a different label; automatic save is blocked.';
        loading = true;
        return;
      }
      data.serving_quantity = String(label.serving_quantity || '');
      data.serving_unit = String(label.serving_unit || '');
      data.ingredients = Array.isArray(label.ingredient_rows) ? label.ingredient_rows : [];
      data.other_ingredients = String(label.other_ingredients || '');
      data.servings_per_container = String(label.servings_per_container || '');
      data.upc_sku = String(label.upc_sku || '');
      draw();
      status.textContent = data.ingredients.length
        ? data.ingredients.length + ' labeled ingredient rows imported. Review each amount and serving basis.'
        : 'NIH label returned no ingredient quantities. Verify the product before saving.';
    });
    form.addEventListener('regimen:label-failed639', event => {
      if (event.detail?.source_id !== selectionId) return;
      loading = false;
      status.textContent = 'Could not load detailed label. You may enter facts manually.';
    });
    form.addEventListener('submit', event => {
      if (loading) {
        event.preventDefault();
        status.textContent = 'Wait for label details or choose manual entry before saving.';
        return;
      }
      updateHidden();
    });

    // Existing entries are populated on Edit, without a network refresh.
    if (hidden.value.trim()) draw();
    else {
      // An empty new item remains manual until the user edits facts or
      // deliberately selects a label; no empty facts row is persisted.
      provenance.textContent = 'Manual product details. Select a label to import facts.';
    }
  });
})();