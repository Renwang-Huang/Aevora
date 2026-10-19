"""Business errors are distinct from SQLite or evaluator infrastructure errors."""


class OrderFlowError(Exception):
    """Base class for an unsuccessful business operation."""


class InvalidInput(OrderFlowError, ValueError):
    pass


class OrderNotFound(OrderFlowError, LookupError):
    pass


class InventoryNotFound(OrderFlowError, LookupError):
    pass


class OrderConflict(OrderFlowError):
    pass


class InsufficientInventory(OrderFlowError):
    pass


class InvalidOrderState(OrderFlowError):
    pass


class FixtureConflict(OrderFlowError):
    pass
