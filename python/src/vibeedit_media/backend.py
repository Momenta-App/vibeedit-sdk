"""Shared optional backend primitives."""


class MissingBackendError(RuntimeError):
    """Raised when an optional media backend is required but unavailable."""

    def __init__(self, *, backend: str, message: str, install_hint: str | None = None):
        self.backend = backend
        self.install_hint = install_hint
        detail = f"{backend}: {message}"
        if install_hint:
            detail = f"{detail} {install_hint}"
        super().__init__(detail)
