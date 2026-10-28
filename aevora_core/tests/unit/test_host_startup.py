"""Synthetic configuration/filesystem contracts; no DB, credentials or native execution."""
from argparse import Namespace
import json
import os
from pathlib import Path
import pytest
from aevora.host_config import DB_KEYS, configure, load_profile, prepare_environment
from aevora.local_session import SessionLease, current_session
from aevora.startup import StartupError


@pytest.fixture
def profile(tmp_path, monkeypatch):
    for key in (*DB_KEYS, 'AEVORA_CONFIG'): monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path/'config'))
    args=Namespace(output=None,host='127.0.0.1',port=17790,graph='ordinary_project',
        password_file=str(tmp_path/'private/db.password'),session_root=str(tmp_path/'sessions'),console_port=17805,context=None)
    result=configure(args)
    return Path(result['config'])


def test_default_host_profile_survives_a_fresh_environment(profile):
    value=prepare_environment()
    assert value['session']['public_context']=={}
    assert os.environ['AEVORA_FALKORDB_GRAPH']=='ordinary_project'
    assert os.environ['AEVORA_FALKORDB_PORT']=='17790'
    assert profile.stat().st_mode & 0o777==0o600
    assert profile.parent.stat().st_mode & 0o777==0o700
    assert 'password' not in value['database']


def test_explicit_environment_is_not_mixed_with_an_implicit_profile(profile,monkeypatch):
    monkeypatch.setenv('AEVORA_FALKORDB_PORT','18888')
    assert prepare_environment() is None
    assert 'AEVORA_FALKORDB_PASSWORD_FILE' not in os.environ
    assert prepare_environment(profile)['database']['port']==17790
    assert os.environ['AEVORA_FALKORDB_PORT']=='17790'


@pytest.mark.parametrize('mutation',['mode','link','hardlink','duplicate','unknown','credential_value','malformed'])
def test_untrusted_profiles_are_rejected_without_disclosing_content(profile,mutation,tmp_path,capsys):
    from aevora.cli import entrypoint
    value=json.loads(profile.read_text())
    if mutation=='mode':profile.chmod(0o644)
    elif mutation=='link':
        original=profile.with_name('original.json');profile.rename(original);profile.symlink_to(original)
    elif mutation=='hardlink':os.link(profile,profile.with_name('linked.json'))
    elif mutation=='duplicate':profile.write_text('{"schema_version":1,"schema_version":2}')
    elif mutation=='unknown':value['unexpected']='private-sentinel';profile.write_text(json.dumps(value))
    elif mutation=='credential_value':value['database']['password']='private-sentinel';profile.write_text(json.dumps(value))
    elif mutation=='malformed':profile.write_text('private-sentinel')
    assert entrypoint(['--config',str(profile),'health'])==2
    error=json.loads(capsys.readouterr().err)
    assert error['code'] and error['next_step']
    assert 'private-sentinel' not in json.dumps(error) and 'Traceback' not in json.dumps(error)


def test_existing_profile_is_preserved(profile):
    before=profile.read_bytes()
    with pytest.raises(StartupError,match='already exists'):
        configure(Namespace(output=str(profile),host='localhost',port=17791,graph='different',password_file='/tmp/reference',session_root='/tmp/session-reference',console_port=17806,context=None))
    assert profile.read_bytes()==before


def test_configure_protects_only_its_default_application_directory_after_bootstrap(tmp_path,monkeypatch):
    import subprocess
    import sys
    root=Path(__file__).resolve().parents[3]
    base=tmp_path/'config';base.mkdir(mode=0o755);base.chmod(0o755)
    monkeypatch.setenv('XDG_CONFIG_HOME',str(base))
    subprocess.run([sys.executable,str(root/'deploy/bootstrap.py'),str(base/'aevora/local')],check=True,capture_output=True)
    (base/'aevora').chmod(0o775)
    args=Namespace(output=None,host='127.0.0.1',port=17790,graph='ordinary_project',
        password_file=str(base/'aevora/local/falkordb.password'),session_root=str(tmp_path/'sessions'),console_port=17805,context=None)
    configure(args)
    assert (base/'aevora').stat().st_mode & 0o777==0o700
    assert base.stat().st_mode & 0o777==0o755
    unrelated=tmp_path/'other';unrelated.mkdir(mode=0o755);unrelated.chmod(0o755)
    args.output=str(unrelated/'host.json')
    with pytest.raises(StartupError):configure(args)
    assert unrelated.stat().st_mode & 0o777==0o755


def test_missing_configuration_has_an_actionable_public_error(tmp_path,monkeypatch,capsys):
    from aevora.cli import entrypoint
    for key in (*DB_KEYS,'AEVORA_CONFIG'):monkeypatch.delenv(key,raising=False)
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path/'unconfigured'))
    assert entrypoint(['health'])==2
    value=json.loads(capsys.readouterr().err)
    assert value['code']=='HOST_CONFIG_REQUIRED' and 'configure' in value['next_step']


def test_mutable_selector_cannot_escape_its_private_session_root(tmp_path):
    root=tmp_path/'sessions';root.mkdir(mode=0o700)
    path=root/'current.json'
    path.write_text(json.dumps({'schema_version':'aevora.local-session/1','directory':'../elsewhere','run_id':'actual-run'}));path.chmod(0o600)
    with pytest.raises(StartupError,match='selector is invalid'):current_session(root)


def test_malformed_selector_and_linked_owner_lock_have_recovery_hints(tmp_path):
    root=tmp_path/'sessions';root.mkdir(mode=0o700)
    path=root/'current.json';path.write_text('private-sentinel');path.chmod(0o600)
    with pytest.raises(StartupError) as result:current_session(root)
    assert result.value.code=='SESSION_SELECTOR_INVALID' and result.value.next_step
    assert 'private-sentinel' not in str(result.value.public())
    (root/'.owner.lock').symlink_to(tmp_path/'unrelated')
    with pytest.raises(StartupError) as result:
        with SessionLease(root,Namespace(run_id=None)):pass
    assert result.value.code=='SESSION_LOCK_UNAVAILABLE' and result.value.next_step
    assert not (tmp_path/'unrelated').exists()


def test_session_lock_does_not_replace_an_active_owner(tmp_path):
    # Short external directory is required by the real Unix socket path bound.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='av-lock-') as directory:
        args=Namespace(run_id=None)
        with SessionLease(directory,args):
            before=set(Path(directory).iterdir())
            with pytest.raises(StartupError) as result:
                with SessionLease(directory,Namespace(run_id=None)):pass
            assert result.value.code=='SESSION_ALREADY_RUNNING'
            assert set(Path(directory).iterdir())==before
