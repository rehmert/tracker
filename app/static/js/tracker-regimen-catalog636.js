/* Release 636: inline suggestions in the existing Add/Edit regimen item forms.
 * Remote results are untrusted label text. No auto-submit, dose, or schedule edits.
 */
(() => {
  'use strict';

  function activate(form) {
    const name = form.elements.namedItem('name');
    const kind = form.elements.namedItem('kind');
    const panel = form.querySelector('[data-reg636-results]');
    const status = form.querySelector('[data-reg636-status]');
    const source = form.querySelector('[data-reg636-source]');
    if (!name || !kind || !panel || !status || !source) return;

    let timer = null;
    let current = null;
    let requestNumber = 0;
    let selected = null;

    function clear() {
      panel.replaceChildren();
      panel.hidden = true;
      source.textContent = '';
      selected = null;
    }

    async function search() {
      const q = name.value.trim();
      clear();
      if (q.length < 2 || q.length > 80) {
        status.textContent = 'Enter at least 2 characters to search, or continue manually.';
        return;
      }
      current?.abort();
      const controller = new AbortController();
      current = controller;
      const number = ++requestNumber;
      status.textContent = 'Searching catalog…';
      try {
        const url = '/regimen/catalog/suggest?' + new URLSearchParams({kind: kind.value, q});
        const response = await fetch(url, {
          method: 'GET', credentials: 'same-origin',
          headers: {'Accept': 'application/json'}, signal: controller.signal
        });
        if (!response.ok) throw new Error('Catalog temporarily unavailable');
        const data = await response.json();
        if (number !== requestNumber || name.value.trim() !== q) return;
        const matches = Array.isArray(data.results) ? data.results : [];
        if (!matches.length) {
          status.textContent = 'No catalog match. You can enter the details manually.';
          return;
        }
        for (const match of matches) {
          const option = document.createElement('button');
          option.type = 'button';
          option.className = 'reg636-option';
          option.setAttribute('role', 'option');
          const detail = [match.brand, match.strength, match.form]
            .filter(Boolean).join(' · ');
          const title = document.createElement('strong');
          title.textContent = match.name || '';
          const secondary = document.createElement('small');
          secondary.textContent = [detail, match.source].filter(Boolean).join(' — ');
          option.append(title, secondary);
          option.addEventListener('click', () => {
            for (const key of ['name', 'ingredient', 'strength', 'form']) {
              const field = form.elements.namedItem(key);
              if (field && typeof match[key] === 'string' && match[key]) {
                field.value = match[key].slice(0, field.maxLength > 0 ? field.maxLength : 160);
                field.dispatchEvent(new Event('change', {bubbles: true}));
              }
            }
            selected = {
              source: String(match.source || ''),
              id: String(match.source_id || ''),
              name: String(match.name || '')
            };
            const notes = form.elements.namedItem('notes');
            const marker = 'Catalog reference: ' + selected.source +
              (selected.id ? ' #' + selected.id : '');
            if (notes && !notes.value.includes(marker)) {
              const combined = notes.value.trim()
                ? notes.value.trim() + '\n' + marker : marker;
              if (combined.length <= notes.maxLength) notes.value = combined;
            }
            source.textContent = 'Selected: ' + selected.source +
              (selected.id ? ' #' + selected.id : '') + '. Verify the label before saving.';
            // Supplement labels may contain multiple ingredients. Keep the
            // concise product identifier fields separate from full label data.
            if (selected.source === 'NIH DSLD' && /^[0-9]{1,12}$/.test(selected.id)) {
              const picked = selected.id;
              fetch('/regimen/catalog/supplement-label?' +
                new URLSearchParams({label_id: picked}), {
                  method: 'GET', credentials: 'same-origin',
                  headers: {'Accept': 'application/json'}
                }).then(response => {
                  if (!response.ok) throw new Error('Label unavailable');
                  return response.json();
                }).then(detail => {
                  if (!selected || selected.id !== picked || !detail.available) return;
                  const formField = form.elements.namedItem('form');
                  if (formField && !formField.value && detail.form) {
                    formField.value = String(detail.form).slice(0, formField.maxLength);
                  }
                  if (notes) {
                    const parts = [];
                    if (detail.serving) parts.push('Labeled serving: ' + detail.serving);
                    if (detail.ingredients) parts.push('Labeled ingredients: ' + detail.ingredients);
                    for (const part of parts) {
                      if (notes.value.includes(part)) continue;
                      const combined = notes.value.trim()
                        ? notes.value.trim() + '\n' + part : part;
                      if (combined.length <= notes.maxLength) notes.value = combined;
                    }
                  }
                  source.textContent += ' Supplement label details loaded into Notes for review.';
                }).catch(() => {
                  source.textContent += ' Detailed supplement label unavailable; manual entry works.';
                });
              }
            }
            panel.replaceChildren();
            panel.hidden = true;
            status.textContent = 'Product details filled. Review or edit before saving.';
          });
          panel.append(option);
        }
        panel.hidden = false;
        status.textContent = matches.length + ' possible matches. Select one or keep typing manually.';
        if (Array.isArray(data.unavailable) && data.unavailable.length) {
          status.textContent += ' Some providers were unavailable.';
        }
      } catch (error) {
        if (error.name !== 'AbortError' && number === requestNumber) {
          status.textContent = 'Catalog unavailable. Manual entry still works.';
        }
      }
    }

    function schedule() {
      clearTimeout(timer);
      current?.abort();
      ++requestNumber;
      clear();
      status.textContent = 'Enter at least 2 characters to search, or continue manually.';
      if (name.value.trim().length >= 2) timer = setTimeout(search, 450);
    }
    name.addEventListener('input', schedule);
    kind.addEventListener('change', schedule);

  }

  document.querySelectorAll('form[data-reg636-catalog]').forEach(activate);
})();
