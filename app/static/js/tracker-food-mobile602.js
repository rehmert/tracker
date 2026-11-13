/* Release 602: surface existing reusable foods on phones without modifying
 * food records, forms, redirects, or journal state.
 */
(() => {
  'use strict';
  function init() {
    const quick = document.getElementById('food-quick-log');
    if (!quick || !window.matchMedia('(max-width: 760px)').matches) return;

    // Leave deliberate deep links and saved-food searches intact.
    const fragment = location.hash;
    const query = new URLSearchParams(location.search);
    if (!fragment || fragment === '#food-quick-log') {
      if (!query.has('q')) quick.open = true;
    }

    const actions = document.querySelector('.food-mobile-actions602');
    if (!actions) return;
    actions.querySelectorAll('a[href^="#food-"]').forEach(link => {
      link.addEventListener('click', () => {
        const target = document.getElementById(link.hash.slice(1));
        if (target?.tagName === 'DETAILS') target.open = true;
      }, {capture:true});
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else {
    init();
  }
})();
