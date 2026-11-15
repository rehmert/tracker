/* Release 639: structured supplement facts on existing Add/Edit forms. */
(() => {
  'use strict';
  const empty = () => ({
    brand: '', source: '', source_id: '', serving_quantity: '',
    serving_unit: '', ingredients: []
  });
  document.querySelectorAll('form[data-reg636-catalog]').forEach(form => {
    const root = form.querySelector('[data-reg639-facts]');
    if (!root) return;
    const hidden = root.querySelector('[name="label_facts_json"]');
    const brand = root.querySelector('[data-reg639-brand]');
    const servingQty = root.querySelector('[data-reg639-serving-quantity]');
    const servingUnit = root.querySelector('[data-reg639-serving-unit]');
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
      data.ingredients = Array.from(body.querySelectorAll('tr')).map(row => ({
        name: row.querySelector('[data-key="name"]').value.trim(),
        amount: row.querySelector('[data-key="amount"]').value.trim(),
        unit: row.querySelector('[data-key="unit"]').value.trim()
      })).filter(row => row.name);
      hidden.value = JSON.stringify(data);
      provenance.textContent = data.source && data.source_id
        ? data.source + ' label #' + data.source_id + ' (editable product label)'
        : 'Manual product information';
    }

    function makeRow(row) {
      const tr = document.createElement('tr');
      for (const [field, max] of [['name',160],['amount',40],['unit',40]]) {
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
      body.replaceChildren();
      (data.ingredients || []).forEach(makeRow);
      updateHidden();
    }

    [brand, servingQty, servingUnit].forEach(input =>
      input.addEventListener('input', () => {
        changedSinceSelection = true;
        updateHidden();
      })
    );
    add.addEventListener('click', () => {
      changedSinceSelection = true;
      makeRow({name: '', amount: '', unit: ''});
      updateHidden();
    });

    form.addEventListener('regimen:catalog-selected639', event => {
      const selected = event.detail || {};
      const source = String(selected.source || '');
      if (!source || source !== 'NIH DSLD') return;
      data = {
        ...empty(), brand: String(selected.brand || ''),
        source, source_id: String(selected.source_id || '')
      };
      selectionId = data.source_id;
      changedSinceSelection = false;
      loading = true;
      status.textContent = 'Loading complete manufacturer label before saving…';
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
      if (label.ingredient_rows_truncated) {
        status.textContent = 'The NIH label has more ingredient rows than Tracker can import. Save is blocked to prevent incomplete data.';
        loading = true;
        return;
      }
      data.serving_quantity = String(label.serving_quantity || '');
      data.serving_unit = String(label.serving_unit || '');
      data.ingredients = Array.isArray(label.ingredient_rows) ? label.ingredient_rows : [];
      draw();
      status.textContent = data.ingredients.length + ' labeled ingredient rows imported. Review each amount and serving basis.';
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