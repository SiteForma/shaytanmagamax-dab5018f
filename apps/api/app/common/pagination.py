from __future__ import annotations

from apps.api.app.common.schemas import PaginatedResponse, PaginationMeta


def paginate[T](items: list[T], page: int = 1, page_size: int = 25) -> PaginatedResponse[T]:
    return paginated_response(items, total=len(items), page=page, page_size=page_size)


def page_offset(page: int, page_size: int) -> int:
    return max(page - 1, 0) * page_size


def paginated_response[T](
    items: list[T],
    *,
    total: int,
    page: int = 1,
    page_size: int = 25,
) -> PaginatedResponse[T]:
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return PaginatedResponse[T](
        items=items[start:end] if total == len(items) else items,
        meta=PaginationMeta(page=page, pageSize=page_size, total=total),
    )
