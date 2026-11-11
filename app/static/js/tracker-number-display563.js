/* Release 563: presentation-only numeric formatting, never mutate inputs or data.
 * Keeps user-facing calculated values at <=3 decimal places, including
 * scientific-notation strings produced by older pages.
 */
(() => {
  'use strict';

  const formatter = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 3,
    minimumFractionDigits: 0,
    useGrouping: false,
    notation: 'standard'
  });

  function format(value) {
    const number = Number(String(value).replace(/,/g, ''));
    if (!Number.isFinite(number)) return '—';
    if (number === 0) return '0';
    if (number > 0 && number < 0.0005) return '<0.001';
    if (number < 0 && number > -0.0005) return '>-0.001';
    return formatter.format(number).replace(/^-0$/, '0');
  }

  window.TrackerNumber563 = Object.freeze({ format });

  const exclude = 'script,style,noscript,template,pre,code,textarea,input,[contenteditable],[data-preserve-numbers]';
  // The exponent expression and >=4-decimal expression only affect
  // complete numeric tokens, not identifiers, filenames, URLs or versions.
  const token = /(?<![\w.\/-])[-+]?\d[\d,]*(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])/g;

  function replaceVisible(text) {
    return text.replace(token, value => {
      if (!/[eE][+-]?\d+$/.test(value) && !/\.\d{4,}/.test(value)) return value;
      return format(value);
    });
  }

  function fixText(node) {
    if (!node?.parentElement || node.parentElement.closest(exclude)) return;
    const updated = replaceVisible(node.nodeValue);
    if (updated !== node.nodeValue) node.nodeValue = updated;
  }

  function scan(node) {
    if (!node || node.nodeType === Node.COMMENT_NODE) return;
    if (node.nodeType === Node.TEXT_NODE) { fixText(node); return; }
    if (node.nodeType !== Node.ELEMENT_NODE || node.closest(exclude)) return;
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) fixText(walker.currentNode);
  }

  function start() {
    scan(document.body);
    let queued = false;
    const pending = new Set();
    const flush = () => {
      queued = false;
      const list = [...pending];
      pending.clear();
      list.forEach(scan);
    };
    const observer = new MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'characterData') pending.add(record.target);
        for (const child of record.addedNodes || []) pending.add(child);
      }
      if (pending.size && !queued) {
        queued = true;
        queueMicrotask(flush);
      }
    });
    observer.observe(document.body, { childList: true, characterData: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
