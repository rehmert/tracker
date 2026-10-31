/*
 * Tracker Stage 34.34
 *
 * Enhances the existing Dashboard customization UI.
 * Does not replace Tracker's layout persistence.
 */

(() => {
  'use strict';

  function initialize() {
    const list = document.getElementById(
      'dashboard-customize-list'
    );

    const panel = document.getElementById(
      'dashboard-customize-panel'
    );

    const reset = document.getElementById(
      'dashboard-reset'
    );

    if (!list || !panel) return;

    const summary = document.createElement('p');

    summary.id = 'tracker-dashboard-panel-summary';
    summary.className = 'note';
    summary.setAttribute('aria-live', 'polite');

    list.before(summary);

    function update() {
      const rows = Array.from(
        list.querySelectorAll('.customize-row')
      );

      const total = rows.length;

      const visible = rows.filter(row => {
        const checkbox = row.querySelector(
          'input[type="checkbox"]'
        );

        return checkbox && checkbox.checked;
      }).length;

      const summaryText =
        `${visible} of ${total} dashboard sections visible`;

      if (summary.textContent !== summaryText) {
        summary.textContent = summaryText;
      }

      rows.forEach((row, index) => {
        const label = row.querySelector('label');

        const checkbox = row.querySelector(
          'input[type="checkbox"]'
        );

        const buttons = Array.from(
          row.querySelectorAll('button')
        );

        const title = (
          label?.textContent || 'Dashboard section'
        ).trim();

        if (checkbox) {
          const name = `Show ${title}`;

          if (checkbox.getAttribute('aria-label') !== name) {
            checkbox.setAttribute('aria-label', name);
          }
        }

        buttons.forEach((button, buttonIndex) => {
          const direction = buttonIndex === 0
            ? 'up'
            : 'down';

          const name = `Move ${title} ${direction}`;

          if (button.getAttribute('aria-label') !== name) {
            button.setAttribute('aria-label', name);
          }
        });

        row.dataset.trackerPanelPosition =
          String(index + 1);
      });

      if (reset) {
        const title = 'Restore default dashboard layout';

        if (reset.getAttribute('title') !== title) {
          reset.setAttribute('title', title);
        }

        if (reset.textContent.trim() !== 'Reset to defaults') {
          reset.textContent = 'Reset to defaults';
        }
      }
    }

    // The existing customization script redraws its rows
    // when panels are reordered. Observe those redraws.
    let scheduled = false;

    const observer = new MutationObserver(() => {
      if (scheduled) return;

      scheduled = true;

      queueMicrotask(() => {
        scheduled = false;
        update();
      });
    });

    observer.observe(list, {
      childList: true,
      subtree: true
    });

    list.addEventListener('change', () => {
      queueMicrotask(update);
    });

    update();

    window.trackerDashboardCustomizationDiagnostics =
      () => ({
        totalPanels: document.querySelectorAll(
          '[data-dashboard-panel]'
        ).length,

        customizationRows: list.querySelectorAll(
          '.customize-row'
        ).length,

        visiblePanels: Array.from(
          document.querySelectorAll(
            '[data-dashboard-panel]'
          )
        ).filter(element => !element.hidden).length,

        needsAttentionPresent: Boolean(
          document.getElementById(
            'tracker-attention-heading'
          )
        )
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
