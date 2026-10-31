/*
 * Tracker Stage 34.37
 * Complete sidebar navigation icon coverage.
 *
 * Uses inline SVG with no external dependencies.
 * Supports dynamic favorites and navigation changes.
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

    globe: `
      <circle cx="12" cy="12" r="9"/>
      <path d="M3 12h18"/>
      <path d="M12 3a15 15 0 0 1 0 18"/>
      <path d="M12 3a15 15 0 0 0 0 18"/>
    `,

    box: `
      <path d="M3 7 12 3l9 4v10l-9 4-9-4z"/>
      <path d="m3 7 9 4 9-4M12 11v10"/>
    `,

    heart: `
      <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z"/>
    `,

    pencil: `
      <path d="M12 20h9"/>
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L9 17l-4 1 1-4z"/>
    `,

    calendar: `
      <rect x="3" y="5" width="18" height="16" rx="2"/>
      <path d="M7 3v4M17 3v4M3 10h18"/>
    `,

    clock: `
      <circle cx="12" cy="12" r="9"/>
      <path d="M12 7v5l3 2"/>
    `,

    clipboard: `
      <rect x="5" y="5" width="14" height="16" rx="2"/>
      <rect x="9" y="3" width="6" height="4" rx="1"/>
      <path d="M9 12h6M9 16h6"/>
    `,

    syringe: `
      <path d="m5 19 14-14"/>
      <path d="m14 4 6 6M4 14l6 6"/>
      <path d="m3 21 3-3M18 3l3-1"/>
    `,

    chart: `
      <path d="M4 20V4M4 20h16"/>
      <path d="m7 15 4-5 3 2 5-7"/>
    `,

    flask: `
      <path d="M9 3h6M10 3v7l-5 8a2 2 0 0 0 1.7 3h10.6A2 2 0 0 0 19 18l-5-8V3"/>
      <path d="M8 16h8"/>
    `,

    cart: `
      <path d="M3 4h2l2.5 11h11l2-8H6"/>
      <circle cx="9" cy="20" r="1"/>
      <circle cx="18" cy="20" r="1"/>
    `,

    document: `
      <path d="M6 3h9l4 4v14H6z"/>
      <path d="M15 3v5h4M9 12h7M9 16h7"/>
    `,

    database: `
      <ellipse cx="12" cy="5" rx="8" ry="3"/>
      <path d="M4 5v14c0 4 16 4 16 0V5"/>
      <path d="M4 12c0 4 16 4 16 0"/>
    `,

    shield: `
      <path d="M12 2 20 5v6c0 5-3.5 8-8 11-4.5-3-8-6-8-11V5z"/>
      <path d="m9 12 2 2 4-4"/>
    `,

    archive: `
      <rect x="3" y="4" width="18" height="5" rx="1"/>
      <path d="M5 9v11h14V9M10 13h4"/>
    `,

    alert: `
      <path d="M12 3 2 21h20z"/>
      <path d="M12 9v5M12 18h.01"/>
    `,

    layers: `
      <path d="m12 3 9 5-9 5-9-5z"/>
      <path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>
    `,

    sliders: `
      <path d="M4 7h16M4 17h16"/>
      <circle cx="9" cy="7" r="2"/>
      <circle cx="16" cy="17" r="2"/>
    `,

    search: `
      <circle cx="10.5" cy="10.5" r="6.5"/>
      <path d="m16 16 5 5"/>
    `,

    refresh: `
      <path d="M20 7v5h-5M4 17v-5h5"/>
      <path d="M5.5 9a7 7 0 0 1 12-2L20 12"/>
      <path d="M18.5 15a7 7 0 0 1-12 2L4 12"/>
    `,

    download: `
      <path d="M12 3v12m-4-4 4 4 4-4"/>
      <path d="M4 17v4h16v-4"/>
    `,

    tag: `
      <path d="M3 4h9l9 9-8 8-10-10z"/>
      <circle cx="8" cy="9" r="1"/>
    `,

    activity: `
      <path d="M2 12h4l3-7 5 14 3-7h5"/>
    `,

    calculator: `
      <rect x="5" y="2" width="14" height="20" rx="2"/>
      <path d="M8 7h8M8 12h2M14 12h2M8 17h2M14 17h2"/>
    `,

    truck: `
      <path d="M3 6h11v11H3zM14 10h4l3 4v3h-7z"/>
      <circle cx="7" cy="18" r="2"/>
      <circle cx="18" cy="18" r="2"/>
    `
  };

  const exact = {
    '/': 'dashboard',
    '/workflow-hub': 'globe',
    '/activity': 'activity',
    '/calendar': 'calendar',
    '/quick-entry': 'pencil',
    '/pages': 'pencil',
    '/record-explorer/notes': 'document',

    '/protocols': 'clipboard',
    '/protocol-tools': 'sliders',
    '/protocol-coverage': 'chart',
    '/doses': 'syringe',
    '/dose-workspace': 'syringe',
    '/pk': 'chart',
    '/blends': 'flask',

    '/vials': 'box',
    '/record-explorer/vials': 'search',
    '/compounds': 'flask',
    '/purchases': 'cart',
    '/purchase-analysis': 'chart',
    '/supplies': 'box',
    '/consumption': 'chart',
    '/coas': 'document',

    '/inventory-intelligence': 'chart',
    '/inventory-alerts': 'alert',
    '/inventory-health': 'shield',
    '/inventory-forecast': 'chart',
    '/forecast-horizons': 'calendar',
    '/forecast-audit': 'clipboard',
    '/scheduled-forecast': 'calendar',
    '/planning-hub': 'globe',
    '/expiry-exposure': 'clock',
    '/fefo-forecast': 'clock',
    '/inventory-timeline': 'clock',
    '/reconciliation': 'refresh',

    '/vendor-prices': 'tag',

    '/vitals': 'heart',
    '/labs': 'flask',
    '/health-timeline': 'heart',
    '/health-insights': 'heart',
    '/record-explorer/health': 'heart',

    '/reports': 'chart',
    '/sqlite-viewer': 'database',
    '/record-explorer/database': 'database',
    '/exports': 'download',
    '/data-integrity': 'shield',
    '/backups': 'archive',
    '/maintenance-review': 'clipboard',
    '/audit-history': 'clock'
  };

  const fallbackRules = [
    [/health|vital|heart|wellness/i, 'heart'],
    [/note|edit|entry|journal/i, 'pencil'],
    [/inventory|vial|supply|stock/i, 'box'],
    [/dose|inject|syringe/i, 'syringe'],
    [/protocol|task|checklist/i, 'clipboard'],
    [/calendar|schedule|date/i, 'calendar'],
    [/expiry|expiration|history|timeline/i, 'clock'],
    [/alert|warning|risk/i, 'alert'],
    [/lab|compound|blend/i, 'flask'],
    [/report|analytics|forecast|trend/i, 'chart'],
    [/purchase|order|vendor/i, 'cart'],
    [/database|sqlite|data/i, 'database'],
    [/backup|archive/i, 'archive'],
    [/export|download/i, 'download'],
    [/search|explorer/i, 'search'],
    [/settings|preference/i, 'sliders']
  ];

  function classify(anchor) {
    const raw = anchor.getAttribute('href') || '';

    let path;

    try {
      const url = new URL(raw, location.href);

      if (url.origin !== location.origin) {
        return 'globe';
      }

      path = url.pathname.replace(/\/+$/, '') || '/';
    } catch (_) {
      path = raw.split(/[?#]/)[0];
    }

    if (Object.hasOwn(exact, path)) {
      return exact[path];
    }

    const label = (
      anchor.querySelector('.nav-text')?.textContent ||
      anchor.textContent ||
      ''
    ).trim();

    const target = `${label} ${path}`;

    for (const [pattern, kind] of fallbackRules) {
      if (pattern.test(target)) return kind;
    }

    // Every sidebar link receives an icon.
    return 'globe';
  }

  function makeIcon(kind) {
    const svg = document.createElementNS(NS, 'svg');

    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.7');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');

    svg.classList.add('tracker-nav-icon');

    svg.innerHTML = icons[kind] || icons.globe;

    return svg;
  }

  function decorate() {
    const sidebar = document.getElementById('app-sidebar');

    if (!sidebar) return;

    const anchors = sidebar.querySelectorAll(
      '.nav-links li > a[href]'
    );

    anchors.forEach(anchor => {
      const kind = classify(anchor);

      // Keep any existing SVG and update it in place.
      // This avoids duplicates during favorites redraws.
      const existing = anchor.querySelector(
        ':scope > .tracker-nav-icon'
      );

      if (existing) {
        if (existing.dataset.kind !== kind) {
          existing.innerHTML = icons[kind] || icons.globe;
          existing.dataset.kind = kind;
        }
      } else {
        const svg = makeIcon(kind);
        svg.dataset.kind = kind;

        const dot = anchor.querySelector(
          ':scope > .nav-dot'
        );

        if (dot) {
          dot.after(svg);
        } else {
          anchor.prepend(svg);
        }
      }

      anchor.dataset.trackerNavIcon = '1';
      anchor.classList.add('tracker-nav-iconized');
    });
  }

  function initialize() {
    const sidebar = document.getElementById('app-sidebar');

    if (!sidebar) return;

    decorate();

    // Favorites and navigation sorting may rebuild links.
    // Reapply icons after those changes without duplicating them.
    let pending = false;

    const observer = new MutationObserver(() => {
      if (pending) return;

      pending = true;

      requestAnimationFrame(() => {
        pending = false;
        decorate();
      });
    });

    observer.observe(sidebar, {
      childList: true,
      subtree: true
    });

    window.trackerNavigationIconDiagnostics = () => {
      const links = Array.from(
        sidebar.querySelectorAll('.nav-links li > a[href]')
      );

      return {
        navigationLinks: links.length,
        decoratedLinks: links.filter(
          link => Boolean(
            link.querySelector(':scope > .tracker-nav-icon')
          )
        ).length,
        missingIcons: links.filter(
          link => !link.querySelector(
            ':scope > .tracker-nav-icon'
          )
        ).map(link => link.getAttribute('href')),
        iconTypes: [...new Set(
          links.map(link =>
            link.querySelector(
              ':scope > .tracker-nav-icon'
            )?.dataset.kind
          ).filter(Boolean)
        )].sort()
      };
    };
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
