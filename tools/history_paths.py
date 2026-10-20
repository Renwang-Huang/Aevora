"""Resolve relocated documentation without changing frozen source records.

Only developer archive collectors use this map. It grants no Host authority and
does not substitute new source hashes for historical source pins.
"""
import csv
from pathlib import Path, PurePosixPath


def history_path(root, relative):
    root = Path(root).resolve()
    relative = str(relative)
    original = PurePosixPath(relative)
    if original.is_absolute() or '..' in original.parts or str(original) != relative or '\\' in relative:
        raise ValueError('Canonical repository-relative path required')
    with (root / 'docs/history/PATH_RELOCATIONS.csv').open(newline='') as stream:
        paths = {row['old_path']: row['new_path'] for row in csv.DictReader(stream)}
    overlay = root / 'docs/history/PRODUCT_PATH_RELOCATIONS.csv'
    if overlay.is_file():
        with overlay.open(newline='') as stream:
            paths.update({row['old_path']: row['new_path'] for row in csv.DictReader(stream)
                          if row['new_path'].startswith('docs/history/')})
    mapped = paths.get(relative, relative)
    target = root / mapped
    if mapped != relative and not mapped.startswith('docs/history/'):
        raise ValueError('Historical documents must remain in docs/history')
    if target.resolve() != target or not target.is_relative_to(root):
        raise ValueError('Linked historical path refused')
    return target


def write_phase_report(archive, name, text):
    """New phase output belongs to its run, never the frozen documentation."""
    archive = Path(archive).absolute()
    if Path(name).name != name or not name.endswith('.md'):
        raise ValueError('Plain report filename required')
    for parent in (archive, *archive.parents):
        if parent.is_symlink() or (parent / 'EVIDENCE_MANIFEST.json').exists():
            raise ValueError('Sealed or linked archive is immutable')
    frozen = Path(__file__).resolve().parents[1] / 'docs/history'
    if archive.is_relative_to(frozen):
        raise ValueError('Historical documentation is immutable report input')
    directory = archive / 'reports'
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink():
        raise ValueError('Linked report directory refused')
    target = directory / name
    with target.open('x') as stream:
        stream.write(text)
    return target
