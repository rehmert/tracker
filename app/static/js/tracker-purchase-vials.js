/* Purchase vial quantity and price preview; counts and money use exact cents. */
(() => {
  "use strict";
  const form = document.getElementById("purchase-vial-form");
  if (!form) return;
  const field = name => form.elements.namedItem(name);
  const size = field("kit_size");
  const kits = field("kit_count");
  const quantity = field("quantity");
  const basis = field("price_basis");
  const price = field("price_amount");
  const kitsField = document.getElementById("purchase-vial-kits-field");
  const quantityField = document.getElementById("purchase-vial-quantity-field");
  const label = document.getElementById("purchase-vial-price-label");
  const help = document.getElementById("purchase-vial-price-help");
  const preview = document.getElementById("purchase-vial-preview");
  const submit = document.getElementById("purchase-vial-submit");
  if (!size || !kits || !quantity || !basis || !price || !kitsField ||
      !quantityField || !label || !help || !preview || !submit) return;

  function money(cents) {
    const symbol = form.dataset.currency || "$";
    return symbol + (cents / 100).toLocaleString(undefined, {
      minimumFractionDigits: 2, maximumFractionDigits: 2
    });
  }
  function refresh() {
    const kitSize = Number(size.value);
    const isKit = kitSize === 5 || kitSize === 10;
    const count = Number(isKit ? kits.value : quantity.value);
    const vialCount = isKit ? kitSize * count : count;
    const validCount = Number.isInteger(count) && count >= 1 &&
      count <= (isKit ? 100 : 200);
    kitsField.hidden = !isKit;
    quantityField.hidden = isKit;
    kits.disabled = !isKit;
    quantity.disabled = isKit;

    for (const option of basis.options) {
      option.disabled = option.value === "per_half_kit" ? kitSize !== 5 :
        option.value === "per_full_kit" ? kitSize !== 10 : false;
    }
    if (basis.selectedOptions[0]?.disabled) basis.value = "per_vial";
    const perKit = basis.value !== "per_vial";
    const unit = perKit
      ? (kitSize === 5 ? "half kit (5 vials)" : "full kit (10 vials)")
      : "vial";
    label.textContent = "Price per " + unit + " (" + (form.dataset.currency || "$") + ")";
    help.textContent = perKit
      ? "Enter the price of one kit. Exact kit totals are preserved across vials."
      : "Enter the price of one vial.";
    const entered = Number(price.value);
    const validPrice = price.value.trim() !== "" && Number.isFinite(entered) &&
      entered >= 0 && Math.round(entered * 100) <= Number.MAX_SAFE_INTEGER;
    if (!validCount || !validPrice) {
      preview.textContent = "Enter a valid quantity and nonnegative price to preview this purchase.";
      submit.textContent = "Add vials";
      return;
    }
    const cents = Math.round(entered * 100);
    const total = cents * (perKit ? count : vialCount);
    if (!Number.isSafeInteger(total)) {
      preview.textContent = "Price or quantity is too large.";
      submit.textContent = "Add vials";
      return;
    }
    const packageSummary = isKit
      ? count + " " + (kitSize === 5 ? "half kit" : "full kit") +
        (count === 1 ? "" : "s") + " · " + vialCount + " vials"
      : vialCount + " individual vial" + (vialCount === 1 ? "" : "s");
    preview.textContent = packageSummary + " · Line total: " + money(total) +
      (perKit ? " · Kit price allocated across vials" : "");
    submit.textContent = "Add " + vialCount + " vial" + (vialCount === 1 ? "" : "s");
  }
  form.addEventListener("input", refresh);
  form.addEventListener("change", refresh);
  refresh();
})();
