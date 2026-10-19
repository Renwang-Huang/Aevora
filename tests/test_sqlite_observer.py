"""Real SQLite commit-boundary observations independent of candidate helpers."""
import sqlite3

import pytest

from evaluator import worker as module


@pytest.fixture
def observed(tmp_path):
    events = []
    observer = module.SQLiteObserver(lambda event, **metadata: events.append({"event": event, **metadata})).install()
    try:
        yield observer, events, tmp_path / "business.sqlite"
    finally:
        observer.uninstall()


@pytest.mark.parametrize("strategy", ["commit", "connection_sql", "cursor_sql", "context", "custom_context", "cursor_script", "connection_script"])
def test_real_commit_boundaries(observed, strategy):
    observer, events, database = observed
    connection = sqlite3.connect(database, isolation_level=None)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    events.clear()
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("INSERT INTO entries VALUES (1)")
    if strategy == "commit":
        connection.commit()
    elif strategy == "connection_sql":
        connection.execute("/* harmless comment */ COMMIT")
    elif strategy == "cursor_sql":
        connection.cursor().execute("END TRANSACTION")
    elif strategy == "context":
        connection.__exit__(None, None, None)
    elif strategy == "custom_context":
        # The current defect mechanism can choose this legal internal helper.
        def own_transaction_commit():
            connection.commit()
        own_transaction_commit()
    else:
        target = connection.cursor() if strategy == "cursor_script" else connection
        # Python's LEGACY executescript performs a real implicit COMMIT before
        # the script. An explicit additional COMMIT would correctly error.
        target.executescript("")
    assert [event["event"] for event in events] == ["before_commit", "transaction_committed"]
    assert events[0]["in_transaction"] is True
    assert events[1]["in_transaction"] is False
    with observer.original_connect(database) as outside:
        assert outside.execute("SELECT * FROM entries").fetchall() == [(1,)]
    connection.close()


def test_first_commit_in_script_notifies_before_second_transaction(observed):
    observer, events, database = observed
    connection = sqlite3.connect(database, isolation_level=None)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    captured = []
    def checkpoint(event, **metadata):
        events.append({"event": event, **metadata})
        if event == "transaction_committed":
            with observer.original_connect(database) as outside:
                captured.append(outside.execute("SELECT * FROM entries").fetchall())
    observer.notify = checkpoint
    connection.executescript("BEGIN IMMEDIATE;INSERT INTO entries VALUES (1);COMMIT;"
                             "BEGIN IMMEDIATE;INSERT INTO entries VALUES (2);COMMIT;")
    assert captured == [[(1,)], [(1,), (2,)]]
    connection.close()


@pytest.mark.parametrize("boundary", ["commit", "connection_sql", "cursor_sql", "context", "script"])
def test_failed_deferred_foreign_key_commit_is_never_called_committed(observed, boundary):
    observer, events, database = observed
    connection = sqlite3.connect(database, isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
    connection.execute("CREATE TABLE child(id INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED)")
    connection.execute("BEGIN")
    connection.execute("INSERT INTO child VALUES (1)")
    events.clear()
    with pytest.raises(sqlite3.IntegrityError):
        if boundary == "commit": connection.commit()
        elif boundary == "connection_sql": connection.execute("COMMIT")
        elif boundary == "cursor_sql": connection.cursor().execute("COMMIT")
        elif boundary == "context": connection.__exit__(None, None, None)
        else: connection.executescript("COMMIT;")
    if connection.in_transaction:
        connection.rollback()
    assert not [event for event in events if event["event"] == "transaction_committed"], events
    with observer.original_connect(database) as outside:
        assert outside.execute("SELECT * FROM child").fetchall() == []
    connection.close()


def test_rollback_is_not_commit(observed):
    _, events, database = observed
    connection = sqlite3.connect(database, isolation_level=None)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    connection.execute("BEGIN")
    connection.execute("INSERT INTO entries VALUES (1)")
    events.clear()
    connection.rollback()
    connection.execute("SELECT * FROM entries").fetchall()
    assert not events
    connection.close()


def test_connection_and_cursor_subclass_factory_are_preserved(observed):
    _, events, database = observed
    class CustomConnection(sqlite3.Connection):
        def execute(self, *args, **kwargs):
            self.execute_count = getattr(self, "execute_count", 0) + 1
            return super().execute(*args, **kwargs)
    class CustomCursor(sqlite3.Cursor):
        def execute(self, *args, **kwargs):
            self.execute_count = getattr(self, "execute_count", 0) + 1
            return super().execute(*args, **kwargs)
    connection = sqlite3.connect(database, factory=CustomConnection, isolation_level=None)
    assert isinstance(connection, CustomConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE entries(value INTEGER)")
    connection.execute("BEGIN")
    connection.execute("INSERT INTO entries VALUES (1)")
    cursor = connection.cursor(factory=CustomCursor)
    assert isinstance(cursor, CustomCursor)
    cursor.execute("COMMIT")
    assert cursor.execute_count == 1
    assert connection.execute_count == 3
    assert [event["event"] for event in events] == ["before_commit", "transaction_committed"]
    assert connection.execute("SELECT * FROM entries").fetchone()["value"] == 1
    connection.close()


@pytest.mark.parametrize("autocommit", [True, False])
def test_python312_autocommit_modes(observed, autocommit):
    observer, events, database = observed
    connection = sqlite3.connect(database, autocommit=autocommit)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    connection.commit()
    events.clear()
    connection.execute("INSERT INTO entries VALUES (1)")
    connection.commit()
    committed = [event for event in events if event["event"] == "transaction_committed"]
    assert len(committed) == 1, events
    assert committed[0]["in_transaction"] is False
    assert connection.in_transaction is (not autocommit)
    with observer.original_connect(database) as outside:
        assert outside.execute("SELECT * FROM entries").fetchall() == [(1,)]
    connection.close()


def test_autocommit_returning_not_prematurely_recorded(observed):
    observer, events, database = observed
    connection = sqlite3.connect(database, autocommit=True)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    events.clear()
    cursor = connection.execute("INSERT INTO entries VALUES (1),(2) RETURNING value")
    assert not [event for event in events if event["event"] == "transaction_committed"], events
    assert cursor.fetchone() == (1,)
    with observer.original_connect(database) as outside:
        assert outside.execute("SELECT * FROM entries").fetchall() == []
    assert not [event for event in events if event["event"] == "transaction_committed"], events
    assert cursor.fetchall() == [(2,)]
    assert len([event for event in events if event["event"] == "transaction_committed"]) == 1
    with observer.original_connect(database) as outside:
        assert outside.execute("SELECT * FROM entries").fetchall() == [(1,), (2,)]
    connection.close()


def test_candidate_trace_callback_is_preserved(observed):
    _, events, database = observed
    seen = []
    connection = sqlite3.connect(database, isolation_level=None)
    connection.set_trace_callback(seen.append)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    connection.execute("BEGIN")
    connection.execute("INSERT INTO entries VALUES (1)")
    connection.commit()
    connection.set_trace_callback(None)
    assert any(statement == "COMMIT" for statement in seen)
    assert len([event for event in events if event["event"] == "transaction_committed"]) == 1
    connection.close()


def test_callable_factory_preserves_business_and_marks_unavailable(observed):
    observer, events, database = observed
    connection = sqlite3.connect(database, factory=lambda *a, **kw: sqlite3.Connection(*a, **kw))
    connection.execute("CREATE TABLE entries(value INTEGER)")
    connection.execute("INSERT INTO entries VALUES (1)")
    connection.commit()
    assert observer.unavailable == [{"reason": "opaque_callable_connection_factory"}]
    assert not events
    connection.close()


@pytest.mark.parametrize("sql", ["COMMIT/*adjacent comment*/", "COMMIT--comment\n", "\ufeffCOMMIT", "END;"])
def test_sql_token_boundaries(observed, sql):
    _, events, database = observed
    connection = sqlite3.connect(database, isolation_level=None)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    connection.execute("BEGIN")
    connection.execute("INSERT INTO entries VALUES (1)")
    connection.cursor().execute(sql)
    assert [event["event"] for event in events] == ["before_commit", "transaction_committed"]
    connection.close()


def test_read_only_transaction_is_not_a_durable_write_observation(observed):
    _, events, database = observed
    connection = sqlite3.connect(database, isolation_level=None)
    connection.execute("BEGIN")
    connection.execute("SELECT 1").fetchall()
    connection.commit()
    assert not events
    connection.close()


def test_only_target_database_writes_emit_commit(tmp_path):
    target = tmp_path / "business.sqlite"
    events = []
    observer = module.SQLiteObserver(lambda event, **metadata: events.append(event), target).install()
    try:
        business = sqlite3.connect(target)
        business.execute("CREATE TABLE entries(value INTEGER)")
        auxiliary = sqlite3.connect(tmp_path / "cache.sqlite")
        auxiliary.execute("CREATE TABLE cache(value INTEGER)")
        auxiliary.execute("INSERT INTO cache VALUES (1)")
        auxiliary.commit()
        auxiliary.close()
        assert not events
        business.execute("INSERT INTO entries VALUES (1)")
        business.commit()
        business.close()
        assert events == ["before_commit", "transaction_committed"]
    finally:
        observer.uninstall()


def test_trigger_and_returning_commit_is_observed_only_after_statement_done(observed):
    observer, events, database = observed
    connection = sqlite3.connect(database, autocommit=True)
    connection.executescript("CREATE TABLE entries(value INTEGER);CREATE TABLE audit(value INTEGER);"
                             "CREATE TRIGGER copied AFTER INSERT ON entries BEGIN INSERT INTO audit VALUES(new.value);END;")
    events.clear()
    snapshots = []
    def checkpoint(event, **metadata):
        events.append({"event": event, **metadata})
        if event == "transaction_committed":
            with observer.original_connect(database) as outside:
                snapshots.append((outside.execute("SELECT * FROM entries").fetchall(),
                                  outside.execute("SELECT * FROM audit").fetchall()))
    observer.notify = checkpoint
    cursor = connection.execute("INSERT INTO entries VALUES (1),(2) RETURNING value")
    assert not events
    assert cursor.fetchone() == (1,)
    assert not events
    assert cursor.fetchall() == [(2,)]
    assert snapshots == [([(1,), (2,)], [(1,), (2,)])]
    connection.close()


def test_active_returning_cursor_prevents_other_statement_false_commit(observed):
    observer, events, database = observed
    connection = sqlite3.connect(database, autocommit=True)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    first = connection.execute("INSERT INTO entries VALUES (1),(2) RETURNING value")
    second = connection.execute("INSERT INTO entries VALUES (3),(4) RETURNING value")
    assert not events
    first.fetchall()
    assert not events
    with observer.original_connect(database) as outside:
        assert outside.execute("SELECT * FROM entries").fetchall() == []
    second.fetchall()
    assert len([event for event in events if event["event"] == "transaction_committed"]) == 1
    with observer.original_connect(database) as outside:
        assert outside.execute("SELECT * FROM entries").fetchall() == [(1,), (2,), (3,), (4,)]
    connection.close()


def test_control_notify_failure_is_recorded_as_incomplete_without_altering_commit(observed):
    observer, _, database = observed
    def unavailable_control(event, **metadata):
        raise RuntimeError("synthetic scheduling channel failure")
    observer.notify = unavailable_control
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    connection.execute("INSERT INTO entries VALUES (1)")
    connection.commit()
    assert observer.observation()["availability"] == "UNAVAILABLE"
    assert observer.errors and all(row["type"] == "RuntimeError" for row in observer.errors)
    with observer.original_connect(database) as outside:
        assert outside.execute("SELECT * FROM entries").fetchall() == [(1,)]
    connection.close()


def test_unbound_commit_followed_by_wrapped_close_is_proved(observed):
    observer, events, database = observed
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    connection.execute("INSERT INTO entries VALUES (1)")
    sqlite3.Connection.commit(connection)
    assert [row["event"] for row in events] == ["before_commit"]
    connection.close()
    assert [row["event"] for row in events] == ["before_commit", "transaction_committed"]
    assert events[-1]["boundary_source"] == "connection_close_after_commit"
    with observer.original_connect(database) as outside:
        assert outside.execute("SELECT * FROM entries").fetchall() == [(1,)]


def test_savepoint_commit_boundary_is_explicitly_unavailable(observed):
    observer, events, database = observed
    connection = sqlite3.connect(database, isolation_level=None)
    connection.execute("CREATE TABLE entries(value INTEGER)")
    connection.execute("SAVEPOINT s")
    connection.execute("INSERT INTO entries VALUES (1)")
    connection.execute("RELEASE s")
    assert observer.observation()["availability"] == "UNAVAILABLE"
    assert {"reason": "savepoint_commit_boundary"} in observer.unavailable
    connection.close()


def test_custom_connection_constructor_and_dict_row_factory_preserved(tmp_path):
    events = []
    target = tmp_path / "business.sqlite"
    observer = module.SQLiteObserver(lambda event, **metadata: events.append(event), target).install()
    class Factory(sqlite3.Connection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.row_factory = lambda cursor, row: dict(zip((column[0] for column in cursor.description), row))
            self.execute("CREATE TABLE entries(value INTEGER)")
    try:
        connection = sqlite3.connect(target, factory=Factory)
        connection.execute("INSERT INTO entries VALUES (1)")
        connection.commit()
        assert connection.execute("SELECT * FROM entries").fetchone() == {"value": 1}
        assert events == ["before_commit", "transaction_committed"]
        assert observer.observation()["availability"] == "AVAILABLE"
        connection.close()
    finally:
        observer.uninstall()


def _participant_transaction_workspace(tmp_path, strategy, boundary):
    from benchmark.episodes.episode_d import build_episode_d_fixture
    workspace = build_episode_d_fixture(tmp_path / "candidate", strategy=strategy)
    service = workspace / "app/service.py"
    service.write_text(service.read_text().replace("self.persistence.transaction()", "self.persistence.participant_transaction()"))
    endings = {
        "commit": "connection.commit()",
        "connection_sql": "connection.execute('COMMIT/*ordinary comment*/')",
        "cursor_sql": "connection.cursor().execute('END TRANSACTION')",
        "context": "connection.__exit__(None, None, None)",
        "subclass_factory": "connection.commit()",
        "unbound_commit": "sqlite3.Connection.commit(connection)",
    }
    connection_context = "self.connection()"
    extra = ""
    if boundary == "subclass_factory":
        extra = '''
class ParticipantConnection(sqlite3.Connection):
    def commit(self):
        return super().commit()
@contextmanager
def _participant_connection(self):
    connection = sqlite3.dbapi2.connect(self.db_path, factory=ParticipantConnection, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
    finally:
        connection.close()
SQLitePersistence.participant_connection = _participant_connection
'''
        connection_context = "self.participant_connection()"
    custom = f'''
{extra}
@contextmanager
def _participant_transaction(self):
    with {connection_context} as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            {endings[boundary]}
        except BaseException:
            connection.rollback()
            raise
SQLitePersistence.participant_transaction = _participant_transaction
'''
    persistence = workspace / "app/persistence.py"
    persistence.write_text(persistence.read_text() + custom)
    return workspace


@pytest.mark.parametrize("boundary", ["commit", "connection_sql", "cursor_sql", "context", "subclass_factory", "unbound_commit"])
@pytest.mark.parametrize("strategy", ["reference", "split-ledger"])
def test_real_worker_custom_helper_crash_distinguishes_atomic_and_split_commit(tmp_path, strategy, boundary):
    from evaluator.supervisor import WorkerSupervisor
    from evaluator.episode_d_oracle import inspect_episode_d_database
    workspace = _participant_transaction_workspace(tmp_path, strategy, boundary)
    supervisor = WorkerSupervisor(workspace, tmp_path / "data", tmp_path / "artifacts").start()
    try:
        supervisor.initialize({"widget": 5})
        crash = supervisor.crash_call(0, "create_order", "transaction_committed", order_id="custom", sku="widget", quantity=2)
        assert crash["availability"] == "AVAILABLE", crash
        assert crash["event"]["metadata"]["in_transaction"] is False
        assert crash["event"]["metadata"]["sqlite_observer_version"] == module.SQLiteObserver.VERSION
        assert crash["kill"]["worker_pidfd_exited"] is True
        assert crash["request_outcome"]["error"]["type"] == "RemoteExecutionError"
        supervisor.stop_all()
        audit = inspect_episode_d_database(tmp_path / "data/business.sqlite", data_dir=tmp_path / "data",
                                          expected_stock={"widget": 5})
        assert audit["orders"][0]["order_id"] == "custom"
        assert audit["inventory"][0]["reserved"] == 2
        assert audit["consistent"] is (strategy == "reference"), audit
        assert len(audit["ledger"]) == (1 if strategy == "reference" else 0)
    finally:
        supervisor.close()


@pytest.mark.parametrize("preface", ["read_transaction", "auxiliary_database"])
def test_real_worker_ignores_read_only_and_auxiliary_commit_before_atomic_business_write(tmp_path, preface):
    from benchmark.episodes.episode_d import build_episode_d_fixture
    from evaluator.supervisor import WorkerSupervisor
    from evaluator.episode_d_oracle import inspect_episode_d_database
    workspace = build_episode_d_fixture(tmp_path / "candidate", strategy="reference")
    prefixes = {
        "read_transaction": '''
    with self.persistence.connection() as connection:
        connection.execute("BEGIN")
        connection.execute("SELECT sku FROM inventory").fetchall()
        connection.commit()
''',
        "auxiliary_database": '''
    import sqlite3
    connection = sqlite3.connect("/data/cache.sqlite")
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS cache(value INTEGER)")
        connection.execute("INSERT INTO cache VALUES (1)")
        connection.commit()
    finally:
        connection.close()
''',
    }
    service = workspace / "app/service.py"
    service.write_text(service.read_text() + f'''
_participant_original_create = OrderFlow.create_order
def _participant_create(self, *args, **kwargs):
{prefixes[preface]}
    return _participant_original_create(self, *args, **kwargs)
OrderFlow.create_order = _participant_create
''')
    supervisor = WorkerSupervisor(workspace, tmp_path / "data", tmp_path / "artifacts").start()
    try:
        supervisor.initialize({"widget": 5})
        crash = supervisor.crash_call(0, "create_order", "transaction_committed", order_id="atomic", sku="widget", quantity=1)
        assert crash["availability"] == "AVAILABLE", crash
        supervisor.stop_all()
        audit = inspect_episode_d_database(tmp_path / "data/business.sqlite", data_dir=tmp_path / "data",
                                          expected_stock={"widget": 5})
        assert audit["consistent"] and len(audit["orders"]) == len(audit["ledger"]) == 1, audit
    finally:
        supervisor.close()
