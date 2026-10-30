(() => {
  const input = document.getElementById('inventory-filter');
  const rows = [...document.querySelectorAll('.inventory-main-row')];
  document.querySelectorAll('.inventory-expand').forEach(button => {
    button.addEventListener('click', () => {
      const detail = document.getElementById(button.getAttribute('aria-controls'));
      if (!detail) return;
      detail.hidden = !detail.hidden;
      button.setAttribute('aria-expanded', String(!detail.hidden));
      button.textContent = detail.hidden ? '＋' : '−';
    });
  });
  if (!input) return;
  const filterKey = 'tracker.inventory.filter.v1';
  try { input.value = sessionStorage.getItem(filterKey) || ''; } catch (_) {}
  function applyFilter() {
    const query = input.value.trim().toLocaleLowerCase();
    try { sessionStorage.setItem(filterKey, input.value); } catch (_) {}
    let visible = 0;
    rows.forEach(row => {
      const match = (row.dataset.search || '').includes(query);
      row.hidden = !match;
      const detail = document.getElementById(row.querySelector('.inventory-expand').getAttribute('aria-controls'));
      if (detail) detail.hidden = !match || row.querySelector('.inventory-expand').getAttribute('aria-expanded') !== 'true';
      if (match) visible++;
    });
    document.getElementById('inventory-empty').hidden = visible !== 0;
  }
  input.addEventListener('input', applyFilter);
  applyFilter();
})();
