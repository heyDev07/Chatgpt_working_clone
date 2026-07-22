class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str | None = None):
        self.message = message or self.code
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class AuthError(AppError):
    status_code = 401
    code = "auth_error"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class ProviderError(AppError):
    status_code = 502
    code = "provider_error"


class StorageError(AppError):
    status_code = 502
    code = "storage_error"
