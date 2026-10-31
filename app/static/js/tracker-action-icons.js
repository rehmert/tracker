/*
 * Tracker Stage 34.30
 * Decorative icons for page headings and common actions.
 *
 * No external libraries.
 * No changes to form submission or navigation behavior.
 */

(() => {
  'use strict';

  const NS = 'http://www.w3.org/2000/svg';

  const icons = {
    dashboard: `
      <rect x="3" y="3" width="7" height="7" rx="1.5"/>
      <rect x="14" y="3" width="7" height="7" rx="1.5"/>
      <rect x="3" y="14" width="7" height="7" rx="1.5"/>
      <rect x="14" y="14" width="7" height="7" rx="1.5"/>
    `,
    protocols: `
      <rect x="5" y="3" width="14" height="18" rx="2"/>
      <path d="M9 9h6M9 13h6M9 17h4"/>
      <path d="m7 9 .5.5L8.5 8M7 13l.5.5L8.5 12"/>
    `,
    inventory: `
      <path d="M3 7 12 3l9 4v10l-9 4-9-4z"/>
      <path d="m3 7 9 4 9-4M12 11v10"/>
    `,
    dosing: `
      <path d="m5 19 14-14M14 4l6 6M4 14l6 6"/>
      <path d="m9 10 2 2M12 7l2 2"/>
    `,
    calendar: `
      <rect x="3" y="5" width="18" height="16" rx="2"/>
      <path d="M7 3v4M17 3v4M3 10h18"/>
      <path d="m8 15 2.5 2.5L16 12"/>
    `,
    labs: `
      <path d="M9 3h6M10 3v7l-5 8a2 2 0 0 0 1.7 3h10.6A2 2 0 0 0 19 18l-5-8V3"/>
      <path d="M8 16h8"/>
    `,
    settings: `
      <path d="M4 7h16M4 12h16M4 17h16"/>
      <circle cx="9" cy="7" r="2"/>
      <circle cx="16" cy="12" r="2"/>
      <circle cx="9" cy="17" r="2"/>
    `,
    plus: `
      <path d="M12 5v14M5 12h14"/>
    `,
    check: `
      <path d="m4 12 5 5L20 6"/>
    `,
    edit: `
      <path d="M12 20h9"/>
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L9 17l-4 1 1-4z"/>
    `,
    trash: `
      <path d="M3 6h18M8 6V4h8v2M6 6l1 15h10l1-15"/>
      <path d="M10 10v7M14 10v7"/>
    `,
    search: `
      <circle cx="11" cy="11" r="7"/>
      <path d="m16 16 5 5"/>
    `,
    download: `
      <path d="M12 3v12m-5-5 5 5 5-5"/>
      <path d="M4 17v4h16v-4"/>
    `
  };

  const headingRules = [
    [/dose[\s-]*workspace|administration/i, 'dosing'],
    [/protocol/i, 'protocols'],
    [/inventory|vials|supplies|compounds/i, 'inventory'],
    [/calendar|schedule/i, 'calendar'],
    [/lab|bloodwork|analyte/i, 'labs'],
    [/settings|preferences/i, 'settings'],
    [/dashboard|overview/i, 'dashboard']
  ];

  const actionRules = [
    [/^(?:add|new|create)(?:\s|$)/i, 'plus'],
    [/^(?:save|update|apply)(?:\s|$)/i, 'check'],
    [/^edit(?:\s|$)/i, 'edit'],
    [/^(?:delete|remove|discard)(?:\s|$)/i, 'trash'],
    [/^search(?:\s|$)/i, 'search'],
    [/^(?:download|export)(?:\s|$)/i, 'download']
  ];

  function normalize(value) {
    return String(value || '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function classify(text, rules) {
    for (const [pattern, kind] of rules) {
      if (pattern.test(text)) return kind;
    }
    return null;
  }

  function makeIcon(kind, className) {
    const svg = document.createElementNS(NS, 'svg');

    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.7');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');

    svg.classList.add('tracker-action-icon', className);

    svg.innerHTML = icons[kind];

    return svg;
  }

  function decorateHeading(heading) {
    if (
      heading.dataset.trackerHeadingIcon ||
      heading.querySelector('.tracker-heading-icon')
    ) {
      return false;
    }

    const text = normalize(heading.textContent);
    const kind = classify(text, headingRules);

    if (!kind) return false;

    // Keep headings containing interactive controls untouched.
    if (
      heading.querySelector(
        'button, input, select, textarea, a'
      )
    ) {
      return false;
    }

    heading.prepend(makeIcon(kind, 'tracker-heading-icon'));
    heading.dataset.trackerHeadingIcon = kind;

    return true;
  }

  function decorateAction(element) {
    if (
      element.dataset.trackerActionIcon ||
      element.querySelector('.tracker-action-icon')
    ) {
      return false;
    }

    if (element.matches('[disabled], [aria-disabled="true"]')) {
      // Disabled controls are still eligible for decoration.
    }

    if (
      element.querySelector(
        'svg, img, input, select, textarea'
      )
    ) {
      return false;
    }

    // Avoid changing input buttons, icon-only controls,
    // or elements with custom child widgets.
    if (element.tagName === 'INPUT') return false;

    const text = normalize(element.textContent);
    if (!text || text.length > 50) return false;

    const kind = classify(text, actionRules);
    if (!kind) return false;

    // Do not decorate a button that is itself part of
    // an existing icon-based control.
    if (element.closest('[data-tracker-no-icons]')) {
      return false;
    }

    element.prepend(makeIcon(kind, 'tracker-button-icon'));
    element.dataset.trackerActionIcon = kind;

    if (kind === 'trash') {
      element.classList.add('tracker-destructive-action');
    }

    return true;
  }

  function initialize(root = document) {
    let headings = 0;
    let actions = 0;

    root.querySelectorAll(
      'main h1, main h2, .content h1, .content h2, ' +
      '.page-content h1, .page-content h2'
    ).forEach(heading => {
      if (decorateHeading(heading)) headings++;
    });

    root.querySelectorAll(
      'main button, main a.btn, ' +
      '.content button, .content a.btn, ' +
      '.page-content button, .page-content a.btn'
    ).forEach(element => {
      if (decorateAction(element)) actions++;
    });

    return { headings, actions };
  }

  function start() {
    initialize();

    window.trackerActionIconDiagnostics = () => ({
      headings: document.querySelectorAll(
        '.tracker-heading-icon'
      ).length,
      actions: document.querySelectorAll(
        '.tracker-button-icon'
      ).length,
      destructiveActions: document.querySelectorAll(
        '.tracker-destructive-action'
      ).length
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      start,
      { once: true }
    );
  } else {
    start();
  }
})();
