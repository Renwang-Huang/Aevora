"""Public request business errors and a separate Clock infrastructure error."""
from app.errors import OrderFlowError


class RequestNotFound(OrderFlowError, LookupError):
    pass


class RequestConflict(OrderFlowError):
    pass


class ClockUnavailable(RuntimeError):
    """The shared time authority could not supply a valid bounded response."""
