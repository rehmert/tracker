/* TRACKER_CORE_97_104 — progressive, read-only workflow helpers */
(function () {
  'use strict';
  var routes = {
    '/protocols': [['/calendar','Calendar'],['/doses','Record dose'],['/protocol-tools','Protocol tools'],['/pk','PK simulator']],
    '/doses': [['/calendar','Calendar'],['/protocols','Protocols'],['/vials','Vials'],['/dose-workspace','Dose workspace']],
    '/dose-workspace': [['/doses','Dose log'],['/calendar','Calendar'],['/vials','Vials']],
    '/vials': [['/inventory-health','Inventory health'],['/inventory-alerts','Alerts'],['/purchases','Purchases'],['/reconciliation','Reconcile']],
    '/purchases': [['/purchase-analysis','Purchase analysis'],['/vials','Vials'],['/vendor-prices','Vendor prices']],
    '/inventory-health': [['/vials','Vials'],['/inventory-alerts','Alerts'],['/inventory-timeline','Timeline']],
    '/inventory-alerts': [['/vials','Vials'],['/purchases','Purchases'],['/inventory-health','Inventory health']],
    '/calendar': [['/doses','Record dose'],['/protocols','Protocols'],['/pk','PK simulator']]
  };
  var path = location.pathname.replace(/\/$/, '') || '/';
  var group = path.match(/^\/protocols\/\d+/) ? '/protocols'
    : path.match(/^\/vials\/\d+/) ? '/vials'
    : path.match(/^\/purchases\/\d+/) ? '/purchases' : path;
  var links = routes[group];
  if (!links) return;
  function enhance() {
    var main = document.getElementById('main-content');
    if (!main) return;
    var title = main.querySelector('h1');
    if (!title) return;
    if (!main.querySelector('[data-core-workflow="97-104"]')) {
      var nav = document.createElement('nav');
      nav.className = 'core-workflow-links';
      nav.dataset.coreWorkflow = '97-104';
      nav.setAttribute('aria-label','Related workflow pages');
      links.forEach(function (item) {
        var a = document.createElement('a');
        a.href = item[0]; a.textContent = item[1];
        nav.appendChild(a);
      });
      title.insertAdjacentElement('afterend', nav);
    }
    main.querySelectorAll('table').forEach(function (table) {
      if (table.dataset.coreWorkflowTable) return;
      table.dataset.coreWorkflowTable = '1';
      if (!table.tBodies.length || !table.tBodies[0].rows.length) return;
      var rows = Array.from(table.tBodies[0].rows);
      if (rows.length < 5 || table.closest('.tool-page')) return;
      // Only filter tables without interactive controls; never hide dose actions.
      if (table.querySelector('input, select, button, form')) return;
      var toolbar = document.createElement('div');
      toolbar.className = 'core-table-toolbar';
      var label = document.createElement('label');
      label.textContent = 'Find in table ';
      var search = document.createElement('input');
      search.type = 'search';
      search.setAttribute('aria-label', 'Find in table');
      label.appendChild(search);
      var count = document.createElement('span');
      count.setAttribute('role', 'status');
      function update() {
        var q = search.value.trim().toLocaleLowerCase();
        var visible = 0;
        rows.forEach(function (row) {
          var show = !q || row.textContent.toLocaleLowerCase().includes(q);
          row.hidden = !show;
          if (show) visible++;
        });
        count.textContent = visible + ' / ' + rows.length + ' rows';
      }
      search.addEventListener('input', update);
      toolbar.append(label, count);
      var holder = table.closest('.scroll') || table;
      holder.parentNode.insertBefore(toolbar, holder);
      update();
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', enhance);
  else enhance();
  document.body.addEventListener('htmx:afterSwap', enhance);
})();
