from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.app.api.router import api_router
from apps.api.app.core.config import get_settings
from apps.api.app.core.errors import install_error_handlers
from apps.api.app.core.logging import configure_logging
from apps.api.app.core.observability import configure_observability
from apps.api.app.core.request_context import bind_request_context, reset_context
from apps.api.app.db.seed import seed_reference_data
from apps.api.app.db.session import SessionLocal, engine
from apps.api.app.modules.analytics.service import materialize_analytics

settings = get_settings()


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    settings.validate_for_startup()
    with SessionLocal() as session:
        if settings.should_seed_sample_data:
            seed_reference_data(session, settings)
        if settings.should_materialize_analytics_on_startup:
            materialize_analytics(session, settings)
    yield


def create_app() -> FastAPI:
    settings.validate_for_startup()
    configure_logging()
    app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=app_lifespan)
    install_error_handlers(app)
    configure_observability(app, settings, engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid4()))
        trace_id = request.headers.get("x-trace-id", request_id)
        tokens = bind_request_context(request_id=request_id, trace_id=trace_id)
        try:
            response = await call_next(request)
        finally:
            reset_context(tokens)
        response.headers["x-request-id"] = request_id
        response.headers["x-trace-id"] = trace_id
        return response

    @app.get("/")
    def root() -> JSONResponse:
        return JSONResponse({"name": settings.app_name, "api": "/api"})

    app.include_router(api_router)
    return app


app = create_app()
