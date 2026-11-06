document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // This panel deliberately does not participate in the
  // nine legacy Release 382/383 journal accordions.
  const target = document.getElementById('food-targets');

  if (!target || target.tagName !== 'DETAILS') {
    return;
  }

  const openTarget = () => {
    target.open = true;
  };

  document.querySelectorAll(
    'a[href="#food-targets"]'
  ).forEach(link => {
    link.addEventListener('click', openTarget);
  });

  if (location.hash === '#food-targets') {
    openTarget();
  }
});
