/*
 * Tracker section deep links.
 * Extends the existing page-jump control without
 * changing records, navigation paths or form data.
 */
(function () {
  "use strict";

  const main = document.getElementById("main-content");
  const select = document.getElementById(
    "tracker-page-jump-select"
  );

  if (!main || !select) return;

  const bar = select.closest(".tracker-page-jump");
  if (!bar) return;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "tracker-copy-section-link";
  button.textContent = "Copy Section Link";
  button.disabled = true;
  button.setAttribute(
    "aria-label", "Copy current section link"
  );

  const status = document.createElement("span");
  status.className = "tracker-section-link-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");

  bar.append(button, status);

  let headings = [];
  let active = null;
  let pending = false;
  let initialHashHandled = false;

  function visible(element) {
    if (
      !element.textContent.trim() ||
      !element.getClientRects().length ||
      element.closest(
        "nav, .workspace-toolbar, .mobile-topbar, " +
        "[hidden], [aria-hidden='true'], " +
        ".workspace-settings, .command-overlay"
      )
    ) {
      return false;
    }

    const details = element.closest("details");
    return !details || details.open;
  }

  function collect() {
    return Array.from(
      main.querySelectorAll("h2, h3")
    ).filter(visible).slice(0, 40);
  }

  function ensureIds() {
    headings.forEach(function (heading, index) {
      if (heading.id) return;

      const base = "tracker-section-" + (index + 1);
      let candidate = base;
      let suffix = 2;

      while (document.getElementById(candidate)) {
        candidate = base + "-" + suffix++;
      }

      heading.id = candidate;
    });
  }

  function currentFromScroll() {
    if (!headings.length) return null;

    // Prefer the last heading already passed in
    // the viewport, accounting for fixed toolbars.
    let result = null;

    headings.forEach(function (heading) {
      if (heading.getBoundingClientRect().top <= 175) {
        result = heading;
      }
    });

    return result;
  }

  function setActive(heading) {
    active = heading;

    const index = headings.indexOf(heading);

    if (!bar.hidden && index >= 0) {
      select.value = String(index);
    } else if (!bar.hidden) {
      select.value = "";
    }

    button.disabled = !heading || bar.hidden;
  }

  function update() {
    pending = false;
    if (bar.hidden) {
      button.disabled = true;
      return;
    }

    const found = currentFromScroll();
    setActive(found);
  }

  function scheduleUpdate() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(update);
  }

  function sectionUrl(heading) {
    const url = new URL(window.location.href);
    url.hash = heading.id;
    return url.toString();
  }

  function navigateToHash() {
    if (!window.location.hash) return;

    let id;
    try {
      id = decodeURIComponent(
        window.location.hash.slice(1)
      );
    } catch (_) {
      return;
    }

    const target = document.getElementById(id);

    if (!target || !headings.includes(target)) return;

    initialHashHandled = true;

    target.scrollIntoView({
      block: "start",
      behavior: "instant"
    });

    setActive(target);
  }

  function refresh() {
    headings = collect();
    ensureIds();

    if (!initialHashHandled && window.location.hash) {
      navigateToHash();
    }

    scheduleUpdate();
  }

  // Capture the selection before the existing page
  // navigator resets its select control.
  select.addEventListener("change", function () {
    const index = Number(select.value);

    if (
      select.value === "" ||
      !Number.isInteger(index) ||
      index < 0 ||
      index >= headings.length
    ) {
      return;
    }

    const heading = headings[index];

    if (!heading) return;

    active = heading;

    // Update the URL without triggering a new load.
    history.replaceState(
      history.state,
      "",
      sectionUrl(heading)
    );

    button.disabled = false;
    status.textContent = "";
  }, true);

  async function copyText(value) {
    if (
      navigator.clipboard &&
      window.isSecureContext
    ) {
      await navigator.clipboard.writeText(value);
      return;
    }

    const area = document.createElement("textarea");
    area.value = value;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();

    const copied = document.execCommand("copy");
    area.remove();

    if (!copied) {
      throw new Error("Clipboard unavailable");
    }
  }

  button.addEventListener("click", async function () {
    if (!active || !headings.includes(active)) return;

    try {
      await copyText(sectionUrl(active));
      status.textContent = "Section link copied.";
    } catch (_) {
      status.textContent =
        "Copy unavailable in this browser.";
    }
  });

  window.addEventListener(
    "scroll", scheduleUpdate, { passive: true }
  );

  window.addEventListener("hashchange", function () {
    navigateToHash();
    scheduleUpdate();
  });

  document.addEventListener(
    "htmx:afterSwap",
    function () {
      requestAnimationFrame(refresh);
    }
  );

  document.addEventListener(
    "htmx:afterSettle",
    function () {
      requestAnimationFrame(refresh);
    }
  );

  window.addEventListener(
    "pageshow", refresh
  );

  refresh();
})();
