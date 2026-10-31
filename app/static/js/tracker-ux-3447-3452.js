/*
 * Tracker UX Stages 34.47–34.52
 *
 * Progressive enhancement only.
 * No API requests or database modifications.
 */

(() => {
  'use strict';

  const CONFIG = {
    successDismissMs: 7000,
    submitUnlockMs: 15000,
    dirtyClass: 'tracker-form-dirty',
    errorClass: 'tracker-field-invalid'
  };

  const state = {
    dirtyForms: new Set(),
    submittingForms: new WeakSet(),
    initializedForms: new WeakSet(),
    initializedTables: new WeakSet(),
    initializedMessages: new WeakSet()
  };

  function isEditableField(field) {
    if (!(field instanceof HTMLElement)) {
      return false;
    }

    if (field.matches(
      '[disabled], [readonly], [type="hidden"], ' +
      '[type="submit"], [type="button"], ' +
      '[type="reset"], [type="image"]'
    )) {
      return false;
    }

    return field.matches(
      'input, select, textarea'
    );
  }

  function isTrackedForm(form) {
    if (!(form instanceof HTMLFormElement)) {
      return false;
    }

    if (form.matches(
      '[data-no-dirty-warning], ' +
      '[data-tracker-ignore-ux]'
    )) {
      return false;
    }

    if (
      (form.getAttribute('method') || 'get')
        .toLowerCase() === 'get'
    ) {
      return false;
    }

    if (
      form.closest(
        'nav, .workspace-toolbar, ' +
        '.command-overlay'
      )
    ) {
      return false;
    }

    return true;
  }

  function isHTMXForm(form) {
    return Boolean(
      form.matches(
        '[hx-post], [hx-put], [hx-patch], ' +
        '[hx-delete], [hx-get], ' +
        '[data-hx-post], [data-hx-put], ' +
        '[data-hx-patch], [data-hx-delete]'
      ) ||
      form.closest(
        '[hx-post], [hx-put], [hx-patch], ' +
        '[hx-delete], [hx-get]'
      )
    );
  }

  function fieldLabel(field) {
    const id = field.id;

    if (id) {
      const labels = Array.from(
        document.querySelectorAll('label[for]')
      );

      const associated = labels.find(
        label => label.htmlFor === id
      );

      if (associated) {
        const value = associated.textContent.trim();

        if (value) return value;
      }
    }

    const parent = field.closest('label');

    if (parent) {
      const span = parent.querySelector('span');

      if (span && span.textContent.trim()) {
        return span.textContent.trim();
      }

      const value = parent.textContent.trim();

      if (value) return value;
    }

    return (
      field.getAttribute('aria-label') ||
      field.getAttribute('placeholder') ||
      field.name ||
      'Field'
    ).trim();
  }

  function removeValidationSummary(form) {
    const summary = Array.from(
      form.children
    ).find(child =>
      child.classList?.contains(
        'tracker-validation-summary'
      )
    );

    if (summary) summary.remove();
  }

  function clearFieldError(field) {
    field.classList.remove(
      CONFIG.errorClass
    );

    field.removeAttribute(
      'data-tracker-validation-error'
    );
  }

  function showValidation(form) {
    removeValidationSummary(form);

    const invalid = Array.from(
      form.elements
    ).filter(field =>
      field instanceof HTMLElement &&
      typeof field.checkValidity === 'function' &&
      !field.checkValidity() &&
      field.willValidate !== false
    );

    if (!invalid.length) return false;

    const summary = document.createElement('div');

    summary.className =
      'tracker-validation-summary';

    summary.setAttribute('role', 'alert');
    summary.setAttribute('tabindex', '-1');

    const heading = document.createElement('strong');
    heading.textContent =
      'Please review these fields:';

    const list = document.createElement('ul');

    invalid.forEach(field => {
      field.classList.add(
        CONFIG.errorClass
      );

      field.dataset.trackerValidationError = 'true';

      const item = document.createElement('li');

      const button = document.createElement('button');
      button.type = 'button';

      const label = fieldLabel(field);

      button.textContent =
        `${label}: ${field.validationMessage}`;

      button.addEventListener('click', () => {
        field.focus();

        field.scrollIntoView({
          block: 'center',
          behavior: 'auto'
        });
      });

      item.append(button);
      list.append(item);
    });

    summary.append(heading, list);
    form.prepend(summary);

    invalid[0].focus();

    invalid[0].scrollIntoView({
      block: 'center',
      behavior: 'auto'
    });

    return true;
  }

  function snapshot(form) {
    const values = [];

    Array.from(form.elements).forEach(field => {
      if (!isEditableField(field)) return;

      if (
        field instanceof HTMLInputElement &&
        field.type === 'file'
      ) {
        values.push([
          field.name,
          'file',
          Array.from(field.files || []).map(
            file => [
              file.name,
              file.size,
              file.lastModified
            ]
          )
        ]);

        return;
      }

      if (
        field instanceof HTMLInputElement &&
        ['checkbox', 'radio'].includes(field.type)
      ) {
        values.push([
          field.name,
          field.type,
          field.checked,
          field.value
        ]);

        return;
      }

      if (
        field instanceof HTMLSelectElement &&
        field.multiple
      ) {
        values.push([
          field.name,
          'multiple',
          Array.from(field.selectedOptions)
            .map(option => option.value)
        ]);

        return;
      }

      values.push([
        field.name,
        field.type || field.tagName,
        field.value
      ]);
    });

    return JSON.stringify(values);
  }

  function initializeForm(form) {
    if (
      !isTrackedForm(form) ||
      state.initializedForms.has(form)
    ) {
      return;
    }

    state.initializedForms.add(form);

    let baseline = snapshot(form);

    function updateDirty() {
      const dirty = snapshot(form) !== baseline;

      form.classList.toggle(
        CONFIG.dirtyClass,
        dirty
      );

      if (dirty) {
        state.dirtyForms.add(form);
      } else {
        state.dirtyForms.delete(form);
      }
    }

    form.addEventListener('input', event => {
      if (isEditableField(event.target)) {
        clearFieldError(event.target);
        removeValidationSummary(form);
      }

      updateDirty();
    });

    form.addEventListener('change', event => {
      if (isEditableField(event.target)) {
        clearFieldError(event.target);
        removeValidationSummary(form);
      }

      updateDirty();
    });

    form.addEventListener('reset', () => {
      setTimeout(updateDirty, 0);
    });

    form.addEventListener('submit', event => {
      if (event.defaultPrevented) return;

      if (!form.checkValidity()) {
        event.preventDefault();
        showValidation(form);
        return;
      }

      removeValidationSummary(form);

      /*
       * HTMX controls its own request lifecycle.
       * Do not disable or lock HTMX submissions.
       */
      if (isHTMXForm(form)) {
        state.dirtyForms.delete(form);
        form.classList.remove(
          CONFIG.dirtyClass
        );
        return;
      }

      if (state.submittingForms.has(form)) {
        event.preventDefault();
        return;
      }

      state.submittingForms.add(form);

      /*
       * Allow a legitimate submission to proceed.
       * Lock only repeated submissions while pending.
       */
      const buttons = Array.from(
        form.querySelectorAll(
          'button[type="submit"], ' +
          'input[type="submit"]'
        )
      );

      buttons.forEach(button => {
        button.dataset.trackerPending = 'true';
        button.setAttribute(
          'aria-disabled',
          'true'
        );
      });

      state.dirtyForms.delete(form);
      form.classList.remove(
        CONFIG.dirtyClass
      );

      setTimeout(() => {
        state.submittingForms.delete(form);

        buttons.forEach(button => {
          delete button.dataset.trackerPending;
          button.removeAttribute(
            'aria-disabled'
          );
        });
      }, CONFIG.submitUnlockMs);
    });

    /*
     * Native validation normally prevents the
     * submit event. Capture invalid events so
     * the summary still appears.
     */
    let invalidTimer = null;

    form.addEventListener('invalid', () => {
      clearTimeout(invalidTimer);

      invalidTimer = setTimeout(() => {
        showValidation(form);
      }, 0);
    }, true);

    /*
     * Avoid false positives after a successful
     * programmatic form reset.
     */
    form.trackerResetDirtyState = () => {
      baseline = snapshot(form);
      updateDirty();
    };
  }

  /*
   * Stage 34.48: Unsaved changes.
   *
   * Only warn for tracked forms still connected
   * to the document.
   */
  window.addEventListener('beforeunload', event => {
    const dirty = Array.from(
      state.dirtyForms
    ).some(form =>
      form.isConnected &&
      !state.submittingForms.has(form)
    );

    if (!dirty) return;

    event.preventDefault();
    event.returnValue = '';
  });

  /*
   * Stage 34.50: Feedback messages.
   */
  function initializeMessage(message) {
    if (
      state.initializedMessages.has(message) ||
      message.querySelector(
        '.tracker-flash-dismiss'
      )
    ) {
      return;
    }

    state.initializedMessages.add(message);

    const dismiss = document.createElement('button');

    dismiss.type = 'button';
    dismiss.className =
      'tracker-flash-dismiss';

    dismiss.setAttribute(
      'aria-label',
      'Dismiss notification'
    );

    dismiss.textContent = '×';

    dismiss.addEventListener('click', () => {
      message.remove();
    });

    message.append(dismiss);

    if (
      message.classList.contains('ok') &&
      !message.matches(
        '[data-persistent], [data-no-auto-dismiss]'
      )
    ) {
      setTimeout(() => {
        if (
          message.isConnected &&
          !message.matches(':hover') &&
          !message.contains(
            document.activeElement
          )
        ) {
          message.remove();
        }
      }, CONFIG.successDismissMs);
    }
  }

  /*
   * Stage 34.51: Tables.
   *
   * Avoid wrapping a table that already lives
   * inside a scrolling container.
   */
  function initializeTable(table) {
    if (state.initializedTables.has(table)) {
      return;
    }

    state.initializedTables.add(table);

    if (
      table.closest(
        '.scroll, .table-scroll, ' +
        '.table-responsive, ' +
        '.tracker-ci-results, ' +
        '.tracker-lifecycle-scroll'
      )
    ) {
      return;
    }

    if (
      table.closest(
        '[data-no-table-scroll], ' +
        '.calendar, .chart, .plot'
      )
    ) {
      return;
    }

    if (!table.parentNode) return;

    const wrapper = document.createElement('div');

    wrapper.className =
      'tracker-responsive-table';

    wrapper.tabIndex = 0;

    wrapper.setAttribute(
      'role',
      'region'
    );

    const caption = table.querySelector('caption');

    wrapper.setAttribute(
      'aria-label',
      caption?.textContent.trim() ||
      'Scrollable data table'
    );

    table.before(wrapper);
    wrapper.append(table);

    function updateOverflow() {
      const overflowing =
        wrapper.scrollWidth >
        wrapper.clientWidth + 2;

      wrapper.classList.toggle(
        'tracker-table-overflowing',
        overflowing
      );

      wrapper.tabIndex = overflowing ? 0 : -1;
    }

    updateOverflow();

    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(
        updateOverflow
      );

      observer.observe(wrapper);
      observer.observe(table);
    }
  }

  /*
   * Progressive enhancement for content
   * inserted by HTMX.
   */
  function enhance(root = document) {
    if (!root.querySelectorAll) return;

    root.querySelectorAll('form').forEach(
      initializeForm
    );

    root.querySelectorAll(
      '.flash.ok, .flash.error'
    ).forEach(initializeMessage);

    root.querySelectorAll('table').forEach(
      initializeTable
    );

    if (
      root instanceof HTMLFormElement
    ) {
      initializeForm(root);
    }

    if (
      root instanceof HTMLTableElement
    ) {
      initializeTable(root);
    }

    if (
      root instanceof HTMLElement &&
      root.matches('.flash.ok, .flash.error')
    ) {
      initializeMessage(root);
    }
  }

  function initialize() {
    enhance();

    document.body.addEventListener(
      'htmx:afterSwap',
      event => {
        enhance(event.detail?.target || document);
      }
    );

    document.body.addEventListener(
      'htmx:afterSettle',
      event => {
        enhance(event.detail?.target || document);
      }
    );

    window.trackerUXDiagnostics = () => ({
      version: '34.47-34.52',
      trackedForms: document.querySelectorAll(
        'form.tracker-form-dirty'
      ).length,
      scrollableTables: document.querySelectorAll(
        '.tracker-responsive-table'
      ).length,
      feedbackMessages: document.querySelectorAll(
        '.flash.ok, .flash.error'
      ).length,
      stages: [
        'Form validation',
        'Unsaved changes',
        'Duplicate-submit protection',
        'Feedback dismissal',
        'Responsive tables',
        'Accessibility refinements'
      ]
    });
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
