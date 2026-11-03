/*
 * Tracker page title capitalization.
 *
 * Presentation only:
 * - No route, database or form changes
 * - Matches navigation Title Case conventions
 * - Preserves common technical acronyms
 * - Handles dynamically inserted page headings
 */
(function () {
  "use strict";

  const acronyms = Object.freeze({
    pk: "PK",
    fefo: "FEFO",
    sqlite: "SQLite",
    coas: "COAs",
    coa: "COA",
    ui: "UI",
    ux: "UX",
    csv: "CSV",
    api: "API",
    http: "HTTP",
    https: "HTTPS",
    sql: "SQL",
    htmx: "HTMX",
    hcg: "hCG",
    hgh: "HGH",
    igf: "IGF",
    trt: "TRT",
    tsh: "TSH",
    t3: "T3",
    t4: "T4",
    fsh: "FSH",
    lh: "LH",
    psa: "PSA",
    dna: "DNA",
    rna: "RNA",
    ai: "AI",
    iu: "IU",
    mg: "mg",
    mcg: "mcg",
    ml: "mL",
    ng: "ng",
    dl: "dL",
    bpm: "BPM",
    bp: "BP"
  });

  function titleCase(value) {
    return value.replace(/[A-Za-z]+/g, function (word) {
      const lower = word.toLowerCase();

      if (Object.prototype.hasOwnProperty.call(
        acronyms, lower
      )) {
        return acronyms[lower];
      }

      // Keep existing intentional mixed-case notation.
      if (
        word.length > 1 &&
        /[a-z]/.test(word) &&
        /[A-Z]/.test(word.slice(1))
      ) {
        return word;
      }

      return lower.charAt(0).toUpperCase() +
        lower.slice(1);
    });
  }

  function formatTextNodes(element) {
    if (!element || element.closest(
      "[data-no-title-case], pre, code, kbd, samp"
    )) {
      return;
    }

    const walker = document.createTreeWalker(
      element,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          const parent = node.parentElement;

          if (!parent || parent.closest(
            "pre, code, kbd, samp, " +
            "[data-no-title-case], " +
            "[contenteditable], input, textarea"
          )) {
            return NodeFilter.FILTER_REJECT;
          }

          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );

    const nodes = [];
    while (walker.nextNode()) {
      nodes.push(walker.currentNode);
    }

    nodes.forEach(function (node) {
      const current = node.nodeValue;
      const updated = titleCase(current);

      if (updated !== current) {
        node.nodeValue = updated;
      }
    });
  }

  function apply(root) {
    if (!root) return;

    const selector = [
      "h1", "h2", "h3", "h4",
      ".page-title",
      ".section-title",
      ".panel-title",
      ".card-title",
      ".dashboard-section-title"
    ].join(", ");

    const main = document.getElementById("main-content");

    if (main) {
      if (
        root.nodeType === Node.ELEMENT_NODE &&
        root.matches(selector) &&
        main.contains(root)
      ) {
        formatTextNodes(root);
      }

      if (
        root === document ||
        root === main ||
        (root.nodeType === Node.ELEMENT_NODE &&
         main.contains(root))
      ) {
        const scope = root === document
          ? main
          : root;

        scope.querySelectorAll(selector).forEach(
          formatTextNodes
        );
      }
    }

    if (document.title) {
      const updated = titleCase(document.title);

      if (updated !== document.title) {
        document.title = updated;
      }
    }
  }

  let scheduled = false;

  function scheduleApply() {
    if (scheduled) return;

    scheduled = true;

    requestAnimationFrame(function () {
      scheduled = false;
      apply(document);
    });
  }

  function initialize() {
    apply(document);

    const main = document.getElementById(
      "main-content"
    );

    if (main) {
      const observer = new MutationObserver(
        scheduleApply
      );

      observer.observe(main, {
        childList: true,
        subtree: true,
        characterData: true
      });
    }

    document.addEventListener(
      "htmx:afterSwap",
      scheduleApply
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      initialize,
      { once: true }
    );
  } else {
    initialize();
  }
})();
