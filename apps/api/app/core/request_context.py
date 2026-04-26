from __future__ import annotations

from contextvars import ContextVar
from typing import NamedTuple

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_context: ContextVar[str | None] = ContextVar("trace_id", default=None)
job_id_context: ContextVar[str | None] = ContextVar("job_id", default=None)


class ContextTokens(NamedTuple):
    request_token: object | None
    trace_token: object | None
    job_token: object | None


def get_request_id() -> str | None:
    return request_id_context.get()


def get_trace_id() -> str | None:
    return trace_id_context.get()


def get_job_id() -> str | None:
    return job_id_context.get()


def bind_request_context(*, request_id: str, trace_id: str | None = None) -> ContextTokens:
    return ContextTokens(
        request_token=request_id_context.set(request_id),
        trace_token=trace_id_context.set(trace_id or request_id),
        job_token=None,
    )


def bind_job_context(*, job_id: str, trace_id: str | None = None) -> ContextTokens:
    effective_trace_id = trace_id or job_id
    return ContextTokens(
        request_token=request_id_context.set(effective_trace_id),
        trace_token=trace_id_context.set(effective_trace_id),
        job_token=job_id_context.set(job_id),
    )


def reset_context(tokens: ContextTokens) -> None:
    if tokens.job_token is not None:
        job_id_context.reset(tokens.job_token)
    if tokens.trace_token is not None:
        trace_id_context.reset(tokens.trace_token)
    if tokens.request_token is not None:
        request_id_context.reset(tokens.request_token)
