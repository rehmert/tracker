/* Purchases: read-only review. Values are rendered by the server. */
(() => {
  'use strict';

  function initialize() {
    const table = document.querySelector('[data-purchase-history]');
    const toolbar = document.querySelector('[data-purchase-review-toolbar]');
    if (!table || !toolbar || table.dataset.purchaseReady) return;

    const search = toolbar.querySelector('[data-purchase-search]');
    const vendor = toolbar.querySelector('[data-purchase-vendor]');
    const status = toolbar.querySelector('[data-purchase-status]');
    const from = toolbar.querySelector('[data-purchase-from]');
    const through = toolbar.querySelector('[data-purchase-through]');
    const reset = toolbar.querySelector('[data-purchase-reset]');
    const exportButton = toolbar.querySelector('[data-purchase-export]');
    const count = document.querySelector('[data-purchase-visible-count]');
    const needsCount = document.querySelector('[data-purchase-needs-count]');
    const total = document.querySelector('[data-purchase-visible-total]');
    const results = document.querySelector('[data-purchase-results]');
    const empty = document.querySelector('[data-purchase-empty]');
    const dateError = document.querySelector('[data-purchase-date-error]');
    if (![search, vendor, status, from, through, reset, exportButton,
          count, needsCount, total, results, empty, dateError].every(Boolean)) return;

    const body = table.tBodies[0];
    if (!body) return;
    const rows = [...body.querySelectorAll('[data-purchase-row]')];
    const original = new Map(rows.map((row, i) => [row, i]));
    // Server-rendered purchase identity fields never change on this page.
    // Index once instead of normalizing them again on every keystroke.
    const searchableByRow = new Map(rows.map(row => [
      row,
      [row.dataset.purchaseDate, row.dataset.purchaseVendor,
       row.dataset.purchaseOrder, row.dataset.purchaseId]
        .join(' ').toLocaleLowerCase()
    ]));
    const collator = new Intl.Collator(undefined,
      {numeric:true, sensitivity:'base'});
    const currency = table.dataset.currency || '';
    const sortState = {key: 'date', direction: 'desc'};

    const vendorLabels = new Map();
    for (const row of rows) {
      const label = row.dataset.purchaseVendor.trim();
      const key = label.toLocaleLowerCase();
      if (!vendorLabels.has(key)) vendorLabels.set(key, label);
    }
    for (const [key, label] of [...vendorLabels]
      .sort((a, b) => collator.compare(a[1], b[1]))) {
      const option = document.createElement('option');
      option.value = key;
      option.textContent = label;
      vendor.appendChild(option);
    }

    function cents(row) {
      const value = Number(row.dataset.purchaseTotalCents);
      return Number.isFinite(value) ? value : 0;
    }

    function formatCents(value) {
      const sign = value < 0 ? '-' : '';
      const amount = (Math.abs(value) / 100).toLocaleString(undefined,
        {minimumFractionDigits:2, maximumFractionDigits:2});
      return sign + currency + amount;
    }

    function compare(a, b) {
      const key = sortState.key;
      let result = 0;
      if (key === 'date') {
        result = a.dataset.purchaseDate.localeCompare(b.dataset.purchaseDate);
      } else if (key === 'vendor') {
        result = collator.compare(a.dataset.purchaseVendor, b.dataset.purchaseVendor);
      } else if (key === 'order') {
        result = collator.compare(a.dataset.purchaseOrder, b.dataset.purchaseOrder);
      } else if (key === 'vials' || key === 'supplies') {
        const attr = key === 'vials' ? 'purchaseVials' : 'purchaseSupplies';
        result = Number(a.dataset[attr]) - Number(b.dataset[attr]);
      } else if (key === 'total') {
        result = cents(a) - cents(b);
      }
      const signed = sortState.direction === 'asc' ? result : -result;
      return signed || original.get(a) - original.get(b);
    }

    const headers = [...table.querySelectorAll('thead th[data-purchase-sort]')];
    function updateSortState() {
      for (const th of headers) {
        if (th.dataset.purchaseSort === sortState.key) {
          th.setAttribute('aria-sort',
            sortState.direction === 'asc' ? 'ascending' : 'descending');
        } else {
          th.removeAttribute('aria-sort');
        }
      }
    }

    for (const th of headers) {
      const key = th.dataset.purchaseSort;
      const label = th.textContent.trim();
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'purchase-sort-button';
      button.textContent = label;
      button.title = 'Sort purchases by ' + label;
      th.replaceChildren(button);
      button.addEventListener('click', () => {
        if (sortState.key === key) {
          sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc';
        } else {
          sortState.key = key;
          sortState.direction = key === 'date' ? 'desc' : 'asc';
        }
        update();
      });
    }

    function visibleRows() {
      return rows.filter(row => !row.hidden);
    }

    function update() {
      const text = search.value.trim().toLocaleLowerCase();
      const selectedVendor = vendor.value;
      const selectedStatus = status.value;
      const invalidDate = Boolean(from.value && through.value &&
        from.value > through.value);
      dateError.hidden = !invalidDate;

      let shown = 0;
      let pending = 0;
      let sumCents = 0;

      for (const row of [...rows].sort(compare)) {
        const d = row.dataset;
        const searchable = searchableByRow.get(row);
        const match = !invalidDate &&
          (!text || searchable.includes(text)) &&
          (!selectedVendor || d.purchaseVendor.trim().toLocaleLowerCase() === selectedVendor) &&
          (selectedStatus === 'all' || d.purchaseStatus === selectedStatus) &&
          (!from.value || d.purchaseDate >= from.value) &&
          (!through.value || d.purchaseDate <= through.value);
        row.hidden = !match;
        row.style.display = match ? '' : 'none';
        if (match) {
          shown++;
          if (d.purchaseStatus === 'needs-items') pending++;
          sumCents += cents(row);
        }
        body.appendChild(row);
      }

      count.textContent = String(shown);
      needsCount.textContent = String(pending);
      total.textContent = formatCents(sumCents);
      results.textContent = 'Showing ' + shown + ' of ' + rows.length + ' purchases.';
      empty.hidden = shown !== 0 || rows.length === 0;
      exportButton.disabled = shown === 0;
      reset.disabled = !text && !selectedVendor && selectedStatus === 'all' &&
        !from.value && !through.value &&
        sortState.key === 'date' && sortState.direction === 'desc';
      updateSortState();
    }

    function csvCell(value, numeric = false) {
      const originalText = String(value ?? '');
      const safeNumeric = numeric && /^-?\d+(?:\.\d+)?$/.test(originalText);
      const formulaLike = /^[\s\u0000-\u001f]*[=+\-@]/.test(originalText) ||
        /^[\t\r\n]/.test(originalText);
      const safe = formulaLike && !safeNumeric ? "'" + originalText : originalText;
      return '"' + safe.replaceAll('"', '""') + '"';
    }

    function exportCsv() {
      const visible = visibleRows();
      if (!visible.length) return;
      const header = ['Purchase ID', 'Date', 'Vendor', 'Order reference',
        'Vials', 'Supplies / pills', 'Allocated total (' + currency + ')',
        'Inventory status'];
      const values = visible.map(row => {
        const d = row.dataset;
        return [
          d.purchaseId, d.purchaseDate, d.purchaseVendor,
          d.purchaseOrder, d.purchaseVials, d.purchaseSupplies,
          (cents(row) / 100).toFixed(2),
          d.purchaseStatus === 'needs-items' ? 'Needs items' : 'Items recorded'
        ];
      });
      const csv = '\uFEFF' + [header, ...values].map((entry, n) =>
        entry.map((value, i) =>
          csvCell(value, n > 0 && [0, 4, 5, 6].includes(i))
        ).join(',')
      ).join('\r\n') + '\r\n';
      const blob = new Blob([csv], {type:'text/csv;charset=utf-8'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'tracker-purchase-history-filtered.csv';
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    search.addEventListener('input', update);
    vendor.addEventListener('change', update);
    status.addEventListener('change', update);
    from.addEventListener('change', update);
    through.addEventListener('change', update);
    reset.addEventListener('click', () => {
      search.value = '';
      vendor.value = '';
      status.value = 'all';
      from.value = '';
      through.value = '';
      sortState.key = 'date';
      sortState.direction = 'desc';
      update();
      search.focus();
    });
    exportButton.addEventListener('click', exportCsv);

    table.dataset.purchaseReady = '1';
    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once:true});
  } else {
    initialize();
  }
})();
