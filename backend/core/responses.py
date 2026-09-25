"""The ``{data, message, error}`` response envelope.

Errors keep flowing through CustomException, whose handler already returns
``{error, message}``; successful responses wrap their payload here.
"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[str] = None


def ok(data: T, message: str | None = None) -> ApiResponse[T]:
    return ApiResponse(data=data, message=message)
