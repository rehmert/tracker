(() => {
  const details = document.getElementById('supply-product-details');
  let products = [];
  try { products = details ? JSON.parse(details.textContent) : []; } catch (_) {}
  const money = n => Number.isFinite(n) ? new Intl.NumberFormat(undefined,{style:'currency',currency:'USD'}).format(n) : '—';
  document.querySelectorAll('[data-bulk-ux]').forEach(form => {
    const field = name => form.elements.namedItem(name);
    const mode = form.querySelector('[data-mode]');
    const packFields = form.querySelector('[data-pack-fields]');
    const unitFields = form.querySelector('[data-individual-fields]');
    const summary = form.querySelector('[data-summary]');
    const picker = form.querySelector('[data-product-picker]');
    function refresh() {
      const bulk = mode.value === 'bulk';
      packFields.hidden = !bulk;
      unitFields.hidden = bulk;
      packFields.querySelectorAll('input').forEach(el => {el.disabled = !bulk;});
      unitFields.querySelectorAll('input').forEach(el => {el.disabled = bulk;});
      const count = Number(field('pack_count')?.value || 0);
      const per = Number(field('units_per_pack')?.value || 0);
      const units = bulk ? count * per : Number(field('quantity')?.value || 0);
      const price = bulk ? Number(field('package_price')?.value || 0) : units * Number(field('unit_price')?.value || 0);
      summary.textContent = units > 0 ? `${Number(units.toFixed(4)).toLocaleString()} individual units added · ${money(price)} line total · ${money(price/units)} per unit` : 'Enter package quantities to preview inventory and costs.';
    }
    picker?.addEventListener('change', () => {
      if (picker.value === '') return;
      const product = products[Number(picker.value)];
      if (!product) return;
      field('name').value = product.name;
      field('kind').value = product.kind;
      if (field('units_per_pack')) field('units_per_pack').value = product.units || 1;
      if (field('package_price')) field('package_price').value = (product.price / 100).toFixed(2);
      if (field('package_type')) field('package_type').value = product.package_type || 'box';
      mode.value = 'bulk'; refresh();
    });
    form.addEventListener('input', refresh);
    form.addEventListener('change', refresh);
    form.addEventListener('submit', e => {
      refresh();
      const bulk = mode.value === 'bulk';
      if (bulk && (!(Number(field('pack_count').value) > 0) || !(Number(field('units_per_pack').value) > 0))) {
        e.preventDefault(); alert('Enter a valid number of packages and items per package.');
      }
    });
    refresh();
  });
})();
