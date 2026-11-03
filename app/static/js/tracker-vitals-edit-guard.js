/*
 * Vitals edit unsaved-changes protection.
 * Browser-only; no storage or network calls.
 */
(() => {
  'use strict';

  function initialize() {
    const form = document.querySelector(
      'form[data-tracker-vitals-entry="edit"]'
    );
    if (!form || form.dataset.editGuard) return;

    const cancel = form.querySelector(
      'a[data-vitals-edit-cancel]'
    );
    const save = form.querySelector(
      'button[type="submit"]'
    );
    if (!cancel || !save) return;

    form.dataset.editGuard = 'true';

    const fields = Array.from(
      form.querySelectorAll(
        'input:not([type="hidden"]),select,textarea'
      )
    );

    const original = fields.map(field => ({
      field,
      value: field.value,
      checked: field.checked
    }));

    const indicator = document.createElement('span');
    indicator.className = 'tracker-vitals-dirty-status';
    indicator.setAttribute('role', 'status');
    indicator.setAttribute('aria-live', 'polite');
    indicator.textContent = 'No Unsaved Changes';

    const restore = document.createElement('button');
    restore.type = 'button';
    restore.className = 'tracker-vitals-restore';
    restore.textContent = 'Restore Original Values';
    restore.disabled = true;

    const actions = save.parentElement;
    actions.append(restore, indicator);

    let saving = false;

    function isDirty() {
      return original.some(item =>
        item.field.value !== item.value ||
        (
          (item.field.type === 'checkbox' ||
           item.field.type === 'radio') &&
          item.field.checked !== item.checked
        )
      );
    }

    function update() {
      const dirty = isDirty();

      form.dataset.unsaved = dirty ? 'true' : 'false';
      indicator.textContent = dirty
        ? 'Unsaved Changes'
        : 'No Unsaved Changes';
      restore.disabled = !dirty;
    }

    restore.addEventListener('click', () => {
      for (const item of original) {
        item.field.value = item.value;

        if (
          item.field.type === 'checkbox' ||
          item.field.type === 'radio'
        ) {
          item.field.checked = item.checked;
        }

        item.field.dispatchEvent(
          new Event('input', { bubbles: true })
        );
        item.field.dispatchEvent(
          new Event('change', { bubbles: true })
        );
      }
      update();
    });

    form.addEventListener('input', update);
    form.addEventListener('change', update);

    cancel.addEventListener('click', event => {
      if (!isDirty() || saving) return;

      const proceed = window.confirm(
        'Discard unsaved changes to this reading?'
      );

      if (!proceed) {
        event.preventDefault();
      }
      // Prevent an additional browser warning after
      // an explicitly confirmed Cancel action.
      else {
        saving = true;
      }
    });

    form.addEventListener('submit', event => {
      if (
        event.defaultPrevented ||
        !form.checkValidity()
      ) {
        return;
      }
      saving = true;
    });

    window.addEventListener('beforeunload', event => {
      if (saving || !isDirty()) return;

      event.preventDefault();
      event.returnValue = '';
    });

    window.addEventListener('pageshow', () => {
      saving = false;
      update();
    });

    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded', initialize, { once: true }
    );
  } else {
    initialize();
  }
})();
