from .s3 import S3
from .email import EmailClient
from .sms import SMSClient

Registry = dict[str, type]

_REGISTRY: Registry = {
    "s3": S3,
    "email": EmailClient,
    "sms": SMSClient,
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
    "SMSClient",
    "get_service",
]
