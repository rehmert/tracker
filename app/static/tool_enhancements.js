// TRACKER_TOOLS_89_96
(function () {
  'use strict';
  function init() {
    document.querySelectorAll('.tool-page').forEach(function (page) {
      if (page.dataset.enhanced === 'yes') return;
      page.dataset.enhanced = 'yes';
      var body = page.querySelector('.tool-page-body');
      if (!body) return;
      var tables = Array.from(body.querySelectorAll('table'));
      var header = page.querySelector('.tool-page-header');
      if (header && !header.querySelector('.tool-shortcuts')) {
        var nav = document.createElement('nav');
        nav.className = 'tool-shortcuts';
        nav.setAttribute('aria-label', 'Related tools');
        [['/protocol-tools','Protocols'], ['/purchase-analysis','Purchasing'],
         ['/record-explorer/vials','Vials'], ['/record-explorer/notes','Notes'],
         ['/record-explorer/health','Health'], ['/record-explorer/database','Database'],
         ['/maintenance-review','Maintenance']].forEach(function (item) {
          var a = document.createElement('a');
          a.href = item[0]; a.textContent = item[1];
          if (location.pathname === item[0]) a.setAttribute('aria-current','page');
          nav.appendChild(a);
        });
        header.appendChild(nav);
      }
      tables.forEach(function (table, index) {
        if (table.dataset.toolEnhanced === 'yes') return;
        table.dataset.toolEnhanced = 'yes';
        var tbody = table.tBodies[0];
        if (!tbody) return;
        var rows = Array.from(tbody.rows);
        var wrapper = document.createElement('div');
        wrapper.className = 'tool-table-controls';
        var label = document.createElement('label');
        label.textContent = 'Filter table ' + (index + 1) + ' ';
        var input = document.createElement('input');
        input.type = 'search'; input.placeholder = 'Search visible rows';
        input.setAttribute('aria-label', 'Filter table ' + (index + 1));
        label.appendChild(input);
        var count = document.createElement('span');
        count.className = 'tool-row-count'; count.setAttribute('role','status');
        var exportButton = document.createElement('button');
        exportButton.type = 'button'; exportButton.textContent = 'Export CSV';
        function visibleRows() { return rows.filter(function (row) { return !row.hidden; }); }
        function refresh() {
          var query = input.value.trim().toLocaleLowerCase();
          rows.forEach(function (row) {
            row.hidden = !!query && !row.textContent.toLocaleLowerCase().includes(query);
          });
          var visible = visibleRows().length;
          count.textContent = visible + ' of ' + rows.length + ' rows';
          exportButton.disabled = visible === 0;
        }
        input.addEventListener('input', refresh);
        function csvCell(text) { return '"' + String(text).replace(/"/g, '""') + '"'; }
        exportButton.addEventListener('click', function () {
          var headings = table.tHead && table.tHead.rows.length
            ? Array.from(table.tHead.rows[table.tHead.rows.length - 1].cells).map(function (c) { return c.textContent.trim(); })
            : [];
          var lines = [];
          if (headings.length) lines.push(headings.map(csvCell).join(','));
          visibleRows().forEach(function (row) {
            lines.push(Array.from(row.cells).map(function (c) { return csvCell(c.textContent.trim()); }).join(','));
          });
          var blob = new Blob(['\uFEFF' + lines.join('\r\n') + '\r\n'], {type:'text/csv;charset=utf-8'});
          var url = URL.createObjectURL(blob);
          var a = document.createElement('a'); a.href = url;
          a.download = 'tracker-table-' + (index + 1) + '.csv';
          document.body.appendChild(a); a.click(); a.remove();
          setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
        });
        wrapper.append(label, count, exportButton);
        var holder = table.closest('.scroll') || table;
        holder.parentNode.insertBefore(wrapper, holder);
        if (!rows.length) {
          var empty = document.createElement('p');
          empty.className = 'tool-empty';
          empty.textContent = 'No records in this table.';
          holder.parentNode.insertBefore(empty, holder.nextSibling);
        }
        refresh();
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  document.body.addEventListener('htmx:afterSwap', init);
})();
