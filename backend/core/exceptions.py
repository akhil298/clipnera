class CustomException(Exception):
    """Single exception class for all Clipnera errors."""

    def __init__(self, message: str, code: str = "UNKNOWN", status_code: int = 500) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
        }
