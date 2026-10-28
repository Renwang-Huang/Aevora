"""Trusted private-pipe adapter for ExperienceService; never an Agent RPC server."""
from __future__ import annotations

import json
import math
import os
import struct
import sys

MAX_FRAME = 262144
MAX_RESULT = MAX_FRAME // 4


class RunContextConflict(ValueError):
    """An existing Run cannot acquire another trusted factual context."""


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate key')
            result[key] = value
        return result
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    if not isinstance(value, dict):
        raise ValueError('Object required')
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > 20000 or depth > 16:
            raise ValueError('JSON shape bound')
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError('Finite numbers required')
        if isinstance(item, str):
            item.encode('utf-8')
        if isinstance(item, dict):
            pending.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            pending.extend((v, depth + 1) for v in item)
    return value


def exact_read(stream, count):
    result = bytearray()
    while len(result) < count:
        part = stream.read(count - len(result))
        if not part:
            raise EOFError()
        result.extend(part)
    return bytes(result)


def read_packet(stream):
    size = struct.unpack('>I', exact_read(stream, 4))[0]
    if not 0 < size <= MAX_FRAME:
        raise ValueError('Frame bound')
    return strict_json(exact_read(stream, size))


def write_packet(stream, value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
    if len(raw) > MAX_FRAME:
        raise ValueError('Output frame bound')
    stream.write(struct.pack('>I', len(raw)) + raw)
    stream.flush()


def service_from_bootstrap(boot, repository):
    from .mcp_server import ExperienceService
    from .backend_guard import backend_id
    fields = {'schema_version', 'backend_id', 'workspace_id', 'run_id', 'facts',
              'facts_version', 'facts_source', 'enable_proposals'}
    if set(boot) != fields or boot['schema_version'] != 'aevora.worker-bootstrap/1':
        raise ValueError('Invalid bootstrap')
    identity = backend_id(os.environ['AEVORA_FALKORDB_HOST'],
                          int(os.environ['AEVORA_FALKORDB_PORT']), os.environ['AEVORA_FALKORDB_GRAPH'])
    if boot['backend_id'] != identity or boot['workspace_id'] != identity or boot['facts_version'] != 'public-context/1' or boot['facts_source'] != 'protected_host_profile':
        raise ValueError('Invalid Run binding')
    return ExperienceService(run_id=boot['run_id'], public_context=boot['facts'],
        repository=repository, enable_proposals=boot['enable_proposals'])


def preflight(repository):
    from .models import LIFECYCLE_SCHEMA_VERSION, schema_catalog, GraphUnavailable
    if repository.get_node('Schema', LIFECYCLE_SCHEMA_VERSION) is None:
        raise GraphUnavailable('Lifecycle schema must be initialized by trusted maintenance')
    required = {(label, kind, tuple(sorted(props)))
        for label in schema_catalog(LIFECYCLE_SCHEMA_VERSION)['labels']
        for kind, props in [('UNIQUE', ['id']), ('MANDATORY', ['id', 'payload_json', 'payload_sha256'])]}
    constraints = repository._graph.list_constraints()
    actual = {(c.get('label'), c.get('type'), tuple(sorted(c.get('properties', []))))
              for c in constraints if c.get('entitytype') == 'NODE' and c.get('status') == 'OPERATIONAL'}
    if not required <= actual:
        raise GraphUnavailable('Required graph constraints unavailable')
    repository.state_fingerprint()


def bind_run_history(service, boot):
    from .models import digest
    rows = service.repository.query('MATCH(n:Query {run_id:$run}) RETURN n.id LIMIT 4097',
                                    {'run': service.run_id})
    if len(rows) > 4096:
        raise RunContextConflict('Run history exceeds bounded authority verification')
    expected = digest(service.public_context)
    for row in rows:
        query = service.repository.get_node('Query', row[0])
        if (not query or query.get('run_id') != service.run_id
                or query.get('context_authority') != 'TRUSTED_PINNED_PUBLIC_FACTS_ONLY'
                or 'pinned_public_context' not in query
                or digest(query['pinned_public_context']) != expected):
            raise RunContextConflict('Run factual authority conflicts with stored history')
    return digest({key: boot[key] for key in ('backend_id', 'workspace_id', 'run_id',
        'facts_version', 'facts_source')} | {'facts': service.public_context})


def execute(service, request):
    allowed = {'schema_version', 'request_id', 'operation', 'arguments'}
    if set(request) != allowed or request['schema_version'] != 'aevora.worker-request/1':
        raise ValueError('Invalid request')
    args = request['arguments']
    operation = request['operation']
    if not isinstance(args, dict):
        raise ValueError('Arguments object required')
    if operation == 'resolve_experience' and set(args) == {'task_context'}:
        return service.resolve_experience(args['task_context'])
    if operation == 'read_observation_sources':
        raise ValueError('Observation source reads require the native SQLite runtime')
    if operation=='search_observations' and 'query' in args and not set(args)-{'query','limit'}:
        return service.search_observations(args)
    if operation == 'build_evidence_bundle' and 'experience_id' in args and not set(args) - {'experience_id', 'query_id'}:
        return service.build_evidence_bundle(args['experience_id'], args.get('query_id'))
    if operation == 'record_decision' and set(args) == {'decision'}:
        return service.record_decision(args['decision'])
    if operation == 'record_observation_use' and set(args) == {'report'}:
        raise ValueError('Observation usage reports require the native SQLite runtime')
    if operation == 'propose_experience' and set(args) == {'proposal'}:
        from .proposal_contract import CandidateProposal
        return service.propose_experience(CandidateProposal.model_validate(args['proposal']).model_dump(exclude_none=True))
    raise ValueError('Operation or arguments refused')


def main():
    from .graph_repository import GraphRepository
    from .models import GraphUnavailable, GraphError
    repository = None
    try:
        # A standalone invocation cannot become an unmanaged generic Worker.
        if os.environ.get('AEVORA_BACKEND_LOCK_FD') != '3':
            return 2
        boot = read_packet(sys.stdin.buffer)
        repository = GraphRepository.from_environment()
        # Validate inherited ownership before READY, including read-only tools.
        with repository._write_guard():
            pass
        service = service_from_bootstrap(boot, repository)
        preflight(repository)
        binding = bind_run_history(service, boot)
        write_packet(sys.stdout.buffer, {'schema_version': 'aevora.worker-response/1',
            'status': 'READY', 'context_sha256': binding})
        seen = set()
        while True:
            try:
                request = read_packet(sys.stdin.buffer)
            except EOFError:
                break
            identity = request.get('request_id')
            if not isinstance(identity, str) or len(identity) != 64 or identity in seen or len(seen) >= 4096:
                raise ValueError('Request replay or bound')
            int(identity, 16)
            seen.add(identity)
            response = {'schema_version': 'aevora.worker-response/1', 'request_id': identity}
            try:
                result = execute(service, request)
                raw = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
                if len(raw) > MAX_RESULT:
                    response.update(status='UNKNOWN', error='AEVORA_OPERATION_UNKNOWN')
                else:
                    response.update(status='COMPLETED', result=result)
            except GraphUnavailable:
                response.update(status='FAILED_KNOWN', error='AEVORA_GRAPH_UNAVAILABLE')
            except GraphError:
                response.update(status='FAILED_KNOWN', error='AEVORA_GRAPH_RECORD_ERROR')
            except (ValueError, TypeError):
                response.update(status='FAILED_KNOWN', error='AEVORA_INVALID_OR_UNAUTHORIZED_INPUT')
            except Exception:
                response.update(status='UNKNOWN', error='AEVORA_OPERATION_UNKNOWN')
            write_packet(sys.stdout.buffer, response)
        return 0
    except RunContextConflict:
        write_packet(sys.stdout.buffer, {'schema_version': 'aevora.worker-response/1',
            'status': 'REJECTED', 'error': 'AEVORA_RUN_CONTEXT_CONFLICT'})
        return 2
    except Exception:
        # No exception values, tracebacks, secrets or malformed output on pipes.
        return 2
    finally:
        if repository is not None:
            repository.close()


if __name__ == '__main__':
    raise SystemExit(main())
