"""Public persistent request and claim history; actual base tables, not views.

Claim issuance does not require an order row. Each token records its immutable
issuance payload/tick/deadline; renewal changes requests.deadline only. Decimal
TEXT avoids signed-64-bit timestamp overflow. Time is compared as Python ints.
"""


def _decimal(column):
    return (f"typeof({column}) = 'text' AND length({column}) > 0 "
            f"AND {column} NOT GLOB '*[^0-9]*' "
            f"AND ({column} = '0' OR substr({column},1,1) BETWEEN '1' AND '9')")


SCHEMA = (
    """CREATE TABLE IF NOT EXISTS requests (
        request_id TEXT PRIMARY KEY NOT NULL,
        order_id TEXT NOT NULL,
        sku TEXT NOT NULL REFERENCES inventory(sku),
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        status TEXT NOT NULL CHECK (status IN ('PENDING','COMPLETED','CANCELLED')),
        current_token TEXT,
        deadline TEXT CHECK (deadline IS NULL OR (""" + _decimal("deadline") + """)),
        receipt_json TEXT,
        CHECK ((current_token IS NULL) = (deadline IS NULL)),
        CHECK (status = 'PENDING' OR current_token IS NULL),
        CHECK ((status = 'PENDING' AND receipt_json IS NULL)
            OR (status IN ('COMPLETED','CANCELLED') AND receipt_json IS NOT NULL))
    )""",
    """CREATE TABLE IF NOT EXISTS request_claims (
        token TEXT PRIMARY KEY NOT NULL,
        request_id TEXT NOT NULL REFERENCES requests(request_id),
        order_id TEXT NOT NULL,
        sku TEXT NOT NULL REFERENCES inventory(sku),
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        issued_tick TEXT NOT NULL CHECK (""" + _decimal("issued_tick") + """),
        issued_deadline TEXT NOT NULL CHECK (""" + _decimal("issued_deadline") + """ )
    )""",
    "CREATE INDEX IF NOT EXISTS request_claims_request_idx ON request_claims(request_id)",
)


def initialize(connection):
    for statement in SCHEMA:
        connection.execute(statement)


def reset(connection):
    connection.execute("DROP TABLE IF EXISTS request_claims")
    connection.execute("DROP TABLE IF EXISTS requests")
