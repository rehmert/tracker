from pathlib import Path
import subprocess

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def test_logging_forms_retain_native_fallback():
    for name in (
        'doses',
        'dose_edit',
        'vitals',
        'vitals_edit'
    ):
        source = (
            ROOT / 'app/templates' / f'{name}.html'
        ).read_text()

        assert source.count(
            'tracker-time24-371.js'
        ) == 1
        assert source.count(
            'tracker-mobile-log373.css'
        ) == 1

        assert 'type="datetime-local"' in source
        templates.env.get_template(f'{name}.html')


def test_24h_adapter_behavior():
    subprocess.run(
        ['node', 'scripts/tracker-time24-check371.cjs'],
        cwd=ROOT,
        check=True
    )
