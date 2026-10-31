/*
 * Tracker Stage 34.4
 *
 * Suggested vial shortcut for Dose Workspace.
 *
 * Read-only navigation. Uses the existing
 * server-selected recommendation.
 */

(() => {
  'use strict';

  function initialize() {
    const table = document.querySelector(
      '#tracker-available-vials ' +
      '[data-tracker-sortable-vials]'
    );

    const button = document.getElementById(
      'tracker-workspace-jump'
    );

    const details = document.getElementById(
      'tracker-workspace-suggestion'
    );

    const search = document.getElementById(
      'tracker-vial-search'
    );

    if (!table || !button || !details) {
      return;
    }

    const suggested = table.querySelector(
      '[data-tracker-vial-row]' +
      '[data-tracker-recommended="1"]'
    );

    if (!suggested) {
      button.disabled = true;
      details.textContent =
        'No suggested inventory vial for this selection.';
      return;
    }

    const compound =
      suggested.dataset.trackerCompound || '';

    const vial =
      suggested.dataset.trackerVial || '';

    const remaining =
      suggested.cells[4]?.textContent.trim() || '';

    details.textContent =
      `${compound} · ${vial}` +
      (remaining ? ` · ${remaining} remaining` : '');

    const style = document.createElement('style');

    style.textContent = `
      #tracker-workspace-shortcut {
        display:flex;
        flex-wrap:wrap;
        align-items:center;
        gap:.75rem;
        padding:.8rem 1rem;
        margin:.75rem 0;
      }

      #tracker-workspace-shortcut .details {
        flex:1 1 16rem;
        min-width:0;
      }

      #tracker-workspace-shortcut .details strong {
        display:block;
        margin-bottom:.2rem;
      }

      #tracker-workspace-shortcut .details span {
        overflow-wrap:anywhere;
      }

      #tracker-workspace-shortcut button:disabled {
        opacity:.5;
        cursor:not-allowed;
      }

      #tracker-available-vials
      tr.tracker-workspace-focus {
        outline:2px solid var(--accent,#2563eb);
        outline-offset:-2px;
      }

      #tracker-available-vials
      tr.tracker-workspace-focus > td {
        background:rgba(59,130,246,.12);
      }
    `;

    document.head.appendChild(style);

    let focusTimer = null;

    button.addEventListener('click', () => {
      /*
       * The existing search implementation controls
       * row visibility. Clear it only when it hides
       * the suggested vial.
       */
      if (suggested.hidden && search) {
        search.value = '';

        search.dispatchEvent(
          new Event('input', { bubbles:true })
        );
      }

      /*
       * Never change the table's current sort order.
       */
      suggested.classList.add(
        'tracker-workspace-focus'
      );

      suggested.scrollIntoView({
        behavior:'auto',
        block:'center',
        inline:'nearest'
      });

      if (focusTimer !== null) {
        clearTimeout(focusTimer);
      }

      focusTimer = setTimeout(() => {
        suggested.classList.remove(
          'tracker-workspace-focus'
        );
        focusTimer = null;
      }, 3500);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initialize,
      { once:true }
    );
  } else {
    initialize();
  }
})();
