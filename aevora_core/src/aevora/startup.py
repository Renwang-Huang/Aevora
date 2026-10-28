"""Sanitized, actionable startup failures. Never include raw exception values."""
from .models import InvalidRecord


class StartupError(InvalidRecord):
    def __init__(self, code, reason, next_step):
        super().__init__(reason)
        self.code, self.reason, self.next_step = code, reason, next_step

    def public(self):
        return {'status': 'ERROR', 'error_type': type(self).__name__, 'code': self.code,
                'reason': self.reason, 'next_step': self.next_step}
