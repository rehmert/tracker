/*
 * Tracker Stage 34.29
 * Lightweight, accessible navigation icons.
 *
 * No external libraries.
 * No changes to navigation destinations.
 */

(() => {
  'use strict';

  const paths = {
    dashboard: `
      <rect x="3" y="3" width="7" height="7" rx="1.5"/>
      <rect x="14" y="3" width="7" height="7" rx="1.5"/>
      <rect x="3" y="14" width="7" height="7" rx="1.5"/>
      <rect x="14" y="14" width="7" height="7" rx="1.5"/>
    `,

    protocols: `
      <rect x="5" y="3" width="14" height="18" rx="2"/>
      <path d="M9 3.5h6M9 9h6M9 13h6M9 17h4"/>
      <path d="M7 9h.01M7 13h.01M7 17h.01"/>
    `,

    inventory: `
      <path d="M3 7 12 3l9 4v10l-9 4-9-4z"/>
      <path d="m3 7 9 4 9-4M12 11v10"/>
      <path d="m7.5 5 9 4"/>
    `,

    dosing: `
      <path d="m5 19 14-14"/>
      <path d="m14 4 6 6M4 14l6 6"/>
      <path d="m3 21 3-3M18 3l3-1"/>
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
      <circle cx="12" cy="12" r="3"/>
      <path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.5-2.3.9a8 8 0 0 0-1.7-1L14.5 3h-4L10 5.9a8 8 0 0 0-1.7 1L6 6l-2 3.5L6 11a7 7 0 0 0 0 2l-2 1.5L6 18l2.3-.9a8 8 0 0 0 1.7 1l.5 2.9h4l.4-2.9a8 8 0 0 0 1.7-1l2.3.9 2-3.5-2-1.5a7 7 0 0 0 .1-1z"/>
    `,

    purchasing: `
      <path d="M3 4h2l2.5 11h11l2-8H6"/>
      <circle cx="9" cy="20" r="1"/>
      <circle cx="18" cy="20" r="1"/>
    `,

    charts: `
      <path d="M4 20V4M4 20h16"/>
      <path d="m7 15 4-5 3 2 5-7"/>
    `,

    preferences: `
      <path d="M4 7h16M4 17h16"/>
      <circle cx="9" cy="7" r="2"/>
      <circle cx="16" cy="17" r="2"/>
    `
  };

  const rules = [
    [/dose[\s-]*workspace|administration/i, 'dosing'],
    [/protocol/i, 'protocols'],
    [/inventory|vials|supplies|compounds/i, 'inventory'],
    [/purchase|vendors|orders/i, 'purchasing'],
    [/calendar|schedule/i, 'calendar'],
    [/lab|bloodwork|analytes/i, 'labs'],
    [/preferences/i, 'preferences'],
    [/settings|configuration/i, 'settings'],
    [/dashboard|overview|home/i, 'dashboard'],
    [/statistics|analytics|reports|trends/i, 'charts'],
    [/dosing|dose log|dose history/i, 'dosing']
  ];

  function classify(anchor) {
    const label = (
      anchor.textContent || ''
    ).replace(/\s+/g, ' ').trim();

    const href = anchor.getAttribute('href') || '';

    // Match the displayed navigation label first.
    for (const [pattern, kind] of rules) {
      if (pattern.test(label)) return kind;
    }

    // Use the destination only as a fallback.
    const pathname = href.split(/[?#]/)[0];

    if (/^\/(?:$|dashboard\/?$)/i.test(pathname)) {
      return 'dashboard';
    }

    const segments = pathname
      .split('/')
      .filter(Boolean);

    const last = segments.at(-1) || '';

    for (const [pattern, kind] of rules) {
      if (pattern.test(last)) return kind;
    }

    return null;
  }

  function makeIcon(kind) {
    const namespace = 'http://www.w3.org/2000/svg';

    const svg = document.createElementNS(
      namespace, 'svg'
    );

    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.7');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');

    svg.classList.add('tracker-nav-icon');

    // Paths are static, application-owned SVG markup.
    svg.innerHTML = paths[kind];

    return svg;
  }

  function initialize() {
    const selectors = [
      'nav a[href]',
      '.sidebar a[href]',
      '.side-nav a[href]',
      '[role="navigation"] a[href]'
    ];

    const anchors = new Set();

    selectors.forEach(selector => {
      document.querySelectorAll(selector).forEach(
        anchor => anchors.add(anchor)
      );
    });

    let added = 0;

    anchors.forEach(anchor => {
      if (
        anchor.querySelector('.tracker-nav-icon') ||
        anchor.dataset.trackerNavIcon === '1'
      ) {
        return;
      }

      const kind = classify(anchor);
      if (!kind || !paths[kind]) return;

      // Avoid interfering with links containing complex widgets.
      if (
        anchor.querySelector(
          'input, select, textarea, button'
        )
      ) {
        return;
      }

      anchor.prepend(makeIcon(kind));
      anchor.dataset.trackerNavIcon = '1';
      added++;
    });

    window.trackerNavigationIconDiagnostics = () => ({
      navigationLinks: anchors.size,
      decoratedLinks: document.querySelectorAll(
        '.tracker-nav-icon'
      ).length,
      addedThisRun: added
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
