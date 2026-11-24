/* Release 713 — 24-hour entry for every native time/datetime-local control.
 *
 * Browsers may render native time pickers with AM/PM regardless of the value's
 * ISO 24-hour representation. Keep the original named input for API and
 * existing JS compatibility; show a plain HH:MM field instead.
 * Do not alter stored times, timezone interpretation, or submitted field names.
 * Works on both static and dynamically inserted controls (including workouts).
 */
(() => {
  'use strict';
  if (window.trackerTime24Global713) return;
  window.trackerTime24Global713 = true;

  const clockPattern = /^(?:[01]\d|2[0-3]):[0-5]\d$/;
  const stampPattern = /^(\d{4}-\d{2}-\d{2})T([0-2]\d:[0-5]\d)(?::00)?$/;

  // Accept HH:MM and colon-free 24-hour clock values such as 0730 or 930.
  // Three digits mean HMM; four mean HHMM. Invalid 24:00/23:60 are rejected.
  const normalizeClock = raw => {
    const value = String(raw || '').trim();
    if (clockPattern.test(value)) return value;
    if (!/^\d{3,4}$/.test(value)) return null;
    const hhmm = value.padStart(4, '0');
    const formatted = hhmm.slice(0, 2) + ':' + hhmm.slice(2);
    return clockPattern.test(formatted) ? formatted : null;
  };

  const pad = n => String(n).padStart(2, '0');
  const localNow = () => {
    const d = new Date();
    return [d.getFullYear(), pad(d.getMonth() + 1), pad(d.getDate())]
      .join('-') + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  };

  function enhance(original) {
    if (original.dataset.tracker24hEnhanced) return;
    const kind = original.type;
    if (kind !== 'datetime-local' && kind !== 'time') return;
    const parent = original.parentNode;
    if (!parent) return;

    const isDateTime = kind === 'datetime-local';
    const form = original.form;
    const clock = document.createElement('input');
    clock.type = 'text';
    clock.className = 'tracker-time24-clock tracker-time24-input713';
    clock.placeholder = 'HHMM or HH:MM';
    clock.inputMode = 'numeric';
    clock.autocomplete = 'off';
    clock.maxLength = 5;
    clock.pattern =
      '(?:(?:[01][0-9]|2[0-3]):[0-5][0-9]|' +
      '(?:[01][0-9]|2[0-3])[0-5][0-9]|[0-9][0-5][0-9])';
    clock.required = original.required;
    clock.disabled = original.disabled;
    clock.readOnly = original.readOnly;
    clock.setAttribute('aria-label', 'Time (24-hour HHMM or HH:MM)');
    clock.title = 'Enter 0730, 930, 2130 or 07:30 (24-hour time)';

    let date = null;
    let container = null;
    if (isDateTime) {
      container = document.createElement('div');
      container.className = 'tracker-time24-controls tracker-time24-controls713';
      date = document.createElement('input');
      date.type = 'date';
      date.className = 'tracker-time24-date';
      date.required = original.required;
      date.disabled = original.disabled;
      date.readOnly = original.readOnly;
      date.setAttribute('aria-label', 'Date');
      container.append(date, clock);

      if (form && (
        form.matches('form[hx-post="/doses"]') ||
        form.matches('form#tracker-dose-correction-form')
      )) {
        const now = document.createElement('button');
        now.type = 'button';
        now.className = 'tracker-time24-now';
        now.textContent = 'Use current time';
        now.addEventListener('click', () => {
          original.value = localNow();
          original.dispatchEvent(new Event('change', {bubbles: true}));
        });
        container.append(now);
      }
      parent.insertBefore(container, original);
      const hint = document.createElement('small');
      hint.className = 'tracker-time24-hint';
      hint.textContent = '24-hour time: 0730 or 07:30 (no AM/PM)';
      parent.insertBefore(hint, original);
    } else {
      parent.insertBefore(clock, original);
    }

    original.hidden = true;
    original.required = false;
    original.tabIndex = -1;
    original.classList.add('tracker-time24-original713');
    original.setAttribute('aria-hidden', 'true');
    original.dataset.tracker24hEnhanced = 'true';

    let syncing = false;
    let lastSynced = null;

    function readOriginal() {
      if (syncing) return;
      const value = original.value;
      if (isDateTime) {
        const matched = stampPattern.exec(value);
        date.value = matched ? matched[1] : '';
        clock.value = matched ? matched[2] : '';
      } else {
        clock.value = clockPattern.test(value) ? value : '';
      }
      clock.setCustomValidity('');
      if (date) date.setCustomValidity('');
      lastSynced = value;
    }

    function writeOriginal() {
      const canonical = normalizeClock(clock.value);
      const validTime = !clock.value || clockPattern.test(clock.value) ||
        Boolean(canonical);
      const partial = isDateTime &&
        Boolean(date.value) !== Boolean(clock.value);
      if (date) {
        date.setCustomValidity(
          partial && !date.value ? 'Choose a date.' : ''
        );
      }
      clock.setCustomValidity(
        (!validTime || (partial && !clock.value))
          ? 'Enter 3–4 digits (e.g. 930 or 2130) or HH:MM (00:00–23:59).'
          : ''
      );
      const good = Boolean(canonical) &&
        (!isDateTime || Boolean(date.value));
      const next = good
        ? (isDateTime ? date.value + 'T' : '') + canonical
        : '';
      if (next === original.value) return;
      syncing = true;
      original.value = next;
      lastSynced = next;
      original.dispatchEvent(new Event('input', {bubbles: true}));
      original.dispatchEvent(new Event('change', {bubbles: true}));
      syncing = false;
    }

    function formatVisibleClock() {
      const canonical = normalizeClock(clock.value);
      if (canonical) clock.value = canonical;
      writeOriginal();
    }

    for (const input of [date, clock].filter(Boolean)) {
      input.addEventListener('input', writeOriginal);
      input.addEventListener('change',
        input === clock ? formatVisibleClock : writeOriginal);
    }
    clock.addEventListener('blur', formatVisibleClock);
    original.addEventListener('input', readOriginal);
    original.addEventListener('change', readOriginal);
    // Existing PK/calendar JS sometimes assigns .value without an event.
    // Refresh from the authoritative named input when the user focuses
    // the new visible control; never overwrite text in the middle of typing.
    clock.addEventListener('focus', () => {
      if (original.value !== lastSynced) readOriginal();
    });
    if (date) {
      date.addEventListener('focus', () => {
        if (original.value !== lastSynced) readOriginal();
      });
    }
    if (form) {
      form.addEventListener('reset', () => queueMicrotask(readOriginal));
      // Also normalize on keyboard-driven submit without losing the
      // original named field used by HTMX/normal POST handlers.
      form.addEventListener('submit', formatVisibleClock);
    }
    readOriginal();
  }

  let queued = false;
  function enhanceAll() {
    queued = false;
    document.querySelectorAll(
      'input[type="datetime-local"], input[type="time"]'
    ).forEach(enhance);
  }
  function schedule() {
    if (queued) return;
    queued = true;
    queueMicrotask(enhanceAll);
  }

  function initialize() {
    enhanceAll();
    document.addEventListener('htmx:afterSwap', schedule);
    document.addEventListener('htmx:afterSettle', schedule);
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(records => {
        if (records.some(record => record.addedNodes.length)) schedule();
      }).observe(document.body, {childList: true, subtree: true});
    }
    window.addEventListener('pageshow', () => {
      document.querySelectorAll(
        'input.tracker-time24-original713'
      ).forEach(original => original.dispatchEvent(
        new Event('change', {bubbles: false})
      ));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once: true});
  } else {
    initialize();
  }
})();
