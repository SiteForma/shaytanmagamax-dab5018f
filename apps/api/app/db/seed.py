from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.common.utils import normalize_header
from apps.api.app.core.config import Settings
from apps.api.app.core.security import hash_password
from apps.api.app.db.models import (
    AccessPolicy,
    Category,
    Client,
    ClientAlias,
    DataSource,
    DiyPolicy,
    InboundDelivery,
    MappingRule,
    MappingTemplate,
    Product,
    QualityIssue,
    ReserveRun,
    Role,
    SalesFact,
    Sku,
    SkuAlias,
    StockSnapshot,
    UploadBatch,
    UploadedRowIssue,
    UploadFile,
    User,
    UserRole,
)


def seed_reference_data(db: Session, settings: Settings) -> None:
    Path("data/sample").mkdir(parents=True, exist_ok=True)

    def ensure_role(code: str, name: str) -> Role:
        role = db.scalar(select(Role).where(Role.code == code))
        if role is None:
            role = Role(code=code, name=name)
            db.add(role)
            db.flush()
        return role

    def ensure_policy(role_code: str, resource: str, action: str, effect: str = "allow") -> None:
        exists = db.scalar(
            select(AccessPolicy.id).where(
                AccessPolicy.role_code == role_code,
                AccessPolicy.resource == resource,
                AccessPolicy.action == action,
                AccessPolicy.effect == effect,
            )
        )
        if exists is None:
            db.add(
                AccessPolicy(
                    role_code=role_code,
                    resource=resource,
                    action=action,
                    effect=effect,
                )
            )

    def ensure_user(
        *,
        user_id: str,
        email: str,
        full_name: str,
        role: Role,
    ) -> User:
        user = db.get(User, user_id)
        if user is None:
            user = User(
                id=user_id,
                email=email,
                full_name=full_name,
                password_hash=hash_password(settings.dev_admin_password),
                is_active=True,
            )
            db.add(user)
            db.flush()
        assigned = db.scalar(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
        )
        if assigned is None:
            db.add(UserRole(user=user, role=role))
        return user

    admin_role = ensure_role("admin", "Администратор")
    operator_role = ensure_role("operator", "Оператор")
    analyst_role = ensure_role("analyst", "Аналитик")
    viewer_role = ensure_role("viewer", "Наблюдатель")

    ensure_policy("admin", "*", "*")

    for resource in (
        "dashboard",
        "catalog",
        "clients",
        "stock",
        "inbound",
        "sales",
        "reserve",
        "uploads",
        "mapping",
        "quality",
        "reports",
        "assistant",
    ):
        ensure_policy("viewer", resource, "read")
    ensure_policy("viewer", "assistant", "query")

    for resource in (
        "dashboard",
        "catalog",
        "clients",
        "stock",
        "inbound",
        "sales",
        "quality",
        "reports",
    ):
        ensure_policy("analyst", resource, "read")
    ensure_policy("analyst", "inbound", "sync")
    ensure_policy("analyst", "reserve", "read")
    ensure_policy("analyst", "reserve", "run")
    ensure_policy("analyst", "uploads", "read")
    ensure_policy("analyst", "uploads", "write")
    ensure_policy("analyst", "uploads", "apply")
    ensure_policy("analyst", "mapping", "read")
    ensure_policy("analyst", "mapping", "write")
    ensure_policy("analyst", "assistant", "query")
    ensure_policy("analyst", "assistant", "internal_analytics")
    ensure_policy("analyst", "exports", "generate")
    ensure_policy("analyst", "exports", "download")

    for resource in ("dashboard", "catalog", "clients", "stock", "inbound", "quality", "reports"):
        ensure_policy("operator", resource, "read")
    ensure_policy("operator", "inbound", "sync")
    ensure_policy("operator", "uploads", "read")
    ensure_policy("operator", "uploads", "write")
    ensure_policy("operator", "uploads", "apply")
    ensure_policy("operator", "mapping", "read")
    ensure_policy("operator", "assistant", "internal_analytics")
    ensure_policy("operator", "mapping", "write")
    ensure_policy("operator", "reserve", "read")
    ensure_policy("operator", "reserve", "run")
    ensure_policy("operator", "assistant", "query")
    ensure_policy("operator", "exports", "generate")
    ensure_policy("operator", "exports", "download")
    ensure_policy("operator", "admin", "read")

    admin_user = ensure_user(
        user_id="user_admin",
        email=settings.dev_admin_email,
        full_name="Администратор MAGAMAX",
        role=admin_role,
    )
    ensure_user(
        user_id="user_operator",
        email="operator@magamax.local",
        full_name="Оператор MAGAMAX",
        role=operator_role,
    )
    ensure_user(
        user_id="user_analyst",
        email="analyst@magamax.local",
        full_name="Аналитик MAGAMAX",
        role=analyst_role,
    )
    ensure_user(
        user_id="user_viewer",
        email="viewer@magamax.local",
        full_name="Наблюдатель MAGAMAX",
        role=viewer_role,
    )

    db.flush()
    if db.scalar(select(Sku.id).limit(1)):
        db.commit()
        return

    categories = [
        Category(
            id="cat_handles", code="handles", name="Мебельные ручки", level=0, path="/handles"
        ),
        Category(
            id="cat_slides", code="slides", name="Направляющие для ящиков", level=0, path="/slides"
        ),
        Category(id="cat_hinges", code="hinges", name="Петли", level=0, path="/hinges"),
        Category(
            id="cat_lighting", code="lighting", name="Световая фурнитура", level=0, path="/lighting"
        ),
    ]
    db.add_all(categories)
    category_map = {category.code: category for category in categories}

    sku_specs = [
        ("sku_1", "K-2650-CR", "Ручка-кнопка Trilliant 128 мм", "handles", "KERRON"),
        ("sku_2", "RT-4410-BL", "Ручка-скоба Linear 224 мм", "handles", "LEMAX"),
        ("sku_3", "SL-3300-MT", "Направляющая с доводчиком 450 мм", "slides", "LEMAX Prof"),
        ("sku_4", "HG-1820-NI", "Скрытая петля 110°", "hinges", "HANDY HOME"),
        ("sku_5", "LG-9001-WH", "Крепление для LED-ленты 2 м", "lighting", "Natural House"),
        ("sku_6", "SL-5500-GR", "Усиленная направляющая 500 мм", "slides", "LEMAX Prof"),
    ]
    skus: dict[str, Sku] = {}
    sku_category_ids: dict[str, str] = {}
    for sku_id, article, name, category_code, brand in sku_specs:
        product = Product(id=f"prd_{sku_id}", name=name, brand=brand)
        sku = Sku(
            id=sku_id,
            article=article,
            name=name,
            product=product,
            category=category_map[category_code],
            brand=brand,
            unit="pcs",
            active=True,
        )
        skus[sku_id] = sku
        sku_category_ids[sku_id] = category_map[category_code].id
        db.add(product)
        db.add(sku)
        db.add(SkuAlias(sku=sku, alias=normalize_header(article)))

    clients = [
        Client(id="client_1", code="leroy-merlin", name="Леруа Мерлен", region="Москва"),
        Client(id="client_2", code="leman-pro", name="Леман Про", region="Санкт-Петербург"),
        Client(id="client_3", code="obi-russia", name="OBI Россия", region="Краснодар"),
    ]
    db.add_all(clients)
    client_aliases = {
        "client_1": ["Леруа Мерлен", "Leroy Merlin"],
        "client_2": ["Леман Про", "Leman Pro"],
        "client_3": ["OBI Россия", "OBI Russia"],
    }

    policy_specs = {
        "client_1": {
            "reserve_months": 3,
            "safety_factor": 1.15,
            "priority_level": 1,
            "allowed_fallback_depth": 4,
            "notes": "Приоритетный федеральный клиент с полным резервным покрытием.",
            "category_overrides": {},
            "sku_overrides": {},
        },
        "client_2": {
            "reserve_months": 3,
            "safety_factor": 1.10,
            "priority_level": 2,
            "allowed_fallback_depth": 4,
            "notes": "Клиент второго приоритета, допускаем SKU-override для ключевых направляющих.",
            "category_overrides": {},
            "sku_overrides": {
                "sku_3": {
                    "reserve_months": 3,
                    "safety_factor": 1.15,
                    "priority_level": 2,
                }
            },
        },
        "client_3": {
            "reserve_months": 2,
            "safety_factor": 1.05,
            "priority_level": 3,
            "allowed_fallback_depth": 3,
            "notes": "Локальный клиент с более коротким горизонтом резерва и category-override по свету.",
            "category_overrides": {
                "cat_lighting": {
                    "reserve_months": 2,
                    "safety_factor": 1.08,
                    "priority_level": 3,
                }
            },
            "sku_overrides": {},
        },
    }
    for client in clients:
        policy_spec = policy_specs[client.id]
        db.add(
            DiyPolicy(
                client=client,
                reserve_months=policy_spec["reserve_months"],
                safety_factor=policy_spec["safety_factor"],
                priority_level=policy_spec["priority_level"],
                active=True,
                allowed_fallback_depth=policy_spec["allowed_fallback_depth"],
                fallback_chain=[
                    "client_sku",
                    "client_category",
                    "global_sku",
                    "category_baseline",
                    "insufficient_history",
                ],
                category_overrides=policy_spec["category_overrides"],
                sku_overrides=policy_spec["sku_overrides"],
                notes=policy_spec["notes"],
                effective_from=date.today().replace(day=1) - timedelta(days=180),
            )
        )
        for alias in client_aliases[client.id]:
            db.add(ClientAlias(client=client, alias=alias))

    source_types = [
        ("sales", "Отчёт по продажам"),
        ("stock", "Снимок склада"),
        ("diy_clients", "Мастер DIY-клиентов"),
        ("category_structure", "Структура категорий"),
        ("inbound", "План поставок"),
        ("raw_report", "Неразобранный отчёт"),
    ]
    source_type_labels = {code: name for code, name in source_types}
    for code, name in source_types:
        db.add(DataSource(code=code, name=name, source_type=code))

    mapping_fields = {
        "sales": {
            "article": "sku_code",
            "sku": "sku_code",
            "артикул": "sku_code",
            "client": "client_name",
            "customer": "client_name",
            "сеть": "client_name",
            "qty": "quantity",
            "quantity": "quantity",
            "кол_во": "quantity",
            "month": "period_date",
            "period": "period_date",
            "дата": "period_date",
        },
        "stock": {
            "article": "sku_code",
            "артикул": "sku_code",
            "warehouse": "warehouse_name",
            "склад": "warehouse_name",
            "free_stock": "stock_free",
            "free": "stock_free",
            "свободный_остаток": "stock_free",
        },
        "inbound": {
            "article": "sku_code",
            "eta": "eta_date",
            "qty": "quantity",
            "status": "status",
        },
    }
    for source_type, field_map in mapping_fields.items():
        template = MappingTemplate(
            name=f"{source_type_labels[source_type]} — базовый шаблон",
            source_type=source_type,
            version=1,
            is_default=True,
        )
        db.add(template)
        for source_header, canonical_field in field_map.items():
            db.add(
                MappingRule(
                    template=template,
                    source_header=source_header,
                    canonical_field=canonical_field,
                    confidence=0.98 if source_header == canonical_field else 0.9,
                )
            )

    # PostgreSQL enforces these foreign keys during flush, so parent catalog/client rows
    # must be persisted before dependent facts and inbound records are inserted.
    db.flush()

    today = date.today().replace(day=1)
    sales_matrix = {
        "client_1": {
            "sku_1": [320, 340, 360, 390, 410, 430],
            "sku_2": [190, 205, 210, 230, 225, 245],
            "sku_3": [120, 135, 150, 165, 170, 180],
            "sku_6": [95, 105, 115, 125, 140, 155],
        },
        "client_2": {
            "sku_1": [280, 300, 310, 330, 345, 360],
            "sku_3": [220, 230, 240, 260, 275, 295],
            "sku_4": [70, 75, 88, 92, 96, 104],
            "sku_6": [110, 118, 126, 132, 140, 150],
        },
        "client_3": {
            "sku_2": [130, 138, 144, 155, 162, 170],
            "sku_4": [82, 84, 90, 96, 101, 109],
            "sku_5": [45, 42, 49, 55, 58, 64],
        },
    }
    sku_prices = {
        "sku_1": 1250,
        "sku_2": 840,
        "sku_3": 640,
        "sku_4": 420,
        "sku_5": 310,
        "sku_6": 980,
    }
    for client_id, sku_values in sales_matrix.items():
        for sku_id, quantities in sku_values.items():
            for months_ago, quantity in enumerate(reversed(quantities)):
                period = today - timedelta(days=30 * months_ago)
                db.add(
                    SalesFact(
                        client_id=client_id,
                        sku_id=sku_id,
                        category_id=sku_category_ids[sku_id],
                        period_month=period,
                        quantity=quantity,
                        revenue_amount=quantity * sku_prices[sku_id],
                    )
                )
    historical_2025_sales = [
        ("client_1", "sku_1", date(2025, 3, 1), 260, 1250),
        ("client_1", "sku_2", date(2025, 3, 1), 155, 840),
        ("client_1", "sku_6", date(2025, 3, 1), 88, 980),
        ("client_3", "sku_2", date(2025, 3, 1), 118, 840),
        ("client_3", "sku_4", date(2025, 3, 1), 74, 420),
        ("client_3", "sku_5", date(2025, 3, 1), 39, 310),
        ("client_1", "sku_1", date(2025, 2, 1), 240, 1250),
        ("client_3", "sku_2", date(2025, 2, 1), 104, 840),
        ("client_1", "sku_1", date(2025, 1, 1), 220, 1250),
        ("client_3", "sku_2", date(2025, 1, 1), 98, 840),
    ]
    for client_id, sku_id, period, quantity, price in historical_2025_sales:
        db.add(
            SalesFact(
                client_id=client_id,
                sku_id=sku_id,
                category_id=sku_category_ids[sku_id],
                period_month=period,
                quantity=quantity,
                revenue_amount=quantity * price,
            )
        )

    stock_rows = [
        ("sku_1", "Щёлково", 280, 40),
        ("sku_2", "Щёлково", 120, 22),
        ("sku_3", "Краснодар", 90, 18),
        ("sku_4", "Симферополь", 140, 12),
        ("sku_5", "Щёлково", 430, 15),
        ("sku_6", "Краснодар", 65, 10),
    ]
    for sku_id, warehouse_code, free_stock_qty, reserved_like_qty in stock_rows:
        db.add(
            StockSnapshot(
                sku_id=sku_id,
                warehouse_code=warehouse_code,
                free_stock_qty=free_stock_qty,
                reserved_like_qty=reserved_like_qty,
            )
        )

    inbound_rows = [
        (
            "INB-1001",
            "sku_1",
            620,
            today + timedelta(days=14),
            "confirmed",
            ["client_1", "client_2"],
            420,
        ),
        ("INB-1002", "sku_3", 380, today + timedelta(days=28), "in_transit", ["client_2"], 250),
        (
            "INB-1003",
            "sku_6",
            250,
            today + timedelta(days=41),
            "delayed",
            ["client_1", "client_2"],
            0,
        ),
        (
            "INB-1004",
            "sku_2",
            180,
            today + timedelta(days=22),
            "confirmed",
            ["client_1", "client_3"],
            120,
        ),
    ]
    for (
        external_ref,
        sku_id,
        quantity,
        eta_date,
        status,
        affected,
        reserve_impact_qty,
    ) in inbound_rows:
        db.add(
            InboundDelivery(
                external_ref=external_ref,
                sku_id=sku_id,
                quantity=quantity,
                eta_date=eta_date,
                status=status,
                affected_client_ids=affected,
                reserve_impact_qty=reserve_impact_qty,
            )
        )

    upload_batches = [
        ("batch_sales", "sales", "applied", "sales_2025_11.csv", 18420, 3),
        ("batch_stock", "stock", "normalized", "stock_snapshot_shch.csv", 4302, 0),
        ("batch_clients", "diy_clients", "issues_found", "diy_clients_master.xlsx", 211, 2),
        ("batch_inbound", "inbound", "validating", "inbound_dec.csv", 1180, 0),
    ]
    for batch_id, source_type, status, file_name, total_rows, issue_count in upload_batches:
        batch = UploadBatch(
            id=batch_id,
            source_type=source_type,
            detected_source_type=source_type,
            status=status,
            uploaded_by_id=admin_user.id,
            total_rows=total_rows,
            valid_rows=max(total_rows - issue_count, 0),
            issue_count=issue_count,
        )
        db.add(batch)
        file = UploadFile(
            id=f"file_{batch_id}",
            batch=batch,
            file_name=file_name,
            source_type=source_type,
            content_type="text/csv",
            size_bytes=2048,
            checksum=f"seed-{batch_id}",
            storage_key=f"seed/{file_name}",
        )
        db.add(file)
    db.flush()
    for batch_id, _source_type, _status, _file_name, _total_rows, issue_count in upload_batches:
        batch = db.get(UploadBatch, batch_id)
        file = db.get(UploadFile, f"file_{batch_id}")
        if batch is None or file is None:
            continue
        if issue_count:
            db.add(
                UploadedRowIssue(
                    batch_id=batch.id,
                    file_id=file.id,
                    row_number=12,
                    field_name="client_name",
                    code="unmatched_client",
                    severity="high",
                    message="Алиас клиента не удалось сопоставить",
                    raw_payload={"client_name": "Неизвестная DIY-сеть"},
                )
            )

    db.add_all(
        [
            QualityIssue(
                issue_type="missing_sku",
                severity="high",
                entity_type="sku",
                entity_ref="K-9999-XX",
                description="SKU из загрузки продаж отсутствует в каноническом каталоге",
                source_label="sales_2025_11.csv",
            ),
            QualityIssue(
                issue_type="negative_stock",
                severity="critical",
                entity_type="stock",
                entity_ref="SL-5500-GR",
                description="В исходном снимке обнаружен отрицательный свободный остаток",
                source_label="stock_snapshot_shch.csv",
            ),
            QualityIssue(
                issue_type="suspicious_spike",
                severity="medium",
                entity_type="sales",
                entity_ref="K-2650-CR",
                description="Всплеск месячных продаж превышает 5σ относительно базовой линии",
                source_label="sales_2025_11.csv",
            ),
        ]
    )

    db.add(
        ReserveRun(
            id="run_seed",
            created_by_id=admin_user.id,
            reserve_months=3,
            safety_factor=1.1,
            demand_basis="blended",
            horizon_days=60,
            filters_payload={"client_ids": [client.id for client in clients]},
            row_count=0,
        )
    )

    db.commit()
