from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from apps.api.app.common.schemas import ErrorEnvelope
from apps.api.app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
        *,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        logger.warning(
            "domain_error",
            extra={"error_code": exc.code, "status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorEnvelope(
                code=exc.code,
                message=exc.message,
                request_id=get_request_id(),
                details=exc.details,
            ).model_dump(mode="json"),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(_: Request, exc: HTTPException) -> JSONResponse:
        logger.warning(
            "http_exception",
            extra={"status_code": exc.status_code},
        )
        detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorEnvelope(
                code="http_error",
                message=str(detail.get("detail", exc.detail)),
                request_id=get_request_id(),
                details=detail,
            ).model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=ErrorEnvelope(
                code="internal_error",
                message="Внутренняя ошибка приложения",
                request_id=get_request_id(),
                details=None,
            ).model_dump(mode="json"),
        )
