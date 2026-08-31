from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI

from core.config import get_settings
from core.api_log_middleware import APILogMiddleware

settings = get_settings()


def register_middlewares(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
    app.add_middleware(APILogMiddleware)
