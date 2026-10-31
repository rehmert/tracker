/*
 * Tracker Stages 34.53–34.57
 *
 * Progressive enhancements.
 * No changes to stored values or calculations.
 */

(() => {
  'use strict';

  const initialized = new WeakSet();
  const feedback = new WeakMap();

  const timers = new WeakMap();

  function make(tag, text, className) {
    const node = document.createElement(tag);

    if (text !== undefined) {
      node.textContent = text;
    }

    if (className) {
      node.className = className;
    }

    return node;
  }

  function isEligible(field) {
    return (
      field instanceof HTMLElement &&
      field.matches('input, select, textarea') &&
      !field.matches(
        '[disabled], [readonly], [type="hidden"], ' +
        '[type="submit"], [type="button"]'
      ) &&
      !field.closest('[data-tracker-ignore-ux]')
    );
  }

  /*
   * Stage 34.53
   * Inline validation after a field has been visited.
   *
   * Native browser validation remains authoritative.
   */
  function initializeField(field) {
    if (!isEligible(field) || initialized.has(field)) {
      return;
    }

    initialized.add(field);

    let touched = false;
    let message = null;

    function update() {
      if (
        !touched ||
        !field.willValidate ||
        typeof field.checkValidity !== 'function'
      ) {
        return;
      }

      const invalid = !field.checkValidity();

      field.classList.toggle(
        'tracker-inline-invalid',
        invalid
      );

      if (!invalid) {
        if (message) {
          message.remove();
          message = null;
        }

        field.removeAttribute(
          'data-tracker-inline-error'
        );

        return;
      }

      if (!message) {
        message = make(
          'small',
          '',
          'tracker-inline-error'
        );

        field.insertAdjacentElement(
          'afterend',
          message
        );
      }

      message.textContent = field.validationMessage;

      field.dataset.trackerInlineError = 'true';
    }

    field.addEventListener('blur', () => {
      touched = true;
      update();
    });

    field.addEventListener('input', update);
    field.addEventListener('change', update);

    const form = field.form;

    if (form) {
      form.addEventListener('reset', () => {
        touched = false;

        field.classList.remove(
          'tracker-inline-invalid'
        );

        field.removeAttribute(
          'data-tracker-inline-error'
        );

        if (message) {
          message.remove();
          message = null;
        }
      });
    }
  }

  /*
   * Stage 34.54
   * Numeric-field guidance.
   *
   * Never alter values, step, min, or max.
   */
  function initializeNumericField(field) {
    if (
      !(
        field instanceof HTMLInputElement &&
        field.type === 'number'
      )
    ) {
      return;
    }

    if (
      field.matches(
        '[data-tracker-ignore-ux], [data-no-number-help]'
      )
    ) {
      return;
    }

    if (field.dataset.trackerNumberHelp) return;

    field.dataset.trackerNumberHelp = 'true';

    const parts = [];

    if (field.min !== '') {
      parts.push(`Minimum ${field.min}`);
    }

    if (field.max !== '') {
      parts.push(`Maximum ${field.max}`);
    }

    if (
      field.step !== '' &&
      field.step !== 'any'
    ) {
      parts.push(`Step ${field.step}`);
    }

    if (!parts.length) return;

    /*
     * Preserve any existing title.
     */
    if (!field.title) {
      field.title = parts.join(' · ');
    }
  }

  /*
   * Stage 34.55
   * Nonintrusive HTMX request feedback.
   *
   * Does not disable submit buttons.
   */
  function initializeHTMXFeedback(form) {
    if (!(form instanceof HTMLFormElement)) return;

    if (feedback.has(form)) return;

    const status = make(
      'span',
      '',
      'tracker-request-status'
    );

    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    status.hidden = true;

    feedback.set(form, status);

    form.append(status);

    function clear() {
      const timer = timers.get(form);

      if (timer) clearTimeout(timer);

      status.hidden = true;
      status.textContent = '';
    }

    form.addEventListener('htmx:beforeRequest', event => {
      if (event.target !== form) return;

      clear();

      status.textContent = 'Saving…';
      status.hidden = false;
    });

    form.addEventListener('htmx:afterRequest', event => {
      if (event.target !== form) return;

      const success =
        event.detail?.successful === true;

      status.textContent = success
        ? 'Request completed'
        : 'Request could not be completed';

      status.hidden = false;

      if (success) {
        timers.set(
          form,
          setTimeout(clear, 3500)
        );
      }
    });
  }

  /*
   * Stage 34.56
   * Restore focus after native dialogs close.
   */
  const dialogTriggers = new WeakMap();

  document.addEventListener('click', event => {
    const target = event.target;

    if (!(target instanceof Element)) return;

    const trigger = target.closest(
      '[data-dialog-target], [data-modal-target]'
    );

    if (!trigger) return;

    const selector =
      trigger.getAttribute('data-dialog-target') ||
      trigger.getAttribute('data-modal-target');

    if (!selector || !selector.startsWith('#')) {
      return;
    }

    let dialog;

    try {
      dialog = document.querySelector(selector);
    } catch (_) {
      return;
    }

    if (dialog instanceof HTMLDialogElement) {
      dialogTriggers.set(dialog, trigger);
    }
  });

  function initializeDialog(dialog) {
    if (
      !(dialog instanceof HTMLDialogElement) ||
      initialized.has(dialog)
    ) {
      return;
    }

    initialized.add(dialog);

    dialog.addEventListener('close', () => {
      const trigger = dialogTriggers.get(dialog);

      if (
        trigger instanceof HTMLElement &&
        trigger.isConnected
      ) {
        trigger.focus({
          preventScroll: true
        });
      }
    });
  }

  /*
   * Stage 34.57
   * Mark forms for consistent responsive styling.
   */
  function initializeForm(form) {
    if (!(form instanceof HTMLFormElement)) return;

    if (
      form.matches(
        '[data-tracker-ignore-ux], [data-no-responsive-form]'
      )
    ) {
      return;
    }

    form.classList.add(
      'tracker-responsive-form'
    );

    initializeHTMXFeedback(form);
  }

  function enhance(root = document) {
    if (!root.querySelectorAll) return;

    const fields = root.querySelectorAll(
      'input, select, textarea'
    );

    fields.forEach(field => {
      initializeField(field);
      initializeNumericField(field);
    });

    root.querySelectorAll('form').forEach(
      initializeForm
    );

    root.querySelectorAll('dialog').forEach(
      initializeDialog
    );

    if (root instanceof HTMLElement) {
      if (root.matches('input, select, textarea')) {
        initializeField(root);
        initializeNumericField(root);
      }

      if (root.matches('form')) {
        initializeForm(root);
      }

      if (root.matches('dialog')) {
        initializeDialog(root);
      }
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

    window.trackerUXBatchDiagnostics = () => ({
      version: '34.53-34.58',

      numericFields: document.querySelectorAll(
        'input[type="number"]'
      ).length,

      responsiveForms: document.querySelectorAll(
        'form.tracker-responsive-form'
      ).length,

      inlineErrors: document.querySelectorAll(
        '.tracker-inline-error'
      ).length,

      dialogs: document.querySelectorAll(
        'dialog'
      ).length
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
