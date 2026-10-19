"""Adversarial publication inputs must not escape the explicitly reviewed source."""
from pathlib import Path
import os
import pytest
from tools.public_release import chosen


@pytest.mark.parametrize('name', ['../outside.py', '/tmp/private.py', '.env', 'host.key', 'runs/result.json'])
def test_unsafe_selected_path_is_rejected_before_copy(tmp_path, name):
    (tmp_path/'PUBLIC_SOURCE_FILES.txt').write_text(name+'\n')
    with pytest.raises(ValueError):
        chosen(tmp_path)


@pytest.mark.parametrize('kind', ['file_symlink', 'directory_symlink', 'hardlink', 'fifo'])
def test_filesystem_alias_or_special_file_cannot_be_published(tmp_path, kind):
    private=tmp_path/'private';private.mkdir();(private/'source.py').write_text('# private bytes\n')
    if kind=='directory_symlink':
        (tmp_path/'selected').symlink_to(private, target_is_directory=True);name='selected/source.py'
    else:
        p=tmp_path/'selected.py';name=p.name
        if kind=='file_symlink':p.symlink_to(private/'source.py')
        elif kind=='hardlink':os.link(private/'source.py',p)
        else:os.mkfifo(p)
    (tmp_path/'PUBLIC_SOURCE_FILES.txt').write_text(name+'\n')
    with pytest.raises(ValueError):
        chosen(tmp_path)


def test_disclosed_oracle_is_publishable_without_publishing_live_run_data(tmp_path):
    p=tmp_path/'evaluator/hidden_tests/test_public_history.py';p.parent.mkdir(parents=True)
    p.write_text('# Owner-authorized historical test source\n')
    (tmp_path/'PUBLIC_SOURCE_FILES.txt').write_text('evaluator/hidden_tests/test_public_history.py\n')
    assert chosen(tmp_path)==[p]
