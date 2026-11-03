/* Tracker long-page navigation: presentation only. */
(function () {
  "use strict";

  const main = document.getElementById("main-content");
  const slot = document.getElementById(
    "tracker-page-jump-slot"
  );

  if (!main || !slot) return;

  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  );

  const sections = new Map();

  const bar = document.createElement("nav");
  bar.className = "tracker-page-jump";
  bar.setAttribute("aria-label", "Page sections");
  bar.hidden = true;

  const label = document.createElement("label");
  label.textContent = "Jump to Section";
  label.htmlFor = "tracker-page-jump-select";

  const select = document.createElement("select");
  select.id = "tracker-page-jump-select";
  select.setAttribute("aria-label", "Jump to Section");

  label.append(select);
  bar.append(label);
  slot.append(bar);

  const top = document.createElement("button");
  top.type = "button";
  top.id = "tracker-back-to-top";
  top.className = "tracker-back-to-top";
  top.textContent = "↑ Top";
  top.setAttribute("aria-label", "Back to top");
  top.hidden = true;

  document.body.append(top);

  function scrollToElement(element) {
    element.scrollIntoView({
      behavior: reducedMotion.matches
        ? "instant" : "smooth",
      block: "start"
    });
  }

  function visibleHeading(element) {
    if (
      !element.textContent.trim() ||
      !element.getClientRects().length ||
      element.closest(
        "nav, .workspace-toolbar, .mobile-topbar, " +
        "[hidden], [aria-hidden='true'], " +
        ".tracker-page-jump, " +
        ".workspace-settings, .command-overlay"
      )
    ) {
      return false;
    }

    // Exclude headings in closed disclosure panels.
    const details = element.closest("details");
    if (details && !details.open) return false;

    return true;
  }

  function refresh() {
    sections.clear();
    select.replaceChildren();

    const headings = Array.from(
      main.querySelectorAll("h2, h3")
    ).filter(visibleHeading).slice(0, 40);

    if (headings.length < 3) {
      bar.hidden = true;
      return;
    }

    const first = document.createElement("option");
    first.value = "";
    first.textContent = "Choose a Section…";
    select.append(first);

    headings.forEach(function (heading, index) {
      const key = String(index);
      const option = document.createElement("option");

      const name = heading.textContent
        .replace(/\s+/g, " ")
        .trim();

      option.value = key;
      option.textContent =
        (heading.tagName === "H3" ? "    " : "") +
        name.slice(0, 110);

      sections.set(key, heading);
      select.append(option);
    });

    select.value = "";
    bar.hidden = false;
  }

  select.addEventListener("change", function () {
    const target = sections.get(select.value);
    if (!target) return;

    scrollToElement(target);

    // Make the heading keyboard-focusable without
    // changing its semantic heading role.
    if (!target.hasAttribute("tabindex")) {
      target.setAttribute("tabindex", "-1");
    }

    target.focus({ preventScroll: true });
    select.value = "";
  });

  let scrollPending = false;

  function updateTop() {
    scrollPending = false;
    top.hidden = window.scrollY < 550;
  }

  window.addEventListener("scroll", function () {
    if (scrollPending) return;

    scrollPending = true;
    requestAnimationFrame(updateTop);
  }, { passive: true });

  top.addEventListener("click", function () {
    window.scrollTo({
      top: 0,
      behavior: reducedMotion.matches
        ? "instant" : "smooth"
    });
  });

  let refreshPending = false;

  function scheduleRefresh() {
    if (refreshPending) return;

    refreshPending = true;
    requestAnimationFrame(function () {
      refreshPending = false;
      refresh();
      updateTop();
    });
  }

  document.addEventListener(
    "htmx:afterSwap",
    scheduleRefresh
  );

  document.addEventListener(
    "htmx:afterSettle",
    scheduleRefresh
  );

  window.addEventListener("pageshow", updateTop);

  refresh();
  updateTop();
})();
