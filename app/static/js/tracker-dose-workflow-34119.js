(() => {
  'use strict';

  const STAGE = '34119';

  function initialize() {
    const form = document.querySelector(
      'form[hx-post="/doses"]'
    );

    if (!form) return;

    const preview = document.getElementById(
      'dose-preview'
    );

    const context = document.getElementById(
      'dose-context'
    );

    const shortcuts = document.querySelector(
      '.ux-shortcuts'
    );

    const vial = form.querySelector(
      'select[name="vial_id"]'
    );

    const when = form.querySelector(
      'input[name="taken_at"]'
    );

    const submit = form.querySelector(
      'button[type="submit"]'
    );

    if (
      !preview ||
      !context ||
      !shortcuts ||
      !vial ||
      !when ||
      !submit
    ) {
      return;
    }

    // Give existing elements stable navigation targets.
    const details = when.closest('label');

    if (details && !details.id) {
      details.id = `tracker-recording-details-${STAGE}`;
    }

    if (!submit.id) {
      submit.id = `tracker-submit-${STAGE}`;
    }

    // Add navigation without moving or wrapping
    // any existing form controls.
    function addShortcut(label, target) {
      if (!target) return;

      const link = document.createElement('a');

      link.href = '#' + target;
      link.textContent = label;
      link.className = 'tracker-workflow-shortcut';

      shortcuts.appendChild(link);
    }

    if (
      !document.getElementById(
        `tracker-shortcuts-installed-${STAGE}`
      )
    ) {
      const marker = document.createElement('span');
      marker.id =
        `tracker-shortcuts-installed-${STAGE}`;
      marker.hidden = true;

      shortcuts.appendChild(marker);

      addShortcut(
        'Review calculation',
        preview.id
      );

      addShortcut(
        'Recording details',
        details?.id
      );

      addShortcut(
        'Save entry ↓',
        submit.id
      );
    }

    // Preserve scheduled context when returning to
    // the Dose Workspace from the Dose Log.
    const workspaceLink = document.querySelector(
      '[data-planned-workspace]'
    );

    function updateWorkspaceLink() {
      if (!workspaceLink) return;

      const url = new URL(
        workspaceLink.href,
        window.location.href
      );

      if (
        url.origin !== window.location.origin ||
        url.pathname !== '/dose-workspace'
      ) {
        return;
      }

      const selected =
        vial.selectedOptions?.[0];

      const compoundId =
        selected?.dataset?.compoundId;

      // Use the compound belonging to the selected
      // vial, not an unrelated history filter.
      if (compoundId && /^\d+$/.test(compoundId)) {
        url.searchParams.set(
          'compound_id',
          compoundId
        );
      }

      // Existing planned parameters are retained.
      workspaceLink.href =
        url.pathname + url.search + url.hash;
    }

    vial.addEventListener(
      'change',
      updateWorkspaceLink
    );

    updateWorkspaceLink();

    // Improve anchor navigation for keyboard users.
    const targets = [
      preview,
      context,
      details,
      submit
    ].filter(Boolean);

    for (const target of targets) {
      if (
        !target.hasAttribute('tabindex') &&
        target !== submit &&
        target !== when
      ) {
        target.setAttribute('tabindex', '-1');
      }
    }

    shortcuts.addEventListener(
      'click',
      event => {
        const link = event.target.closest(
          'a.tracker-workflow-shortcut'
        );

        if (!link) return;

        const id = link.hash.slice(1);

        const target = document.getElementById(id);

        if (!target) return;

        event.preventDefault();

        target.scrollIntoView({
          behavior: 'smooth',
          block: 'center'
        });

        if (target === details) {
          when.focus({
            preventScroll: true
          });
        } else {
          target.focus({
            preventScroll: true
          });
        }
      }
    );
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
