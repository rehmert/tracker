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

  // Never reformat a compound-bearing title; names are user-defined.
  let compoundPatterns = null;

  function isCompoundTitle(value) {
    return compoundPatterns !== null && compoundPatterns.some(
      function (pattern) { return pattern.test(value); }
    );
  }

  function setCompoundNames(names) {
    compoundPatterns = names
      .filter(function (name) {
        return typeof name === "string" && name.trim().length > 0;
      })
      .map(function (name) {
        const escaped = name.trim()
          .replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")
          .replace(/\s+/g, "\\s+");
        // Require full names, not substrings of longer identifiers.
        return new RegExp(
          "(^|[^A-Za-z0-9])" + escaped + "(?=$|[^A-Za-z0-9])", "i"
        );
      });
  }

  function titleCase(value) {
    const cased = value.replace(/[A-Za-z]+/g, function (word) {
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
    // Possessive apostrophe-s remains lowercase after title casing.
    return cased.replace(/(['’])S\b/g, '$1s');
  }

  function formatTextNodes(element) {
    if (!element || element.closest(
      "[data-no-title-case], pre, code, kbd, samp"
    )) {
      return;
    }

    // Examine the entire heading, including nested inline markup.
    if (isCompoundTitle(element.textContent || "")) return;

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

  const selector = [
      "h1", "h2", "h3", "h4",
      ".page-title",
      ".section-title",
      ".panel-title",
      ".card-title",
      ".dashboard-section-title"
    ].join(", ");

  function apply(root) {
    if (!root) return;
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

    if (document.title && !isCompoundTitle(document.title)) {
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
    // First obtain the catalog. Formatting before this completes can
    // irrevocably change intentional compound capitalization.
    fetch("/compounds/title-names", {
      credentials: "same-origin",
      cache: "no-store"
    }).then(function (response) {
      if (!response.ok) throw new Error("Compound names unavailable");
      return response.json();
    }).then(function (data) {
      if (!data || !Array.isArray(data.names)) {
        throw new Error("Invalid compound catalog");
      }
      setCompoundNames(data.names);
      apply(document);

      const main = document.getElementById("main-content");
      if (main) {
        const observer = new MutationObserver(records => {
          // Ignore unrelated form/table mutations; heading edits and inserted
          // heading subtrees still trigger the existing coalesced refresh.
          const relevant = records.some(record => {
            const element = record.target.nodeType === Node.ELEMENT_NODE
              ? record.target : record.target.parentElement;
            if (element && element.closest(selector)) return true;
            return Array.from(record.addedNodes).some(node =>
              node.nodeType === Node.ELEMENT_NODE &&
              (node.matches(selector) || node.querySelector(selector)));
          });
          if (relevant) scheduleApply();
        });
        observer.observe(main, {
          childList: true,
          subtree: true,
          characterData: true
        });
      }
      document.addEventListener("htmx:afterSwap", scheduleApply);
    }).catch(function () {
      // If the private catalog is unavailable, leave original titles intact.
    });
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
