class CustomException(Exception):
    """Single exception class for all Clipnera errors."""

    def __init__(
        self, message: str, code: str = "UNKNOWN", status_code: int = 500, extra: dict | None = None
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        # Additional fields for the response body, e.g. which feature was refused.
        self.extra = extra or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            **self.extra,
            "error": self.code,
            "message": self.message,
        }
