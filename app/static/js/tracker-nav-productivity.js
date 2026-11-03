/* Browser-only navigation productivity; never saves record details. */
(() => {
  'use strict';
  const KEY = 'tracker.navigation.recent-pages.v1';
  const LIMIT = 8;
  const el = id => document.getElementById(id);
  function read() {
    try {
      const value = JSON.parse(localStorage.getItem(KEY) || '[]');
      return Array.isArray(value) ? value.filter(x => typeof x === 'string') : [];
    } catch (_) { return []; }
  }
  function store(value) {
    try { localStorage.setItem(KEY, JSON.stringify(value)); } catch (_) {}
  }
  function boot() {
    const menu = el('tracker-recent-pages');
    const list = el('tracker-recent-list');
    const status = el('tracker-recent-status');
    const input = el('nav-filter');
    const rail = el('app-sidebar');
    if (!menu || !list || !status || !input || !rail) return;
    const sections = [...rail.querySelectorAll('#nav-sortable .nav-section')];
    const pages = sections.flatMap(section => {
      const category = section.querySelector('.nav-section-toggle span')
        ?.textContent.trim() || section.dataset.section;
      return [...section.querySelectorAll('li[data-nav-key]')].map(item => ({
        href: item.dataset.navKey,
        label: item.querySelector('.nav-text')?.textContent.trim() || item.dataset.navKey,
        section, category, item
      }));
    });
    pages.unshift({
      href: '/', label: 'Dashboard', category: 'Overview',
      section: null, item: rail.querySelector('.nav-pinned [data-nav-key]')
    });
    const byPath = new Map(pages.map(p => [p.href, p]));
    const pathname = window.location.pathname;
    const current = byPath.get(pathname) || pages
      .filter(p => p.href !== '/' && pathname.startsWith(p.href + '/'))
      .sort((a,b) => b.href.length - a.href.length)[0] || null;
    let recent = [...new Set(read())].filter(p => byPath.has(p)).slice(0, LIMIT);
    if (current) {
      recent = [current.href, ...recent.filter(p => p !== current.href)].slice(0, LIMIT);
      store(recent);
    }
    el('tracker-current-location').textContent = current
      ? 'Current: ' + current.category + ' › ' + current.label
      : 'This URL is not a main navigation destination.';
    function draw() {
      list.replaceChildren();
      if (!recent.length) {
        const empty = document.createElement('li');
        empty.textContent = 'No recent navigation destinations.';
        list.append(empty);
        return;
      }
      for (const path of recent) {
        const page = byPath.get(path);
        if (!page) continue;
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = page.href;
        a.textContent = page.label;
        const category = document.createElement('small');
        category.textContent = page.category;
        li.append(a, category);
        const original = page.item?.querySelector('.nav-star');
        if (original) {
          const star = document.createElement('button');
          star.type = 'button';
          star.title = 'Toggle favorite';
          star.setAttribute('aria-label', 'Toggle favorite for ' + page.label);
          const sync = () => {
            star.textContent = original.getAttribute('aria-pressed') === 'true' ? '★' : '☆';
          };
          star.addEventListener('click', () => {
            original.click();
            sync();
            status.textContent = page.label + ' favorite updated.';
          });
          sync();
          li.append(star);
        }
        list.append(li);
      }
    }
    draw();
    menu.addEventListener('toggle', () => { if (menu.open) draw(); });
    document.addEventListener('pointerdown', e => {
      if (menu.open && !menu.contains(e.target)) menu.open = false;
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && menu.open) menu.open = false;
      if (e.key !== '/' || e.altKey || e.ctrlKey || e.metaKey || e.repeat) return;
      const active = document.activeElement;
      if (active?.isContentEditable || active?.closest('input,textarea,select,[role="textbox"]')) return;
      e.preventDefault();
      input.focus();
      input.select();
    });
    input.addEventListener('keydown', e => {
      if (e.key !== 'Escape') return;
      input.value = '';
      input.dispatchEvent(new Event('input', {bubbles:true}));
    });
    function setAll(open) {
      sections.forEach(section => {
        const toggle = section.querySelector('.nav-section-toggle');
        if (toggle && (toggle.getAttribute('aria-expanded') === 'true') !== open) toggle.click();
      });
    }
    el('tracker-expand-nav')?.addEventListener('click', () => setAll(true));
    el('tracker-collapse-nav')?.addEventListener('click', () => setAll(false));
    el('tracker-find-current')?.addEventListener('click', () => {
      const link = current?.item?.querySelector('a');
      if (!link) {
        status.textContent = 'No matching navigation destination.';
        return;
      }
      const shell = el('app-shell');
      if (window.matchMedia('(max-width: 760px)').matches) {
        if (!shell.classList.contains('sidebar-mobile-open')) el('sidebar-open')?.click();
      } else if (shell.classList.contains('sidebar-collapsed')) {
        el('sidebar-collapse')?.click();
      }
      const toggle = current.section?.querySelector('.nav-section-toggle');
      if (toggle?.getAttribute('aria-expanded') !== 'true') toggle?.click();
      if (current.item.hidden || current.item.classList.contains('tracker-focus-hidden')) {
        status.textContent = 'The link is hidden in Preferences. Reveal it there first.';
        return;
      }
      menu.open = false;
      link.scrollIntoView({block:'center'});
      link.focus({preventScroll:true});
    });
    el('tracker-clear-recent')?.addEventListener('click', () => {
      recent = [];
      store(recent);
      draw();
      status.textContent = 'Recent shortcuts cleared in this browser.';
    });
    el('tracker-copy-link')?.addEventListener('click', async () => {
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(window.location.href);
        } else {
          const area = document.createElement('textarea');
          area.value = window.location.href;
          area.style.position = 'fixed';
          area.style.opacity = '0';
          document.body.append(area);
          area.select();
          const copied = document.execCommand('copy');
          area.remove();
          if (!copied) throw Error('Copy unsupported');
        }
        status.textContent = 'Link copied.';
      } catch (_) {
        status.textContent = 'Copy is unavailable in this browser.';
      }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
