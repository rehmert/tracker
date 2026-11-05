import os
import json
import pytest
from app.pk_manifest269 import write_atomic


def test_private_atomic_file(tmp_path):
    root=tmp_path/'logs'
    root.mkdir(mode=0o700)
    os.chmod(root,0o700)

    target=root/'manifest.json'

    write_atomic(root,target)
    write_atomic(root,target)

    assert target.stat().st_mode & 0o777==0o600
    assert json.loads(
        target.read_text()
    )['format']=='tracker-release-manifest-v1'

    assert not list(root.glob('.tracker-manifest-*.tmp'))


def test_symlink_is_rejected(tmp_path):
    root=tmp_path/'logs'
    root.mkdir(mode=0o700)
    os.chmod(root,0o700)

    original=tmp_path/'other'
    original.write_text('untouched')

    target=root/'manifest.json'
    target.symlink_to(original)

    with pytest.raises(ValueError):
        write_atomic(root,target)

    assert original.read_text()=='untouched'
