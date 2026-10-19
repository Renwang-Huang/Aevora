"""Repository moves must preserve evidence, export coverage and output safety."""
import csv
from hashlib import sha256
from pathlib import Path

import pytest

from tools.history_paths import history_path, write_phase_report
from tools.public_release import chosen

ROOT = Path(__file__).resolve().parents[1]


def test_root_inventory_and_all_relocated_hashes_match():
    with (ROOT/'docs/history/ROOT_CLEANUP_MATRIX.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 101
    assert sum(row['action'] == 'MOVE' for row in rows) == 82
    expected_root = {row['new_path'] for row in rows if row['action'] == 'KEEP'}
    # Ignore local build/cache files; all baseline root entrypoints are retained.
    assert len(expected_root) == 19
    for row in rows:
        path = ROOT/row['new_path']
        assert path.is_file() and not path.is_symlink()
        assert sha256(path.read_bytes()).hexdigest() == row['new_sha256']
        if row['action'] == 'MOVE':
            assert not (ROOT/row['old_path']).exists()
            assert history_path(ROOT,row['old_path']) == path
            if path.suffix in {'.csv','.json'}:
                assert row['old_sha256'] == row['new_sha256']


def test_relocated_history_and_metadata_are_exported():
    selected = {p.relative_to(ROOT).as_posix() for p in chosen(ROOT)}
    with (ROOT/'docs/history/PATH_RELOCATIONS.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 82
    assert all(row['new_path'] in selected for row in rows)
    assert {'docs/history/ROOT_CLEANUP_MATRIX.csv','docs/history/PATH_RELOCATIONS.csv',
            'tools/history_paths.py','tests/test_repository_history_layout.py'} <= selected


@pytest.mark.parametrize('name',['../README.md','/etc/passwd','docs/../README.md'])
def test_historical_lookup_rejects_noncanonical_paths(name):
    with pytest.raises(ValueError):
        history_path(ROOT,name)


def test_new_phase_reports_cannot_overwrite_history_or_escape(tmp_path):
    report = write_phase_report(tmp_path,'fresh.md','observed result')
    assert report.read_text() == 'observed result'
    with pytest.raises(FileExistsError):
        write_phase_report(tmp_path,'fresh.md','replacement')
    assert report.read_text() == 'observed result'
    sealed = tmp_path/'sealed';sealed.mkdir()
    (sealed/'EVIDENCE_MANIFEST.json').write_text('{}')
    with pytest.raises(ValueError):
        write_phase_report(sealed,'new.md','forbidden')
    linked = tmp_path/'linked';linked.mkdir()
    (linked/'reports').symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError):
        write_phase_report(linked,'escape.md','forbidden')
    with pytest.raises(ValueError):
        write_phase_report(ROOT/'docs/history','overwrite.md','forbidden')
