"""Explicit Host JSON profiles; only secret file references, never secret values.

No shell evaluation or project-directory discovery. Existing DB environment
remains an explicit deployment interface; profiles are loaded by Host entry points.
"""
import json
import os
from pathlib import Path
import stat
from .models import PUBLIC_CONTEXT_FACTS, normalize_context, validate_id
from .startup import StartupError

SCHEMA = 'aevora.host-config/1'
DB_KEYS = ('AEVORA_FALKORDB_HOST', 'AEVORA_FALKORDB_PORT', 'AEVORA_FALKORDB_GRAPH', 'AEVORA_FALKORDB_PASSWORD_FILE')


def default_path():
    base = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))
    return base/'aevora/host.json'


def private_directory(path, *, create=False, protect_owned=False):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise StartupError('PRIVATE_PATH_REQUIRED', 'Host state paths must not contain links.', 'Choose an ordinary private directory outside source and evidence archives.')
    if create:
        try: path.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError:
            raise StartupError('PRIVATE_DIRECTORY_UNAVAILABLE', 'Host state directory could not be created.', 'Choose an owned writable private directory outside source and evidence archives.') from None
    if protect_owned:
        # Only configure's default application directory opts in. Bootstrap may
        # have created this parent with the caller's umask (e.g. 0755/0775).
        # Never chmod XDG_CONFIG_HOME or a caller-selected --output directory.
        try:
            descriptor = os.open(path, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                if os.fstat(descriptor).st_uid != os.getuid(): raise PermissionError()
                os.fchmod(descriptor, 0o700)
            finally: os.close(descriptor)
        except OSError:
            raise StartupError('PRIVATE_DIRECTORY_PERMISSIONS', 'The default Aevora configuration directory could not be protected.', 'Check the directory owner, or use --output in another owned mode-0700 directory.') from None
    try: info = path.lstat()
    except OSError:
        raise StartupError('PRIVATE_DIRECTORY_MISSING', 'Host state directory is missing.', 'Run aevora configure or choose an existing owned mode-0700 directory.') from None
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise StartupError('PRIVATE_DIRECTORY_PERMISSIONS', 'Host state directory must be owned by this user with mode 0700.', 'Check the chosen directory owner and permissions; do not change unrelated directories.')
    return path


def read_private_json(path, maximum=65536):
    path = Path(path).absolute()
    private_directory(path.parent)
    if path.is_symlink():
        raise StartupError('PRIVATE_FILE_REQUIRED', 'Linked Host state files are refused.', 'Use an ordinary owned mode-0600 file.')
    fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or not 1 <= info.st_size <= maximum:
            raise StartupError('PRIVATE_FILE_PERMISSIONS', 'Host state must be a bounded owned single-link mode-0600 file.', 'Check the selected file owner, permissions and type.')
        raw = os.read(fd, maximum+1)
        after = os.fstat(fd)
        if len(raw) != info.st_size or (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns) != (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise StartupError('HOST_STATE_CHANGED', 'Host state changed during reading.', 'Retry after the writer has finished.')
    finally: os.close(fd)
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise ValueError('Duplicate key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def absolute_path(value):
    if not isinstance(value, str) or not value or '\0' in value or not Path(value).is_absolute():
        raise ValueError('Absolute path required')
    return str(Path(value))


def validate_profile(value):
    try:
        if not isinstance(value, dict) or set(value) != {'schema_version','database','session','console'} or value['schema_version'] != SCHEMA: raise ValueError()
        db, session, console = value['database'], value['session'], value['console']
        if set(db) != {'host','port','graph','password_file'} or set(session) != {'root','public_context'} or set(console) != {'port'}: raise ValueError()
        if db['host'] not in {'127.0.0.1','localhost'}: raise ValueError()
        for port in (db['port'], console['port']):
            if type(port) is not int or not 1024 <= port <= 65535: raise ValueError()
        validate_id(db['graph']); absolute_path(db['password_file']); absolute_path(session['root'])
        facts = normalize_context(session['public_context'])
        if set(facts)-PUBLIC_CONTEXT_FACTS: raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise StartupError('HOST_CONFIG_INVALID', 'Host profile does not match the public configuration schema.', 'Use aevora configure to create a complete profile with database, session and Console settings.') from None
    return value


def load_profile(path=None, *, use_default=True):
    selected = path or os.environ.get('AEVORA_CONFIG')
    if selected is None:
        if not use_default or any(key in os.environ for key in DB_KEYS): return None
        candidate = default_path()
        if not candidate.exists() and not candidate.is_symlink(): return None
        selected = candidate
    try: return validate_profile(read_private_json(selected))
    except StartupError: raise
    except FileNotFoundError:
        raise StartupError('HOST_CONFIG_NOT_FOUND', 'Selected Host profile was not found.', 'Run aevora configure, or select an existing profile with --config PATH.') from None
    except (OSError, ValueError, TypeError):
        raise StartupError('HOST_CONFIG_UNREADABLE', 'Selected Host profile could not be read as protected JSON.', 'Check --config, ownership, mode 0700/0600 and the documented schema.') from None


def prepare_environment(path=None, *, use_default=True):
    profile = load_profile(path, use_default=use_default)
    if profile:
        db = profile['database']
        os.environ.update(dict(zip(DB_KEYS, [db['host'],str(db['port']),db['graph'],db['password_file']])))
    return profile


def configure(args):
    profile = validate_profile({'schema_version': SCHEMA,
        'database': {'host': args.host, 'port': args.port, 'graph': args.graph, 'password_file': str(Path(args.password_file).expanduser().absolute())},
        'session': {'root': str(Path(args.session_root).expanduser().absolute()), 'public_context': {}},
        'console': {'port': args.console_port}})
    if args.context:
        from .cli import read_json
        profile['session']['public_context'] = read_json(args.context)
        validate_profile(profile)
    target = Path(args.output).expanduser().absolute() if args.output else default_path().absolute()
    private_directory(target.parent, create=True, protect_owned=not args.output)
    # Configuration creation is exclusive too; changing a profile is an explicit edit.
    try: fd = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise StartupError('HOST_CONFIG_EXISTS', 'A Host profile already exists at the selected location.', 'Keep it and run health; edit it explicitly or choose --output PATH for a separate project.') from None
    except OSError:
        raise StartupError('HOST_CONFIG_UNWRITABLE', 'The Host profile could not be created safely.', 'Choose an owned writable mode-0700 configuration directory and an unused filename.') from None
    with os.fdopen(fd, 'w') as output: json.dump(profile, output, indent=2); output.write('\n')
    return {'status':'CONFIGURED', 'config':str(target), 'console_url':'http://127.0.0.1:'+str(args.console_port),
            'next_step':'Run aevora health and aevora serve; new terminals load the default profile automatically. Use --config PATH for a separate profile.'}
