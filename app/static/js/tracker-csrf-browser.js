/* CSRF rollout: issue submission tokens without enforcement. */
(() => {
  'use strict';

  const COOKIE = 'tracker_csrf_v1';
  const FIELD = 'csrf_token';
  const HEADER = 'X-Tracker-CSRF';

  function token() {
    const prefix = COOKIE + '=';
    for (const part of document.cookie.split(';')) {
      const entry = part.trim();
      if (entry.startsWith(prefix)) {
        try {
          return decodeURIComponent(entry.slice(prefix.length));
        } catch (_) {
          return '';
        }
      }
    }
    return '';
  }

  window.trackerCsrfToken = token;

  function localTarget(url) {
    try {
      return new URL(url || location.href, location.href).origin
        === location.origin;
    } catch (_) {
      return false;
    }
  }

  function enhanceForm(form) {
    if (!(form instanceof HTMLFormElement)) return;
    if (!localTarget(form.action)) return;
    if (form.method.toUpperCase() !== 'POST') return;

    const value = token();
    if (!value) return;

    let field = [...form.elements].find(
      element => element.name === FIELD
    );
    if (!field) {
      field = document.createElement('input');
      field.type = 'hidden';
      field.name = FIELD;
      form.appendChild(field);
    }
    field.value = value;
  }

  function enhanceForms() {
    document.querySelectorAll('form').forEach(enhanceForm);
  }

  document.addEventListener('submit', event => {
    enhanceForm(event.target);
  }, true);

  document.addEventListener('htmx:configRequest', event => {
    const detail = event.detail;
    if (!detail || !detail.headers) return;
    const method = String(detail.verb || 'GET').toUpperCase();
    if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) return;
    if (!localTarget(detail.path)) return;
    const value = token();
    if (value) detail.headers[HEADER] = value;
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceForms);
  } else {
    enhanceForms();
  }

  // Include forms inserted later by HTMX and other UI updates.
  const startObserver = () => {
    if (!document.documentElement) return;
    new MutationObserver(changes => {
      if (changes.some(change => change.addedNodes.length)) {
        enhanceForms();
      }
    }).observe(document.documentElement, {
      childList: true,
      subtree: true,
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startObserver);
  } else {
    startObserver();
  }
})();
