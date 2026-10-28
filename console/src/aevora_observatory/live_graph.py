"""Request scoped, paged reads using the official Core repository.

Only identity/count queries scan the project. Payloads, including those read by
Core's publication gate, share one budget. No resolver or graph writes run here.
"""
import base64
import json
import re
import time

from aevora.graph_repository import GraphRepository
from aevora.models import GraphError, LIFECYCLE_LABELS, validate_id
from ._public_projection import project

MAX_NODES = 500
MAX_EDGES = 1200
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_QUERIES = 4096
READ_SECONDS = 10
PAGE_KEYS = frozenset({'sessions', 'queries', 'experiences', 'candidates',
                       'timeline', 'recorded_decisions', 'trusted', 'external', 'graph'})


def decode_cursor(token, run, experience):
    if token is None:
        return {}
    try:
        if len(token) > 3800 or not re.fullmatch(r'[A-Za-z0-9_-]+', token):
            raise ValueError()
        value = json.loads(base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)))
        if (set(value) != {'v', 'run', 'experience', 'after'} or value['v'] != 1
                or value['run'] != run or value['experience'] != experience
                or not isinstance(value['after'], dict) or set(value['after']) - PAGE_KEYS):
            raise ValueError()
        for identity in value['after'].values():
            validate_id(identity)
        return value['after']
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError('Invalid page cursor') from None


def encode_cursor(after, run, experience):
    raw = json.dumps({'v': 1, 'run': run, 'experience': experience, 'after': after},
                     separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


class BoundedRepository(GraphRepository):
    """Core methods retain their validation and run inside the Console budget."""

    def __init__(self, repository):
        self.__dict__.update(repository.__dict__)
        self.deadline = time.monotonic() + READ_SECONDS
        self.read_queries = self.payload_bytes = self.read_edges = 0
        self.nodes = {}
        self.checked_edges = set()

    def query(self, statement, params=None, *, read_only=True):
        if not read_only:
            raise GraphError('Console repository is read only')
        remaining = self.deadline - time.monotonic()
        self.read_queries += 1
        if remaining <= 0 or self.read_queries > MAX_QUERIES:
            raise OverflowError('Request query budget exceeded')
        self.query_timeout_ms = min(self.query_timeout_ms, max(1, int(remaining * 1000)))
        # All payload projections used by Core inspect/get_node/require_edge are
        # scalar columns. Guard them in DB before SDK result materialization.
        prefix, marker, projection = statement.rpartition('RETURN ')
        payload_column = {
            'n.payload_json,n.payload_sha256': ('n.payload_json', 0),
            'r.id,r.payload_json,r.payload_sha256': ('r.payload_json', 1),
        }.get(projection)
        if '.payload_json' in projection and payload_column is None:
            raise GraphError('Unsupported Core payload projection')
        params = dict(params or {})
        if payload_column:
            column, index = payload_column
            params['console_chars'] = min(256 * 1024, (MAX_PAYLOAD_BYTES - self.payload_bytes) // 8)
            projection = projection.replace(column, f'CASE WHEN size({column})<=$console_chars THEN {column} ELSE null END')
            statement = prefix + marker + projection
            statement += ' LIMIT 2'
        result = super().query(statement, params)
        if payload_column:
            # Each returned payload column is consumed by the existing Core
            # validator. Count bytes before any further read or JSON decoding.
            for row in result:
                raw = row[index]
                if not isinstance(raw, str):
                    raise OverflowError('Payload exceeds bounded read')
                self.payload_bytes += len(raw.encode('utf-8'))
                if self.payload_bytes > MAX_PAYLOAD_BYTES:
                    raise OverflowError('Request payload budget exceeded')
        return result

    def get_node(self, label, record_id, *, public=False):
        key = (label, record_id)
        if key not in self.nodes and len(self.nodes) >= MAX_NODES:
            raise OverflowError('Request node budget exceeded')
        # LifecycleHead is mutable: Core's final head check must reach the DB.
        # Keep only its latest observation for distinct-node accounting; each
        # read still passes through query(), charging payload/time/query budgets.
        if label == 'LifecycleHead' or key not in self.nodes:
            self.nodes[key] = super().get_node(label, record_id)
        value = self.nodes[key]
        if public and value is not None:
            from aevora.models import public_record
            return public_record(label, value)
        return value

    def require_edge(self, edge_type, source_label, source_id, target_label, target_id):
        key = (edge_type, source_label, source_id, target_label, target_id)
        if key not in self.checked_edges:
            self.charge_edges(1)
            super().require_edge(*key)
            self.checked_edges.add(key)

    def charge_edges(self, count):
        self.read_edges += count
        if self.read_edges > MAX_EDGES:
            raise OverflowError('Request edge budget exceeded')


class LivePages:
    def __init__(self, repo, *, run=None, experience=None, limit=20, offset=0, after=None):
        self.repo = repo
        self.run = run
        self.experience = experience
        self.limit = limit
        self.offset = offset
        self.after = after or {}
        self.pagination = {}
        self.params = {'run': run, 'experience': experience}

    def page(self, key, match, expression='n.id', where=None, *, limit=None):
        limit = limit or self.limit
        predicates = list(where or [])
        after = self.after.get(key)
        if after:
            predicates.append(expression + '>$after')
        params = {**self.params, 'after': after, 'skip': self.offset, 'take': limit + 1}
        rows = self.repo.query(match + (' WHERE ' + ' AND '.join(predicates) if predicates else '')
                               + f' RETURN DISTINCT {expression} AS identity ORDER BY identity SKIP $skip LIMIT $take', params)
        more = len(rows) > limit
        ids = [r[0] for r in rows[:limit]]
        next_after = {**self.after, key: ids[-1]} if more else None
        self.pagination[key] = {'limit': limit, 'offset': self.offset, 'has_more': more,
                                'next_cursor': encode_cursor(next_after, self.run, self.experience) if more else None,
                                'order': 'identity ASC'}
        return ids

    def records(self, key, labels, *, where=None, match='MATCH (n)', limit=None):
        predicates = ['(' + ' OR '.join('n:' + label for label in labels) + ')'] + list(where or [])
        ids = self.page(key, match, where=predicates, limit=limit)
        return self.load(ids)

    def load(self, ids):
        if not ids:
            return []
        headers = self.repo.query('MATCH (n) WHERE n.id IN $ids RETURN n.id,labels(n) ORDER BY n.id LIMIT $take',
                                  {'ids': ids, 'take': len(ids) + 1})
        if len(headers) != len(ids) or any(len(labels) != 1 for _, labels in headers):
            raise GraphError('Graph identity is absent or ambiguous')
        result = []
        for identity, labels in headers:
            if labels[0] not in LIFECYCLE_LABELS:
                raise GraphError('Unknown graph label')
            value = self.repo.get_node(labels[0], identity)
            if value is None:
                raise GraphError('Graph changed during read')
            result.append((labels[0], value))
        return result

    def public(self, key, labels, *, run_scoped=False, where=None, match='MATCH (n)'):
        predicates = list(where or [])
        if run_scoped and self.run is not None:
            predicates.append('n.run_id=$run')
        values = self.records(key, labels, where=predicates, match=match)
        if run_scoped and self.run is not None and any(v.get('run_id') != self.run for _, v in values):
            raise GraphError('Run property differs from stored record')
        return [project(label, value) for label, value in values]

    def graph(self):
        cap = min(self.limit, 64)
        truncated = False
        if self.experience:
            values = self.load([self.experience]) if self.repo.get_node('Experience', self.experience) else []
            ids = [v['id'] for _, v in values]
            front = ids[:]
            # Fixed-depth BFS, capped at each step. Never enumerate paths.
            for _ in range(3):
                if not front or len(ids) >= 64:
                    break
                rows = self.repo.query('MATCH (s)-[r]-(t) WHERE s.id IN $front AND NOT t.id IN $seen '
                    'AND type(r) IN $relations RETURN DISTINCT t.id ORDER BY t.id LIMIT $take',
                    {'front': front, 'seen': ids, 'take': 65 - len(ids), 'relations': [
                        'HAS_REVISION', 'USES_RULE', 'REQUIRES', 'SUPPORTED_BY', 'COUNTEREXAMPLE',
                        'OBSERVED_OUTCOME', 'VERIFIES', 'IN_CONTEXT', 'FOR_TASK', 'PUBLISHED_FROM',
                        'HAS_LIFECYCLE', 'HAS_CANDIDATE_EVENT']})
                room = 64 - len(ids)
                truncated |= len(rows) > room
                front = [r[0] for r in rows[:room]]
                ids.extend(front)
            values = self.load(ids)
            if front:
                truncated |= bool(self.repo.query('MATCH (s)-[r]-(t) WHERE s.id IN $front AND NOT t.id IN $seen '
                    'RETURN t.id LIMIT 1', {'front': front, 'seen': ids}))
            self.pagination['graph'] = {'limit': 64, 'has_more': truncated, 'next_cursor': None,
                                        'order': 'bounded breadth first, identity ASC', 'depth': 3}
            total = None  # Local neighborhood, never claim a full project total.
        else:
            values = self.records('graph', sorted(LIFECYCLE_LABELS - {'Schema'}),
                                  where=['n.run_id=$run'] if self.run else [], limit=cap)
            if self.run and any(v.get('run_id') != self.run for _, v in values):
                raise GraphError('Run property differs from stored record')
            ids = [v['id'] for _, v in values]
            total = self.repo.query('MATCH (n)' + (' WHERE n.run_id=$run' if self.run else ' WHERE NOT n:Schema')
                                    + ' RETURN count(n)', self.params)[0][0]
            truncated = self.pagination['graph']['has_more'] or bool(self.after.get('graph') or self.offset)
            if self.run:
                # QuerySnapshot/Experience/head/event nodes have no run_id of
                # their own. Include actual immediate neighbors of this page's
                # Run records, while excluding records owned by another Run.
                self.pagination['graph']['total_seed_nodes'] = total
                self.pagination['graph']['depth'] = 1
                room = 64 - len(ids)
                neighbors = self.repo.query('MATCH (s)-[r]-(t) WHERE s.id IN $ids AND NOT t.id IN $ids '
                    'AND (t.run_id IS NULL OR t.run_id=$run) RETURN DISTINCT t.id ORDER BY t.id LIMIT $take',
                    {'ids': ids, 'run': self.run, 'take': room + 1}) if ids else []
                truncated |= len(neighbors) > room
                ids.extend(r[0] for r in neighbors[:room])
                values = self.load(ids)
                if any(v.get('run_id') not in {None, self.run} for _, v in values):
                    raise GraphError('Run neighbor property differs from stored record')
                total = None
        remaining_edges = MAX_EDGES - self.repo.read_edges
        edges = self.repo.query('MATCH (s)-[r]->(t) WHERE s.id IN $ids AND t.id IN $ids '
            'RETURN s.id,type(r),r.id,r.payload_sha256,t.id ORDER BY s.id,r.id LIMIT $take',
            {'ids': ids, 'take': remaining_edges + 1}) if ids else []
        truncated |= len(edges) > remaining_edges
        self.repo.charge_edges(min(len(edges), remaining_edges))
        from aevora.models import digest
        return {'nodes': [{'id': v['id'], 'label': label, 'public': project(label, v),
                           'stored_payload_sha256': digest(v)} for label, v in values],
                'edges': [dict(zip(['source', 'relation', 'id', 'stored_payload_sha256', 'target'], e))
                          for e in edges[:remaining_edges]],
                'status': 'PARTIAL' if truncated else 'AVAILABLE' if values else 'EMPTY',
                'total_nodes': total, 'total_edges': None, 'node_limit': 64,
                'scope': 'EXPERIENCE_NEIGHBORHOOD' if self.experience else 'RUN_NEIGHBORHOOD' if self.run else 'PROJECT_PAGE',
                'disclosure': 'Actual bounded local read; omitted nodes and edges are not inferred.'}
