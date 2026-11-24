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

  function normalizeClock(raw) {
    const value = String(raw || '').trim();
    if (validClock.test(value)) return value;
    if (!/^\\d{3,4}$/.test(value)) return null;
    const compact = value.padStart(4, '0');
    const normalized = compact.slice(0, 2) + ':' + compact.slice(2);
    return validClock.test(normalized) ? normalized : null;
  }

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
      'Time (24-hour HHMM or HH:MM)'
    );
    time.setAttribute('placeholder', 'HHMM or HH:MM');
    time.setAttribute('inputmode', 'numeric');
    time.setAttribute('autocomplete', 'off');
    time.setAttribute(
      'pattern',
      '(?:(?:[01][0-9]|2[0-3]):[0-5][0-9]|' +
      '(?:[01][0-9]|2[0-3])[0-5][0-9]|[0-9][0-5][0-9])'
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
      '24-hour time: 0730 or 07:30 (no AM/PM)';

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

      const canonical = normalizeClock(time.value);
      const correctTime = !time.value || Boolean(canonical);

      date.setCustomValidity(
        partial && !date.value ? 'Choose a date.' : ''
      );

      time.setCustomValidity(
        !correctTime || (partial && !time.value)
          ? 'Enter 3–4 digits (e.g. 930 or 2130) or HH:MM.'
          : ''
      );

      const good = Boolean(
        date.value && canonical
      );

      const value = good
        ? `${date.value}T${canonical}`
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

    function formatVisibleTime() {
      const canonical = normalizeClock(time.value);
      if (canonical) time.value = canonical;
      writeOriginal();
    }

    for (const control of [date, time]) {
      control.addEventListener('input', writeOriginal);
      control.addEventListener('change',
        control === time ? formatVisibleTime : writeOriginal);
    }
    time.addEventListener('blur', formatVisibleTime);
    form.addEventListener('submit', formatVisibleTime);

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
