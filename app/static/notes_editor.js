
(() => {
  'use strict';

  const root = document.getElementById('notes-editor');
  if (!root) return;

  const form = root.closest('form');
  const source = document.getElementById('notes-body');
  const sourceWrap = document.getElementById('notes-source-wrap');
  const visual = document.getElementById('notes-visual');
  const toolbar = document.getElementById('notes-toolbar');
  const visualButton = document.getElementById('notes-visual-mode');
  const sourceButton = document.getElementById('notes-source-mode');

  let mode = 'source';
  let dirty = false;

  function inline(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent.replace(/\u00a0/g, ' ');
    }

    if (node.nodeType !== Node.ELEMENT_NODE) return '';

    const tag = node.tagName.toLowerCase();

    if (tag === 'br') return '\n';

    const content = [...node.childNodes].map(inline).join('');

    if (tag === 'strong' || tag === 'b')
      return '**' + content + '**';

    if (tag === 'em' || tag === 'i')
      return '*' + content + '*';

    if (tag === 'code')
      return '`' + content + '`';

    if (tag === 'a') {
      const href = node.getAttribute('href') || '';

      // Preserve internal wiki links where possible.
      if (/^\/pages\/\d+$/.test(href))
        return '[[' + content + ']]';

      if (/^https?:\/\//i.test(href))
        return '[' + content + '](' + href + ')';

      return content;
    }

    return content;
  }

  function blocks(element) {
    const result = [];

    function visit(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        if (node.textContent.trim())
          result.push(node.textContent.trim());
        return;
      }

      if (node.nodeType !== Node.ELEMENT_NODE) return;

      const tag = node.tagName.toLowerCase();

      if (tag === 'ul' || tag === 'ol') {
        const items = [...node.children]
          .filter(child => child.tagName.toLowerCase() === 'li')
          .map((li, i) => {
            const prefix = tag === 'ul' ? '- ' : `${i + 1}. `;
            return prefix + inline(li).trim().replace(/\n/g, '\n  ');
          });

        result.push(items.join('\n'));
        return;
      }

      if (tag === 'h1' || tag === 'h2' || tag === 'h3') {
        result.push(
          '#'.repeat(Number(tag[1])) + ' ' + inline(node).trim()
        );
        return;
      }

      if (tag === 'blockquote') {
        result.push(
          inline(node).trim().split('\n')
            .map(line => '> ' + line).join('\n')
        );
        return;
      }

      if (tag === 'p' || tag === 'div') {
        const content = inline(node).trim();
        if (content) result.push(content);
        return;
      }

      if (tag === 'br') return;

      result.push(inline(node).trim());
    }

    [...element.childNodes].forEach(visit);

    return result.filter(Boolean).join('\n\n');
  }

  async function markdownToVisual() {
    const data = new FormData();
    data.append('body', source.value);

    const response = await fetch('/pages/preview', {
      method: 'POST',
      body: data,
      credentials: 'same-origin'
    });

    if (!response.ok) {
      throw new Error('Preview request failed');
    }

    // The existing server-side Markdown renderer supplies HTML.
    visual.innerHTML = await response.text();
  }

  function syncSource() {
    if (mode !== 'visual' || !dirty) return;

    source.value = blocks(visual);
    source.dispatchEvent(new Event('input', { bubbles: true }));
    dirty = false;
  }

  async function setMode(next) {
    if (next === mode) return;

    if (next === 'visual') {
      try {
        await markdownToVisual();
      } catch (error) {
        alert('Could not load visual editor. Markdown remains available.');
        return;
      }
    } else {
      syncSource();
    }

    mode = next;
    const isVisual = mode === 'visual';

    visual.hidden = !isVisual;
    toolbar.hidden = !isVisual;
    sourceWrap.hidden = isVisual;

    visualButton.setAttribute('aria-pressed', String(isVisual));
    sourceButton.setAttribute('aria-pressed', String(!isVisual));
  }

  visualButton.addEventListener('click', () => setMode('visual'));
  sourceButton.addEventListener('click', () => setMode('source'));

  visual.addEventListener('input', () => {
    dirty = true;
  });

  toolbar.addEventListener('click', event => {
    const button = event.target.closest('button[data-command]');
    if (!button) return;

    visual.focus();

    document.execCommand(
      button.dataset.command,
      false,
      button.dataset.value || null
    );

    dirty = true;
  });

  document.getElementById('notes-link').addEventListener('click', () => {
    visual.focus();

    const url = prompt('Link URL (https://...)');
    if (!url) return;

    if (!/^https?:\/\//i.test(url)) {
      alert('Links must begin with http:// or https://');
      return;
    }

    document.execCommand('createLink', false, url);
    dirty = true;
  });

  form.addEventListener('submit', () => {
    syncSource();
  });

  // Preserve the original Markdown unless the user edits visual content.
  // This prevents merely opening visual mode from rewriting an old note.

  // Prefer visual mode for new notes; preserve source mode for
  // existing notes so complex Markdown can be inspected first.
  if (!source.value.trim()) {
    setMode('visual');
  }

  // Tracker Notes integration API.
  // Read the visual editor without changing modes.
  window.trackerNotesEditor = {
    getBody() {
      return mode === 'visual' && dirty
        ? blocks(visual)
        : source.value;
    },

    async restore(value) {
      source.value = value;
      dirty = false;

      source.dispatchEvent(
        new Event('input', { bubbles: true })
      );

      if (mode === 'visual') {
        await markdownToVisual();
      }
    },

    getMode() {
      return mode;
    }
  };

})();
