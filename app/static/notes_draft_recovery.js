
(() => {
  'use strict';

  const form = document.querySelector(
    'form[action^="/pages"]'
  );

  const body = document.querySelector(
    'textarea[name="body"]'
  );

  if (!form || !body) return;

  const title = form.querySelector('[name="title"]');
  const tags = form.querySelector('[name="tags"]');
  const visual = document.getElementById('notes-visual');

  const key = (
    'tracker:notes:draft:v2:' +
    location.pathname
  );

  // Preserve the previously used key for migration.
  const oldKey = (
    'tracker:notes:draft:' +
    location.pathname
  );

  const currentBody = () => {
    return window.trackerNotesEditor?.getBody()
      ?? body.value;
  };

  const snapshot = () => ({
    title: title?.value || '',
    tags: tags?.value || '',
    body: currentBody(),
    updated: Date.now()
  });

  const initial = snapshot();
  let timer = null;
  let submitted = false;

  function differs(a, b) {
    return (
      a.title !== b.title ||
      a.tags !== b.tags ||
      a.body !== b.body
    );
  }

  function storeDraft() {
    if (submitted) return;

    try {
      const draft = snapshot();

      if (!differs(draft, initial)) {
        localStorage.removeItem(key);
        return;
      }

      localStorage.setItem(
        key,
        JSON.stringify(draft)
      );
    } catch (error) {
      console.warn(
        'Unable to save Notes draft.',
        error
      );
    }
  }

  function scheduleSave() {
    clearTimeout(timer);

    timer = setTimeout(
      storeDraft,
      700
    );
  }

  [title, tags, body, visual].forEach(field => {
    field?.addEventListener(
      'input',
      scheduleSave
    );
  });

  function parseDraft(value) {
    if (!value) return null;

    try {
      const draft = JSON.parse(value);

      if (
        typeof draft.title !== 'string' ||
        typeof draft.tags !== 'string' ||
        typeof draft.body !== 'string'
      ) {
        return null;
      }

      return draft;
    } catch {
      return null;
    }
  }

  async function restoreDraft(draft) {
    if (title) title.value = draft.title;
    if (tags) tags.value = draft.tags;

    if (window.trackerNotesEditor) {
      await window.trackerNotesEditor.restore(
        draft.body
      );
    } else {
      body.value = draft.body;
      body.dispatchEvent(
        new Event('input', { bubbles: true })
      );
    }
  }

  async function initialize() {
    let draft = null;

    try {
      draft = parseDraft(
        localStorage.getItem(key)
      );

      if (!draft) {
        draft = parseDraft(
          localStorage.getItem(oldKey)
        );
      }
    } catch {
      return;
    }

    if (!draft) return;

    if (!differs(draft, initial)) {
      localStorage.removeItem(key);
      localStorage.removeItem(oldKey);
      return;
    }

    const restore = confirm(
      'An unsaved draft of this note was found.\n\n' +
      'Select OK to restore it, or Cancel to keep ' +
      'the currently saved page.'
    );

    if (restore) {
      await restoreDraft(draft);
      storeDraft();
    } else {
      localStorage.removeItem(key);
      localStorage.removeItem(oldKey);
    }
  }

  // A draft can be discarded explicitly.
  const discard = document.getElementById(
    'notes-discard-draft'
  );

  discard?.addEventListener('click', () => {
    if (!confirm(
      'Discard the locally saved draft for this note?'
    )) {
      return;
    }

    localStorage.removeItem(key);
    localStorage.removeItem(oldKey);

    alert(
      'Local draft discarded. ' +
      'The current editor contents have not changed.'
    );
  });

  // Preserve drafts when submitting.
  // A failed server-side validation must not lose work.
  form.addEventListener('submit', () => {
    clearTimeout(timer);
    storeDraft();
    submitted = true;
  });

  window.addEventListener('pagehide', () => {
    if (!submitted) {
      clearTimeout(timer);
      storeDraft();
    }
  });

  initialize();
})();
