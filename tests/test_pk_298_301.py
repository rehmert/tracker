import importlib.util
import subprocess
from pathlib import Path


def test_wrapper_shell_syntax_and_invocation():
    shell=Path(
        'scripts/tracker-pk-browser-check281.sh'
    )

    subprocess.run(
        ['bash','-n',str(shell)],
        check=True
    )

    source=shell.read_text()

    assert '${TRACKER_TEST_URL:-http://127.0.0.1:8000}' in source
    assert 'tracker-browser-auth301.py' in source


def test_credentials_parser_no_secret_output(tmp_path,capsys):
    path=tmp_path/'service.env'

    path.write_text(
        "TRACKER_USER='operator'\n"
        "TRACKER_PASS='safe punctuation ! # inside'\n"
    )

    source=Path(
        'scripts/tracker-browser-auth301.py'
    )

    spec=importlib.util.spec_from_file_location(
        'tracker_browser_auth301',
        source
    )

    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result=module.credentials_from_files([path])

    assert result=={
        'TRACKER_USER':'operator',
        'TRACKER_PASS':'safe punctuation ! # inside'
    }

    assert capsys.readouterr().out==''
