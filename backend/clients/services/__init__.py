from .s3 import S3
from .email import EmailClient

Registry = dict[str, type]

_REGISTRY: Registry = {
    "s3": S3,
    "email": EmailClient,
}


def get_service(name: str):
    """Factory: returns an initialized service client."""
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise ValueError(f"Unknown service '{name}'. Available: {list(_REGISTRY)}")


__all__ = [
    "S3",
    "EmailClient",
    "get_service",
]
