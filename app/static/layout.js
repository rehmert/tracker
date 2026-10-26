/* Stage 2 navigation and client-side table filtering. No dependencies or server calls. */
(() => {
  const KEY = 'tracker-sidebar-collapsed';
  const read = () => { try { return localStorage.getItem(KEY) === '1'; } catch (_) { return false; } };
  const write = value => { try { localStorage.setItem(KEY, value ? '1' : '0'); } catch (_) {} };
  function init() {
    const shell = document.getElementById('app-shell');
    const toggle = document.getElementById('sidebar-collapse');
    const open = document.getElementById('sidebar-open');
    if (!shell) return;
    const setCollapsed = collapsed => {
      shell.classList.toggle('sidebar-collapsed', collapsed);
      toggle?.setAttribute('aria-expanded', String(!collapsed));
      if (toggle) { toggle.textContent = collapsed ? '›' : '‹'; toggle.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar'; }
      write(collapsed);
    };
    setCollapsed(read());
    toggle?.addEventListener('click', () => setCollapsed(!shell.classList.contains('sidebar-collapsed')));
    const closeMobile = () => { shell.classList.remove('sidebar-mobile-open'); open?.setAttribute('aria-expanded', 'false'); };
    open?.addEventListener('click', () => { const visible = shell.classList.toggle('sidebar-mobile-open'); open.setAttribute('aria-expanded', String(visible)); });
    document.querySelector('[data-close-sidebar]')?.addEventListener('click', closeMobile);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMobile(); });
    document.querySelectorAll('.rail a').forEach(a => a.addEventListener('click', closeMobile));
    document.querySelectorAll('[data-filter-target]').forEach(input => {
      const target = document.getElementById(input.dataset.filterTarget);
      if (!target) return;
      input.addEventListener('input', () => {
        const query = input.value.trim().toLocaleLowerCase();
        const rows = target.id === 'inventory-rows' ? target.querySelectorAll('tr') : target.querySelectorAll('.protocol-card');
        rows.forEach(row => { row.hidden = !((row.dataset.search || row.textContent).toLocaleLowerCase().includes(query)); });
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
