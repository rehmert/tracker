/* Release 598: truncate only explanatory section copy that genuinely wraps.
 * Full original markup remains in place and is toggled without network calls.
 */
(() => {
  'use strict';
  const SELECTOR = [
    'main section > p.note',
    'main section > p.section-description',
    'main section > p.tracker-attention-note',
    'main section > header p',
    'main section > .section-intro p',
    'main section > .panel-heading p'
  ].join(', ');

  function init() {
    const entries = [];
    for (const paragraph of document.querySelectorAll(SELECTOR)) {
      if (paragraph.dataset.explanation598 || paragraph.closest('[role="alert"]')) continue;
      paragraph.dataset.explanation598 = '1';
      const content = document.createElement('span');
      content.className = 'tracker-explanation598-text';
      content.id = 'tracker-explanation598-' + (entries.length + 1);
      while (paragraph.firstChild) content.appendChild(paragraph.firstChild);
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'tracker-explanation598-toggle';
      toggle.textContent = 'More';
      toggle.setAttribute('aria-controls', content.id);
      toggle.setAttribute('aria-expanded', 'false');
      toggle.hidden = true;
      paragraph.classList.add('tracker-explanation598');
      paragraph.append(content, toggle);
      const entry = {paragraph, content, toggle, expanded: false};
      toggle.addEventListener('click', () => {
        entry.expanded = !entry.expanded;
        paragraph.classList.toggle('tracker-explanation598-open', entry.expanded);
        toggle.textContent = entry.expanded ? 'Less' : 'More';
        toggle.setAttribute('aria-expanded', String(entry.expanded));
      });
      entries.push(entry);
    }

    function update() {
      for (const entry of entries) {
        if (entry.expanded || !entry.paragraph.getClientRects().length) continue;
        // Measure before showing the control so the control itself cannot
        // make a genuinely single-line explanation look multi-line.
        entry.toggle.hidden = true;
        entry.toggle.hidden = entry.content.scrollHeight <= entry.content.clientHeight + 1;
      }
    }

    requestAnimationFrame(update);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => requestAnimationFrame(update));
    }
    let pending = false;
    window.addEventListener('resize', () => {
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => { pending = false; update(); });
    });
    // Dashboard customization can reveal sections hidden during initial layout.
    document.addEventListener('click', event => {
      if (event.target.closest('#dashboard-customize-panel')) {
        requestAnimationFrame(update);
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else {
    init();
  }
})();
