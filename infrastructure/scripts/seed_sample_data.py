from __future__ import annotations

from apps.api.app.core.config import get_settings
from apps.api.app.db.base import Base
from apps.api.app.db.seed import seed_reference_data
from apps.api.app.db.session import SessionLocal, engine
from apps.api.app.modules.analytics.service import materialize_analytics


def main() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_reference_data(session, settings)
        materialize_analytics(session, settings)
    print("Sample data seeded.")


if __name__ == "__main__":
    main()
