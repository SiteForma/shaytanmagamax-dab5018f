from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.db.models import InboundDelivery, Sku
from apps.api.app.modules.inbound.service import (
    GOOGLE_SHEET_SOURCE_PREFIX,
    parse_inbound_sheet_csv,
    sync_inbound_google_sheet,
)

SHEET_CSV = """,,,,,,,,,,,,,,
Статус,Ожидаемая дата поступления,Дата предоплаты ДО:,Номер контейнера,Артикул (НЕ ТРОГАТЬ НАЗВАНИЕ!!!),В пути,Свободный остаток,БОЦ,Цена по предоплате,Сети,ОБИ,Леруа,Итого заказы клиентов
Оприходован,23.12.2025,,Z25-054,LE 530 BL,2 004,0,,,1 904,100,,2 004
В пути,24.12.2025,,Z25-055,MX-060,108,58,,,8,,42,50
"""


def test_parse_inbound_sheet_csv_preserves_container_qty_and_free_stock() -> None:
    rows, warnings = parse_inbound_sheet_csv(SHEET_CSV)

    assert warnings == []
    assert len(rows) == 2
    assert rows[0].article == "LE 530 BL"
    assert rows[0].container_ref == "Z25-054"
    assert rows[0].in_transit_qty == 2004
    assert rows[0].free_stock_after_allocation_qty == 0
    assert rows[0].client_order_qty == 2004
    assert rows[0].client_allocations == {"Сети": 1904, "ОБИ": 100}


def test_sync_inbound_google_sheet_replaces_authoritative_sheet_rows(
    db_session: Session,
    test_settings,
) -> None:
    result = sync_inbound_google_sheet(
        db_session,
        test_settings,
        actor_user_id="user_admin",
        csv_text=SHEET_CSV,
        source_url="inline://fixture",
    )

    assert result.rows_imported == 2
    assert result.total_in_transit_qty == 2112
    assert result.total_free_stock_after_allocation_qty == 58
    assert result.total_client_order_qty == 2054

    deliveries = db_session.scalars(
        select(InboundDelivery).where(
            InboundDelivery.external_ref.like(f"{GOOGLE_SHEET_SOURCE_PREFIX}:%")
        )
    ).all()
    assert len(deliveries) == 2
    first = next(row for row in deliveries if row.container_ref == "Z25-054")
    assert first.quantity == 2004
    assert first.free_stock_after_allocation_qty == 0
    assert first.client_order_qty == 2004
    assert first.client_allocations["ОБИ"] == 100
    assert first.sheet_status == "Оприходован"
    assert db_session.scalar(select(Sku).where(Sku.article == "LE 530 BL")) is not None

    result_again = sync_inbound_google_sheet(
        db_session,
        test_settings,
        actor_user_id="user_admin",
        csv_text=SHEET_CSV,
        source_url="inline://fixture",
    )
    assert result_again.rows_imported == 2
    assert result_again.deliveries_replaced == 2
    assert (
        db_session.query(InboundDelivery)
        .filter(InboundDelivery.external_ref.like(f"{GOOGLE_SHEET_SOURCE_PREFIX}:%"))
        .count()
        == 2
    )


def test_inbound_sync_endpoint_requires_sync_capability(client: TestClient) -> None:
    response = client.post("/api/inbound/sync", headers={"X-Dev-User": "user_viewer"})

    assert response.status_code == 403
    assert response.json()["details"] == {"resource": "inbound", "action": "sync"}


def test_inbound_sync_endpoint_downloads_configured_sheet(client: TestClient, monkeypatch) -> None:
    class FakeResponse:
        text = SHEET_CSV

        def raise_for_status(self) -> None:
            return None

    def fake_get(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeResponse()

    monkeypatch.setattr("apps.api.app.modules.inbound.service.httpx.get", fake_get)
    response = client.post("/api/inbound/sync", headers={"X-Dev-User": "user_operator"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows_imported"] == 2
    assert payload["total_in_transit_qty"] == 2112
