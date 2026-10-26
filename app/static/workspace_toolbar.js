/* Lightweight accessible workspace preferences popover. */
(() => {
  function init() {
    const root = document.getElementById('workspace-settings');
    const toggle = document.getElementById('workspace-settings-toggle');
    const panel = document.getElementById('workspace-settings-panel');
    const close = document.getElementById('workspace-settings-close');
    if (!root || !toggle || !panel) return;
    const setOpen = (open) => {
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      if (open) close?.focus();
    };
    toggle.addEventListener('click', () => setOpen(panel.hidden));
    close?.addEventListener('click', () => { setOpen(false); toggle.focus(); });
    document.addEventListener('pointerdown', (event) => {
      if (!panel.hidden && !root.contains(event.target)) setOpen(false);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !panel.hidden) { setOpen(false); toggle.focus(); }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
