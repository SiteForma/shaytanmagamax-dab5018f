from __future__ import annotations

from dramatiq import get_broker

from apps.worker.worker_app import broker as _broker  # noqa: F401


def main() -> None:
    broker = get_broker()
    print(f"Worker broker configured: {broker.__class__.__name__}")


if __name__ == "__main__":
    main()
