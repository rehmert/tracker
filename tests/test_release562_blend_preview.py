"""Release 562 blend preview and compact source selector regression checks."""
from pathlib import Path
from jinja2 import Environment
ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/templates/blends.html").read_text()

def test_template_syntax():
    Environment().parse(HTML)

def test_compact_selector():
    assert 'name="source_id"' in HTML
    assert 'value="{{ v.id }}"' in HTML
    assert 'v.purchase.vendor' in HTML
    assert '"tirzepatide":"Tirz"' in HTML
    assert '"retatrutide":"Reta"' in HTML
    assert 'v.compound.name|truncate(12' in HTML
    assert '{{ d.remaining_base|amt(d.dim) }} remaining' not in HTML
    assert '<th>Target/draw</th>' in HTML

def test_read_only_preview_with_dry_or_blank_transfer():
    assert "const hypothetical=hasDrySource||hasMissingTransfer;" in HTML
    assert "hypothetical?'/blends/reconstitution-preview':'/blends/preview'" in HTML
    assert "if(hypothetical){" in HTML
    assert "approvedSnapshot=snapshot();" in HTML
    assert "form.action='/blends/record-plan';recordButton.disabled=false;" in HTML
    assert "form.action='/blends';recordButton.disabled=false;" in HTML
    assert "preview.innerHTML=result;" in HTML
    assert "reviewStatus.textContent='Preview could not be completed." in HTML
