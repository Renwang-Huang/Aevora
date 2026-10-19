"""Persistent two-stage request API, used by independent shared-SQLite workers.

claim_request(request_id, order_id, sku, quantity, ttl) establishes a fixed
payload intent. CLAIM_GRANTED includes handle {request_id, token} and request;
CLAIM_BUSY includes request only. Claiming neither creates an order nor reserves
stock. Tokens are opaque unique issuance identities, not PIDs or owner names.

renew_request(handle, ttl) returns CLAIM_RENEWED, the same handle and request;
valid renewal extends at least max(current_deadline, now + ttl). Deadline
equality is expired. Issuance history is never rewritten by renewal.

complete_request(handle) returns a persistent receipt with outcome, request_id,
order_id, sku, quantity: COMPLETE_RESERVED or COMPLETE_DISCOVERED_CANCELLED.
Repeated completion discovers that receipt without duplicate inventory effects.
INSUFFICIENT_INVENTORY_RETRYABLE leaves PENDING, releases this claim and has no
new business effect. STALE_HANDLE/request_id rejects invalid authority; a
terminal receipt can instead be discovered read-only. Infrastructure errors
are distinct from business results.

cancel_request(request_id) returns persistent REQUEST_CANCELLED for unfinished
intent; COMPLETED-first returns ALREADY_COMPLETED/request_id/original receipt.
get_request(request_id) returns fixed payload, status, deadline(int/null) and
receipt(object/null), never its current token. COMPLETED/CANCELLED are terminal.
Payload conflict is checked before terminal discovery. Existing independent
orders are not cancelled by cancel_request; multiple intents can discover the
same matching order. A matching cancelled order is never reserved again.

Quantity/TTL are positive integers, excluding bool. Quantity follows the
existing SQLite INTEGER business domain. TTL has no artificial business
maximum; deadline uses canonical decimal TEXT and Python ints. Normal
bounded JSON transport/numeric decoding resources still apply. Production
Clock ticks are monotonic milliseconds; controlled shared time uses the public
ORDERFLOW_CLOCK_QUERY NOW protocol described in app.request_clock.
"""
from collections.abc import Mapping
import json
import uuid

from app import request_clock, request_schema
from app.errors import InsufficientInventory, InvalidInput
from app.persistence import validate_identifier, validate_quantity
from app.request_errors import RequestConflict, RequestNotFound


def _receipt(request, outcome):
    return {"outcome": outcome, **{key: request[key] for key in
            ("request_id", "order_id", "sku", "quantity")}}


def _public(request):
    return {**{key: request[key] for key in ("request_id", "order_id", "sku", "quantity", "status")},
            "deadline": None if request["deadline"] is None else int(request["deadline"]),
            "receipt": None if request["receipt_json"] is None else json.loads(request["receipt_json"])}


def _get(connection, request_id):
    row = connection.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,)).fetchone()
    if row is None:
        raise RequestNotFound(request_id)
    return dict(row)


def _handle(handle):
    if not isinstance(handle, dict) or set(handle) != {"request_id", "token"}:
        raise InvalidInput("handle must contain request_id and token")
    for key in ("request_id", "token"):
        validate_identifier(handle[key], key)
    return handle["request_id"], handle["token"]


class RequestAPI:
    """Public mixin preserving the existing OrderFlow facade and persistence."""

    def initialize(self, stock, reset=False):
        # Validate before destructive reset, preserving ordinary fixture errors.
        if not isinstance(stock, Mapping):
            raise InvalidInput("stock must map SKU strings to nonnegative integers")
        for sku, quantity in stock.items():
            validate_identifier(sku, "sku")
            validate_quantity(quantity, allow_zero=True)
        self.persistence.db_path.parent.mkdir(parents=True, exist_ok=True)
        if reset:
            with self.persistence.transaction() as connection:
                request_schema.reset(connection)
        super().initialize(stock, reset=reset)
        with self.persistence.transaction() as connection:
            request_schema.initialize(connection)

    def get_request(self, request_id):
        validate_identifier(request_id, "request_id")
        with self.persistence.connection() as connection:
            return _public(_get(connection, request_id))

    def claim_request(self, request_id, order_id, sku, quantity, ttl):
        for name, value in (("request_id", request_id), ("order_id", order_id), ("sku", sku)):
            validate_identifier(value, name)
        validate_quantity(quantity)
        validate_quantity(ttl)
        with self.persistence.transaction() as connection:
            row = connection.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,)).fetchone()
            if row is not None:
                request = dict(row)
                if (request["order_id"], request["sku"], request["quantity"]) != (order_id, sku, quantity):
                    raise RequestConflict("Request identity has different contents")
                if request["status"] != "PENDING":
                    return json.loads(request["receipt_json"])
            else:
                self.inventory.get(connection, sku)
                connection.execute("INSERT INTO requests(request_id,order_id,sku,quantity,status) "
                                   "VALUES(?,?,?,?,'PENDING')", (request_id, order_id, sku, quantity))
                request = _get(connection, request_id)
            tick = request_clock.now()
            if request["current_token"] is not None and tick < int(request["deadline"]):
                return {"outcome": "CLAIM_BUSY", "request": _public(request)}
            token, deadline = uuid.uuid4().hex, tick + ttl
            connection.execute("INSERT INTO request_claims(token,request_id,order_id,sku,quantity,"
                               "issued_tick,issued_deadline) VALUES(?,?,?,?,?,?,?)",
                               (token, request_id, order_id, sku, quantity, str(tick), str(deadline)))
            connection.execute("UPDATE requests SET current_token=?,deadline=? WHERE request_id=?",
                               (token, str(deadline), request_id))
            return {"outcome": "CLAIM_GRANTED", "handle": {"request_id": request_id, "token": token},
                    "request": _public(_get(connection, request_id))}

    @staticmethod
    def _claim(connection, request_id, token):
        row = connection.execute("SELECT * FROM request_claims WHERE request_id=? AND token=?",
                                 (request_id, token)).fetchone()
        return None if row is None else dict(row)

    @staticmethod
    def _accepted(request, claim, tick):
        return claim is not None and claim["request_id"] == request["request_id"]

    def renew_request(self, handle, ttl):
        request_id, token = _handle(handle)
        validate_quantity(ttl)
        with self.persistence.transaction() as connection:
            request = _get(connection, request_id)
            claim = self._claim(connection, request_id, token)
            if claim is None:
                return {"outcome": "STALE_HANDLE", "request_id": request_id}
            if request["status"] != "PENDING":
                return json.loads(request["receipt_json"])
            tick = request_clock.now()
            if not self._accepted(request, claim, tick):
                return {"outcome": "STALE_HANDLE", "request_id": request_id}
            deadline = max(int(request["deadline"] or "0"), tick + ttl)
            connection.execute("UPDATE requests SET current_token=?,deadline=? WHERE request_id=?",
                               (token, str(deadline), request_id))
            return {"outcome": "CLAIM_RENEWED", "handle": dict(handle),
                    "request": _public(_get(connection, request_id))}

    def complete_request(self, handle):
        request_id, token = _handle(handle)
        with self.persistence.transaction() as connection:
            request = _get(connection, request_id)
            claim = self._claim(connection, request_id, token)
            if claim is None:
                return {"outcome": "STALE_HANDLE", "request_id": request_id}
            if request["status"] == "COMPLETED":
                return json.loads(request["receipt_json"])
            tick = request_clock.now()
            if not self._accepted(request, claim, tick):
                return {"outcome": "STALE_HANDLE", "request_id": request_id}
            connection.execute("SAVEPOINT request_business")
            try:
                order = self.orders.create(connection, claim["order_id"], claim["sku"], claim["quantity"])
                if order["status"] == "cancelled":
                    outcome = "COMPLETE_DISCOVERED_CANCELLED"
                else:
                    self.inventory.reserve(connection, order["order_id"])
                    outcome = "COMPLETE_RESERVED"
            except InsufficientInventory:
                connection.execute("ROLLBACK TO request_business")
                connection.execute("RELEASE request_business")
                connection.execute("UPDATE requests SET current_token=NULL,deadline=NULL WHERE request_id=?",
                                   (request_id,))
                return _receipt(request, "INSUFFICIENT_INVENTORY_RETRYABLE")
            connection.execute("RELEASE request_business")
            receipt = _receipt(request, outcome)
            connection.execute("UPDATE requests SET status='COMPLETED',current_token=NULL,deadline=NULL,"
                               "receipt_json=? WHERE request_id=?", (json.dumps(receipt, sort_keys=True), request_id))
            return receipt

    def cancel_request(self, request_id):
        validate_identifier(request_id, "request_id")
        with self.persistence.transaction() as connection:
            request = _get(connection, request_id)
            if request["status"] == "COMPLETED":
                return {"outcome": "ALREADY_COMPLETED", "request_id": request_id,
                        "receipt": json.loads(request["receipt_json"])}
            if request["status"] == "CANCELLED":
                return json.loads(request["receipt_json"])
            receipt = _receipt(request, "REQUEST_CANCELLED")
            connection.execute("UPDATE requests SET status='CANCELLED',current_token=NULL,deadline=NULL,"
                               "receipt_json=? WHERE request_id=?", (json.dumps(receipt, sort_keys=True), request_id))
            return receipt
