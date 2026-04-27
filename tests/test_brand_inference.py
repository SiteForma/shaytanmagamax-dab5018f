from __future__ import annotations

from apps.api.app.modules.catalog.brand import UNKNOWN_BRAND, infer_brand, resolve_brand


def test_brand_inference_detects_known_product_brands() -> None:
    assert infer_brand("Упаковка 1pcs-FHS Пакет ПЭТ, LEMAX PROF") == "Lemax Prof"
    assert infer_brand("Lemax - пакет универсальный") == "Lemax"
    assert infer_brand("Комплект заглушка Kerron для винта") == "Kerron"
    assert infer_brand("Клей homakoll 164 Prof ведро") == "Homakoll"
    assert infer_brand("Встраиваемая посудомоечная машина Zigmund&shtain") == "Zigmund & Shtain"
    assert infer_brand("Декоративная стеклянная ваза") == UNKNOWN_BRAND


def test_brand_resolution_preserves_known_brand_when_new_source_has_no_brand() -> None:
    assert resolve_brand("Kerron", "Декоративная стеклянная ваза") == "Kerron"
    assert resolve_brand("MAGAMAX", "Декоративная стеклянная ваза") == UNKNOWN_BRAND
    assert resolve_brand("Kerron", "LEMAX PROF пакет") == "Lemax Prof"
