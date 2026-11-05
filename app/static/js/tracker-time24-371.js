/*
 * 24-hour local wall-clock entry without native AM/PM ambiguity.
 * Preserve the original named datetime-local field for server compatibility.
 * Never submit automatically or change historical records.
 */
(() => {
  'use strict';

  const validClock = /^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/;
  const validStamp =
    /^(\d{4}-\d{2}-\d{2})T([0-9]{2}:[0-9]{2})$/;

  const pad = number =>
    String(number).padStart(2, '0');

  function localNow() {
    const d = new Date();

    return (
      d.getFullYear() + '-' +
      pad(d.getMonth() + 1) + '-' +
      pad(d.getDate()) + 'T' +
      pad(d.getHours()) + ':' +
      pad(d.getMinutes())
    );
  }

  function enhance(form) {
    const isVitals =
      Boolean(form.dataset.trackerVitalsEntry);

    const name =
      isVitals ? 'measured_at' : 'taken_at';

    const original = form.querySelector(
      `input[type="datetime-local"][name="${name}"]`
    );

    const label = original?.closest('label');

    if (
      !original ||
      !label ||
      original.dataset.tracker24hEnhanced
    ) {
      return;
    }

    const layout = document.createElement('div');
    layout.className = 'tracker-time24-controls';

    const date = document.createElement('input');
    date.type = 'date';
    date.className = 'tracker-time24-date';
    date.setAttribute('aria-label', 'Date');
    date.required = original.required;

    const time = document.createElement('input');
    time.type = 'text';
    time.className = 'tracker-time24-clock';
    time.setAttribute(
      'aria-label',
      'Time (24-hour HH:MM)'
    );
    time.setAttribute('placeholder', 'HH:MM');
    time.setAttribute('inputmode', 'numeric');
    time.setAttribute('autocomplete', 'off');
    time.setAttribute(
      'pattern',
      '(?:[01][0-9]|2[0-3]):[0-5][0-9]'
    );
    time.maxLength = 5;
    time.required = original.required;

    layout.append(date, time);

    if (!isVitals) {
      const now = document.createElement('button');
      now.type = 'button';
      now.className = 'tracker-time24-now';
      now.textContent = 'Use current time';

      now.addEventListener('click', () => {
        original.value = localNow();

        original.dispatchEvent(
          new Event('change', {bubbles:true})
        );
      });

      layout.append(now);
    }

    const hint = document.createElement('small');
    hint.className = 'tracker-time24-hint';
    hint.textContent =
      '24-hour clock (00:00–23:59)';

    label.insertBefore(layout, original);
    label.insertBefore(hint, original);

    original.hidden = true;
    original.required = false;
    original.tabIndex = -1;
    original.setAttribute('aria-hidden', 'true');
    original.dataset.tracker24hEnhanced = 'true';

    let syncing = false;

    function readOriginal() {
      if (syncing) return;

      const match = validStamp.exec(original.value);

      date.value = match ? match[1] : '';
      time.value = match ? match[2] : '';

      date.setCustomValidity('');
      time.setCustomValidity('');
    }

    function writeOriginal() {
      const partial =
        Boolean(date.value) !== Boolean(time.value);

      const correctTime =
        !time.value || validClock.test(time.value);

      date.setCustomValidity(
        partial && !date.value ? 'Choose a date.' : ''
      );

      time.setCustomValidity(
        !correctTime || (partial && !time.value)
          ? 'Enter a time in 24-hour HH:MM format.'
          : ''
      );

      const good = Boolean(
        date.value && validClock.test(time.value)
      );

      const value = good
        ? `${date.value}T${time.value}`
        : '';

      if (original.value === value) return;

      syncing = true;
      original.value = value;

      original.dispatchEvent(
        new Event('input', {bubbles:true})
      );
      original.dispatchEvent(
        new Event('change', {bubbles:true})
      );

      syncing = false;
    }

    for (const control of [date, time]) {
      control.addEventListener('input', writeOriginal);
      control.addEventListener('change', writeOriginal);
    }

    original.addEventListener(
      'change', readOriginal
    );
    original.addEventListener(
      'input', readOriginal
    );

    form.addEventListener('reset', () =>
      queueMicrotask(readOriginal)
    );

    if (!isVitals) {
      document.body.addEventListener(
        'tracker:dose-saved',
        () => queueMicrotask(readOriginal)
      );
    }

    readOriginal();
  }

  function initialize() {
    document.querySelectorAll(
      'form[hx-post="/doses"], ' +
      'form#tracker-dose-correction-form, ' +
      'form[data-tracker-vitals-entry]'
    ).forEach(enhance);
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initialize,
      {once:true}
    );
  } else {
    initialize();
  }
})();
