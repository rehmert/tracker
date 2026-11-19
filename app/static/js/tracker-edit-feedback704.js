/* Release 704: read-only enhancement of native form validation feedback.
 * No fetch/storage, interception of submit, changes to form fields, or redirects.
 * The browser and existing server still own whether each save is valid.
 */
(() => {
  'use strict';

  function initialize() {
    document.querySelectorAll('#main-content .tracker-edit-actions704')
      .forEach(actions => {
        const form = actions.closest('form');
        const feedback = form?.querySelector('.tracker-edit-feedback704');
        if (!form || !feedback || form.dataset.trackerEditFeedback704) return;
        form.dataset.trackerEditFeedback704 = 'ready';

        const invalidInputs = () => Array.from(form.elements).filter(
          control => control.willValidate && !control.validity.valid
        );

        form.addEventListener('invalid', () => {
          const count = invalidInputs().length;
          feedback.textContent = count === 1
            ? 'Review the highlighted field before saving.'
            : 'Review the highlighted fields before saving.';
          feedback.hidden = false;
        }, true);

        const update = () => {
          if (feedback.hidden || invalidInputs().length) return;
          feedback.textContent = '';
          feedback.hidden = true;
        };
        form.addEventListener('input', update);
        form.addEventListener('change', update);
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once: true});
  } else {
    initialize();
  }
})();
