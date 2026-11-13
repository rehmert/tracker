/* Release 600: preserve mobile picker position during local updates and
   auto-submitted GET filters. Only geometry is stored, never field values. */
(() => {
  'use strict';
  const MOBILE = window.matchMedia('(max-width: 760px)');
  const KEY = 'tracker.mobile600.dropdown-scroll.v1';
  const EXPIRY_MS = 60000;
  let opening = null;

  function eligible(node) {
    return MOBILE.matches && node instanceof HTMLSelectElement &&
      node.id !== 'tracker-page-jump-select' &&
      !node.closest('.tracker-page-jump, [data-mobile600-scroll-exempt]');
  }

  function capture(event) {
    const select = event.target;
    if (!eligible(select)) return;
    opening = {
      select,
      top: select.getBoundingClientRect().top,
      path: location.pathname,
      hash: location.hash
    };
  }

  // pointerdown precedes a native mobile picker opening; focusin covers
  // keyboard and accessibility-driven selection.
  document.addEventListener('pointerdown', capture, true);
  document.addEventListener('focusin', event => {
    if (opening?.select !== event.target) capture(event);
  }, true);
  // A cancelled native picker may blur without dispatching a change.
  document.addEventListener('focusout', event => {
    const snapshot = opening;
    if (!snapshot || snapshot.select !== event.target) return;
    requestAnimationFrame(() => {
      if (opening !== snapshot) return; // change already handled it
      opening = null;
      preserveInPlace(snapshot.select, snapshot);
    });
  }, true);

  function submittedGetFilter(select) {
    const form = select.form;
    if (!form || form.method.toLowerCase() !== 'get') return false;
    if (!/\b(?:requestSubmit|submit)\s*\(/.test(
      select.getAttribute('onchange') || ''
    )) return false;
    const action = new URL(form.getAttribute('action') || location.href, location.href);
    return action.origin === location.origin && action.pathname === location.pathname;
  }

  function rememberNavigation(select, top) {
    const form = select.form;
    const peers = Array.from(document.querySelectorAll('select')).filter(
      other => other.name === select.name && other.form &&
        (other.form.getAttribute('action') || '') ===
        (form.getAttribute('action') || '')
    );
    const record = {
      path: location.pathname,
      hash: location.hash,
      id: select.id || '',
      name: select.name,
      action: form.getAttribute('action') || '',
      peer: peers.indexOf(select),
      top: Math.round(top),
      savedAt: Date.now()
    };
    try { sessionStorage.setItem(KEY, JSON.stringify(record)); }
    catch (_) { /* Without storage, the filter still submits normally. */ }
  }

  function preserveInPlace(select, snapshot) {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (!MOBILE.matches || !select.isConnected ||
          location.pathname !== snapshot.path ||
          location.hash !== snapshot.hash) return;
      const shift = select.getBoundingClientRect().top - snapshot.top;
      // Ignore subpixel movement; never interfere with deliberate navigation.
      if (Math.abs(shift) >= 24) {
        window.scrollBy({top: shift, left: 0, behavior: 'instant'});
      }
    }));
  }

  // Capture phase: runs before inline onchange="this.form.submit()" navigates.
  document.addEventListener('change', event => {
    const select = event.target;
    if (!eligible(select)) return;
    const snapshot = opening?.select === select
      ? opening
      : {select, top: select.getBoundingClientRect().top,
         path: location.pathname, hash: location.hash};
    opening = null;

    if (submittedGetFilter(select)) {
      rememberNavigation(select, snapshot.top);
    } else {
      preserveInPlace(select, snapshot);
    }
  }, true);

  function restoreGetFilter() {
    if (!MOBILE.matches) return;
    let item;
    try {
      const raw = sessionStorage.getItem(KEY);
      if (!raw) return;
      sessionStorage.removeItem(KEY);
      item = JSON.parse(raw);
    } catch (_) { return; }
    if (!item || item.path !== location.pathname ||
        item.hash !== location.hash ||
        !Number.isFinite(item.top) ||
        !Number.isInteger(item.peer) || item.peer < 0 ||
        Date.now() - item.savedAt > EXPIRY_MS) return;

    requestAnimationFrame(() => requestAnimationFrame(() => {
      const peers = Array.from(document.querySelectorAll('select')).filter(
        select => eligible(select) && select.name === item.name &&
          select.form && select.form.method.toLowerCase() === 'get' &&
          (select.form.getAttribute('action') || '') === item.action
      );
      const select = (item.id && document.getElementById(item.id)) ||
        peers[item.peer];
      if (!eligible(select) || !select.getClientRects().length) return;

      // Keep the same on-screen position even when the filter changes
      // the number of rows above the selected control.
      const delta = select.getBoundingClientRect().top - item.top;
      window.scrollBy({top: delta, left: 0, behavior: 'instant'});
    }));
  }

  window.addEventListener('pageshow', restoreGetFilter);
})();
