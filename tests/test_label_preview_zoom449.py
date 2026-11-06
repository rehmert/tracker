"""Release 449: independent 300%-default on-screen vial label preview zoom."""
from pathlib import Path
import shutil
import subprocess

import pytest
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/vial_label_sheets447.html"
SCRIPT = ROOT / "app/static/js/tracker-label-preview-zoom449.js"


def test_300_percent_default_is_applied_in_css_even_without_javascript():
    html = TEMPLATE.read_text()
    assert ":root{color-scheme:light;--label-preview-scale:3}" in html
    assert 'id="label-preview-zoom449"' in html
    assert '<option value="3" selected>300% (default)</option>' in html
    assert "transform:scale(var(--label-preview-scale))" in html
    assert "transform-origin:top left" in html
    assert 'class="label-preview-stage"' in html
    assert "label-preview-zoom449.js?v=449" in html


def test_zoom_options_are_independent_of_sheet_print_settings():
    source = TEMPLATE.read_text()
    for value in ("1", "1.5", "2", "3", "4", "5"):
        assert f'<option value="{value}"' in source
    assert source.count('id="label-preview-zoom449"') == 1
    # Zoom is an on-screen control, not a setting submitted to the server
    # as part of layout, phase, rotation or copy count.
    assert 'name="zoom"' not in source
    assert 'name="preview_scale"' not in source
    script = SCRIPT.read_text()
    assert "sessionStorage" in script
    assert 'apply(saved || "3")' in script
    assert "--label-preview-scale" in script
    assert "window.print()" not in script
    assert "fetch(" not in script


def test_print_css_restores_exact_original_203dpi_sheet_layout():
    html = TEMPLATE.read_text()
    assert "@page{size:{{ width_mm }}mm {{ height_mm }}mm;margin:0}" in html
    assert ".sheet-frame:last-child{break-after:auto;page-break-after:auto}" in html
    assert ".label-preview-stage{width:{{ width_mm }}mm!important;height:{{ height_mm }}mm!important}" in html
    assert ".label-sheet{transform:none!important;transform-origin:top left!important}" in html
    assert ".label-sheet,.label-sheet svg{width:{{ width_mm }}mm!important;height:{{ height_mm }}mm!important;overflow:hidden!important}" in html
    assert 'href="/vials/labels/sheets/download?' in html
    assert 'fmt=png' in html and 'fmt=svg' in html
    assert 'name="ids"' in html


def test_jinja_template_remains_valid():
    Environment().parse(TEMPLATE.read_text())


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable")
def test_zoom_javascript_syntax():
    result = subprocess.run(
        ["node", "--check", str(SCRIPT)],
        capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable")
def test_zoom_runtime_defaults_to_300_and_remembers_allowed_selection():
    program = r"""
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");
const listeners = {};
const select = {
  value: "3",
  addEventListener(name, fn) {listeners[name] = fn;}
};
const status = {textContent: ""};
const custom = {};
const document = {
  readyState: "complete",
  getElementById(id) {
    if(id === "label-preview-zoom449") return select;
    if(id === "label-preview-zoom-status449") return status;
    return null;
  },
  documentElement: {
    style: {setProperty(key, value) {custom[key] = value;}}
  }
};
const store = new Map();
const storage = {
  getItem(key) {return store.get(key) || null;},
  setItem(key, value) {store.set(key, value);}
};
const code = fs.readFileSync(process.argv[1], "utf8");
function run() {
  delete listeners.change;
  vm.runInNewContext(code, {document, sessionStorage:storage});
}
run();
assert.equal(select.value, "3");
assert.equal(custom["--label-preview-scale"], "3");
assert(status.textContent.includes("300%"));
select.value = "4";
listeners.change();
assert.equal(custom["--label-preview-scale"], "4");
assert(status.textContent.includes("400%"));
assert.equal(store.get("tracker.labelPreviewZoom449"), "4");
run();
assert.equal(select.value, "4");
assert.equal(custom["--label-preview-scale"], "4");
select.value = "999";
listeners.change();
assert.equal(select.value, "3");
assert.equal(custom["--label-preview-scale"], "3");
assert.equal(store.get("tracker.labelPreviewZoom449"), "3");
console.log("PASS: independent preview zoom, 300% default, remembered levels and invalid fallback");
"""
    result = subprocess.run(
        ["node", "-e", program, str(SCRIPT)],
        capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS: independent preview zoom" in result.stdout
