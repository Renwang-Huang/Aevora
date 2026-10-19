"""Invalid parser inputs only; never natural Agent/Outcome evidence.

The positive demo check separately uses real graph/native/Oracle records.
These intentionally invalid fixtures test fail-closed byte/path handling.
"""
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import pytest

SOURCE=Path(__file__).resolve().parents[1]/'aevora_core/scripts/h3_verify.py'
spec=importlib.util.spec_from_file_location('h3_public_standalone_verifier',SOURCE)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def invalid_fixture(tmp_path):
    p=tmp_path/'fixture';p.mkdir()
    (p/'item.json').write_text('{}\n')
    m={'kind':'AEVORA_H3_READ_ONLY_DEMO','files':{'item.json':sha256((p/'item.json').read_bytes()).hexdigest()},
        'fixture_classification':'EXPLICIT_SYNTHETIC_INVALID_PARSER_INPUT; NOT_A_RUN'}
    (p/'MANIFEST.json').write_text(json.dumps(m));return p,m


def test_nonexistent_directory_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='Ordinary'):module.verify(tmp_path/'missing')


def test_symlink_directory_is_rejected(tmp_path):
    p,m=invalid_fixture(tmp_path);link=tmp_path/'linked';link.symlink_to(p,target_is_directory=True)
    with pytest.raises(ValueError,match='Ordinary'):module.verify(link)


def test_changed_byte_is_rejected(tmp_path):
    p,m=invalid_fixture(tmp_path);(p/'item.json').write_text('{"tampered":true}')
    with pytest.raises(ValueError,match='byte tamper'):module.verify(p)


def test_extra_file_is_rejected(tmp_path):
    p,m=invalid_fixture(tmp_path);(p/'unlisted.txt').write_text('not admitted')
    with pytest.raises(ValueError,match='file set'):module.verify(p)


def test_linked_member_is_rejected(tmp_path):
    p,m=invalid_fixture(tmp_path);(p/'item.json').unlink();(tmp_path/'outside.json').write_text('{}\n');(p/'item.json').symlink_to(tmp_path/'outside.json')
    with pytest.raises(ValueError,match='Unsafe member'):module.verify(p)


def test_missing_member_is_rejected(tmp_path):
    p,m=invalid_fixture(tmp_path);(p/'item.json').unlink()
    with pytest.raises(ValueError,match='file set'):module.verify(p)


def test_external_manifest_pin_is_required_to_match(tmp_path):
    p,m=invalid_fixture(tmp_path)
    with pytest.raises(ValueError,match='pin mismatch'):module.verify(p,'0'*64)


def test_non_demo_manifest_is_rejected(tmp_path):
    p,m=invalid_fixture(tmp_path);m['kind']='FAKE_PASS';(p/'MANIFEST.json').write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Unexpected manifest'):module.verify(p)


def test_linked_manifest_is_rejected_before_read(tmp_path):
    p,m=invalid_fixture(tmp_path);manifest=p/'MANIFEST.json'
    saved=tmp_path/'outside-manifest.json';manifest.rename(saved);manifest.symlink_to(saved)
    with pytest.raises(ValueError,match='Unsafe member'):module.verify(p)


def test_hardlinked_member_is_rejected(tmp_path):
    p,m=invalid_fixture(tmp_path);os.link(p/'item.json',tmp_path/'outside-item.json')
    with pytest.raises(ValueError,match='Unsafe member'):module.verify(p)


def test_fifo_member_is_rejected_without_blocking(tmp_path):
    p,m=invalid_fixture(tmp_path);(p/'item.json').unlink();os.mkfifo(p/'item.json')
    with pytest.raises(ValueError,match='Unsafe member'):module.verify(p)


def test_oversized_manifest_is_rejected(tmp_path):
    p,m=invalid_fixture(tmp_path)
    with (p/'MANIFEST.json').open('r+b') as f:f.truncate(32*1024*1024+1)
    with pytest.raises(ValueError,match='Unsafe member'):module.verify(p)


def test_duplicate_manifest_keys_are_rejected(tmp_path):
    p,m=invalid_fixture(tmp_path);(p/'MANIFEST.json').write_text('{"kind":"FAKE_PASS","kind":"AEVORA_H3_READ_ONLY_DEMO"}')
    with pytest.raises(ValueError,match='Duplicate JSON key'):module.verify(p)


def test_nonfinite_manifest_values_are_rejected(tmp_path):
    p,m=invalid_fixture(tmp_path);(p/'MANIFEST.json').write_text('{"number":NaN}')
    with pytest.raises(ValueError,match='Non-finite JSON'):module.verify(p)
