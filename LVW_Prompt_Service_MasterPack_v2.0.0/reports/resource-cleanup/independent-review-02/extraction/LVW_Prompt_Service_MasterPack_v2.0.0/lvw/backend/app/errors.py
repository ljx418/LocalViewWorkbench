from __future__ import annotations


class AppError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400,
                 retryable: bool = False, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}
