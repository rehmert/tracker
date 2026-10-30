(() => {
  'use strict';

  function initialize() {
    const panel = document.getElementById('dose-context');
    if (!panel) return;

    const form = panel.closest('form');
    if (!form) return;

    const vial = form.querySelector(
      'select[name="vial_id"]'
    );

    const compoundOutput = document.getElementById(
      'dose-context-compound'
    );

    const sitesOutput = document.getElementById(
      'dose-context-sites'
    );

    const suppliesOutput = document.getElementById(
      'dose-context-supplies'
    );

    if (
      !vial ||
      !compoundOutput ||
      !sitesOutput ||
      !suppliesOutput
    ) return;

    function update() {
      const option = vial.selectedOptions[0];

      const compoundId = option?.dataset.compoundId || '';
      const compoundName = option?.dataset.compoundName || '';

      compoundOutput.textContent =
        compoundName || 'No compound selected';

      // History rows are already sorted newest first.
      // Exclude waste/discard entries and missing sites.
      const recentSites = [];

      document.querySelectorAll(
        '#dose-body tr[data-dose-compound]'
      ).forEach(row => {
        if (
          row.dataset.doseCompound !== compoundId ||
          row.dataset.doseKind !== 'dose'
        ) return;

        const site = (row.dataset.doseSite || '').trim();

        if (site && recentSites.length < 5) {
          recentSites.push(site);
        }
      });

      sitesOutput.textContent = recentSites.length
        ? recentSites.join(' · ')
        : 'No recent injection sites in displayed history';

      const selected = [];

      form.querySelectorAll(
        'input[name="supply_id_used"]:checked'
      ).forEach(checkbox => {
        const row = checkbox.closest('tr');
        if (!row) return;

        const cells = row.querySelectorAll('td');
        const name = cells[1]?.textContent.trim() || 'Supply';

        const quantity = row.querySelector(
          'input[name^="supply_qty_"]'
        )?.value || '1';

        selected.push(`${name} × ${quantity}`);
      });

      suppliesOutput.textContent = selected.length
        ? selected.join(' · ')
        : 'None selected';
    }

    form.addEventListener('change', update);
    form.addEventListener('input', event => {
      if (event.target.matches(
        'input[name^="supply_qty_"]'
      )) update();
    });

    // The history table can be refreshed by HTMX.
    document.body.addEventListener(
      'htmx:afterSwap',
      event => {
        if (
          event.detail.target?.id === 'dose-body'
        ) update();
      }
    );

    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initialize
    );
  } else {
    initialize();
  }
})();
