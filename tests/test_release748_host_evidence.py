"""Release 748 resolved Chromium ELF inventory, no-clobber private evidence."""
from pathlib import Path
import json
import os

import pytest

from scripts import tracker_browser_elf748 as elf

def make_fixture(tmp_path):
    binary=tmp_path/"chromium748"
    binary.write_bytes(b"nonrunning chromium test bytes")
    lib=tmp_path/"libsample748.so.1"
    lib.write_bytes(b"safe synthetic library bytes")
    loader=tmp_path/"ld748.so.2"
    loader.write_bytes(b"loader fixture bytes")
    return binary,lib,loader,(
        "linux-vdso.so.1 (0x00000000001)\n"
        f"  libsample748.so.1 => {lib} (0x00000000002)\n"
        f"  {loader} (0x00000000003)\n"
    )


def test_748_loader_parser_records_sonames_and_system_interpreter(tmp_path):
    binary,lib,loader,raw=make_fixture(tmp_path)
    found=elf.parse_ldd(raw)
    assert found=={"ld748.so.2":loader,"libsample748.so.1":lib}
    assert all(isinstance(v,Path) for v in found.values())


@pytest.mark.parametrize("bad",[
    "libmissing.so.1 => not found",
    "statically linked",
    "linux-vdso.so.1 (0x3)",
    "libbad.so => /etc/foo (no address)",
    "libbad.so => /etc/foo (0x3)\nlibbad.so => /etc/bar (0x4)",
    "libbad.so => ../../other.so (0x3)",
    "libweird.so (0x3)",
    "",
])
def test_748_loader_fails_closed_on_missing_duplicate_or_unknown(bad):
    with pytest.raises(elf.HostEvidenceError):
        elf.parse_ldd(bad)


def test_748_snapshot_hashes_real_symlink_targets_and_never_exposes_paths(tmp_path):
    binary,lib,loader,raw=make_fixture(tmp_path)
    alias=tmp_path/"libalias748.so.1"
    alias.symlink_to(lib)
    raw=f"libalias748.so.1 => {alias} (0x1)\n{loader} (0x2)\n"
    report=elf.snapshot(binary, raw)
    assert len(report["libraries"])==2
    assert report["libraries"]["libalias748.so.1"]["sha256"]==elf.file_digest(lib)["sha256"]
    assert report["browser"]["chromium_sha256"]
    serialized=json.dumps(report,sort_keys=True)
    assert str(tmp_path) not in serialized
    assert "/tmp/" not in serialized
    assert report["scope"]==elf.SCOPE


def test_748_private_noclobber_comparison_and_rollback_not_inferred(tmp_path):
    binary,lib,loader,raw=make_fixture(tmp_path)
    report=elf.snapshot(binary, raw)
    folder=tmp_path/"locked"
    folder.mkdir(mode=0o700)
    output=folder/"dev.json"
    elf.private_write(output,report)
    assert output.stat().st_mode & 0o077==0
    assert elf.private_read(output)==report
    with pytest.raises(FileExistsError):
        elf.private_write(output,report)
    equal=elf.compare(report,report)
    assert equal["matching_host_fingerprints"]
    assert not equal["offline_browser_replay_performed"]
    assert not equal["os_chromium_rollback_tested"]
    assert not equal["full_dynamic_elf_closure_certified"]
    mutated=json.loads(json.dumps(report))
    mutated["libraries"]["ld748.so.2"]["sha256"]="b"*64
    mismatch=elf.compare(report,mutated)
    assert not mismatch["matching_host_fingerprints"]
    assert mismatch["differing_library_count"]==1
    link=folder/"link.json"
    link.symlink_to(output)
    with pytest.raises(elf.HostEvidenceError):
        elf.private_read(link)


@pytest.mark.parametrize("field,bad",[
    ("schema",2),
    ("scope","complete rollback confirmed"),
    ("libraries",{"libunsafe": {"sha256":"z"*64,"bytes":4}}),
])
def test_748_forged_evidence_scope_schema_or_hash_rejected(tmp_path,field,bad):
    binary,lib,loader,raw=make_fixture(tmp_path)
    receipt=elf.snapshot(binary,raw)
    receipt[field]=bad
    with pytest.raises(elf.HostEvidenceError):
        elf.validate(receipt)


def test_748_no_browser_execution_downloads_or_environment_leaks():
    source=(Path(__file__).resolve().parents[1]/"scripts/tracker_browser_elf748.py").read_text()
    assert '"/usr/bin/ldd"' in source
    assert '"LC_ALL": "C"' in source
    assert "LD_LIBRARY_PATH" not in source
    for forbidden in ("pip install", "apt install", "curl ", "wget ",
                      "chromium.launch(", "systemctl restart", "/etc/tracker.env"):
        assert forbidden not in source
