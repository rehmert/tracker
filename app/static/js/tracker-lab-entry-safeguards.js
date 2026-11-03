/*
 * Lab report entry safeguards.
 *
 * Browser-only:
 * - Warn about unsaved changes
 * - Identify duplicate analyte names
 * - Preserve existing server validation and forms
 */
(() => {
  'use strict';

  function initialize() {
    const manual = document.querySelector(
      'form[data-lab-manual-entry]'
    );
    const csv = document.querySelector(
      'form[data-lab-csv-entry]'
    );

    if (!manual || !csv ||
        manual.dataset.safeguardsReady) return;

    const forms = [manual, csv];
    manual.dataset.safeguardsReady = 'true';

    function snapshot(form) {
      const fields = Array.from(
        form.querySelectorAll(
          'input[name],select[name],textarea[name]'
        )
      );

      return JSON.stringify(fields.map(field => {
        if (field.type === 'file') {
          return [
            field.name,
            'file',
            Array.from(field.files || [])
              .map(file => [
                file.name, file.size, file.lastModified
              ])
          ];
        }

        if (
          field.type === 'checkbox' ||
          field.type === 'radio'
        ) {
          return [
            field.name, field.type,
            field.value, field.checked
          ];
        }

        return [field.name, field.type, field.value];
      }));
    }

    const original = new Map(
      forms.map(form => [form, snapshot(form)])
    );

    let submitting = false;
    let leaving = false;

    function isDirty() {
      return forms.some(form =>
        snapshot(form) !== original.get(form)
      );
    }

    const indicator = document.createElement('p');
    indicator.className = 'tracker-lab-unsaved-indicator';
    indicator.setAttribute('role', 'status');
    indicator.textContent = 'No unsaved changes';

    const heading = document.querySelector(
      'h1'
    );
    heading?.insertAdjacentElement(
      'afterend', indicator
    );

    function updateDirty() {
      const dirty = isDirty();
      indicator.textContent = dirty
        ? 'Unsaved lab entry changes'
        : 'No unsaved changes';
      indicator.dataset.dirty =
        dirty ? 'true' : 'false';
    }

    forms.forEach(form => {
      form.addEventListener('input', updateDirty);
      form.addEventListener('change', updateDirty);

      form.addEventListener('submit', event => {
        if (
          event.defaultPrevented ||
          !form.checkValidity()
        ) return;

        // The existing POST endpoint determines
        // whether the report is accepted.
        submitting = true;
      });
    });

    const cancel = manual.querySelector(
      'a[href="/labs"]'
    );

    cancel?.addEventListener('click', event => {
      if (!isDirty()) return;

      const proceed = window.confirm(
        'Discard unsaved lab report changes?'
      );

      if (!proceed) {
        event.preventDefault();
      } else {
        leaving = true;
      }
    });

    window.addEventListener('beforeunload', event => {
      if (
        submitting ||
        leaving ||
        !isDirty()
      ) return;

      event.preventDefault();
      event.returnValue = '';
    });

    window.addEventListener('pageshow', () => {
      submitting = false;
      leaving = false;
      updateDirty();
    });

    const tbody = manual.querySelector('#lab-rows');
    const warning = manual.querySelector(
      '[data-lab-duplicate-warning]'
    );

    function reviewDuplicates() {
      if (!tbody || !warning) return;

      const seen = new Map();
      const duplicates = new Set();

      Array.from(tbody.querySelectorAll('tr'))
        .forEach(row => {
          const field = row.querySelector(
            'input[name="analyte"]'
          );

          const name = field?.value
            ?.trim()
            .replace(/\s+/g, ' ') || '';

          const key = name.toLocaleLowerCase();

          if (!key) {
            row.removeAttribute(
              'data-lab-duplicate'
            );
            return;
          }

          if (seen.has(key)) {
            duplicates.add(key);
          } else {
            seen.set(key, name);
          }
        });

      Array.from(tbody.querySelectorAll('tr'))
        .forEach(row => {
          const field = row.querySelector(
            'input[name="analyte"]'
          );
          const name = field?.value
            ?.trim()
            .replace(/\s+/g, ' ')
            .toLocaleLowerCase() || '';

          if (name && duplicates.has(name)) {
            row.dataset.labDuplicate = 'true';
          } else {
            row.removeAttribute(
              'data-lab-duplicate'
            );
          }
        });

      const names = Array.from(duplicates)
        .map(key => seen.get(key));

      warning.hidden = names.length === 0;
      warning.textContent = names.length
        ? 'Possible duplicate analytes: ' +
          names.join(', ') +
          '. Check the rows before saving.'
        : '';
    }

    if (tbody && warning) {
      tbody.addEventListener(
        'input', reviewDuplicates
      );
      tbody.addEventListener(
        'change', reviewDuplicates
      );

      const observer = new MutationObserver(() => {
        reviewDuplicates();
        updateDirty();
      });

      observer.observe(tbody, {
        childList: true
      });

      reviewDuplicates();
    }

    updateDirty();
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
