/* Release 603: links directly to existing vial sections.
 * Expansion is navigation only; selection and inventory remain untouched.
 */
(() => {
  'use strict';

  function init() {
    const nav = document.querySelector('.tracker-vial-jumps603');
    if (!nav) return;

    nav.querySelectorAll('a[href^="#"]').forEach(link => {
      link.addEventListener('click', () => {
        const id = link.getAttribute('href').slice(1);
        const target = document.getElementById(id);
        if (!target) return;
        // Opening a hidden report is a prerequisite for useful navigation.
        let element = target;
        while (element && element !== document.body) {
          if (element.tagName === 'DETAILS') element.open = true;
          element = element.parentElement;
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else {
    init();
  }
})();
