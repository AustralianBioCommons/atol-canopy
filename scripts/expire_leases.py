#!/usr/bin/env python3
from __future__ import annotations

from app.db.session import SessionLocal
from app.services.broker_service import expire_leases


def main() -> None:
    db = SessionLocal()
    try:
        expired = expire_leases(db)
        db.commit()
    finally:
        db.close()

    for key, count in expired.items():
        print(f"{key}: {count}")


if __name__ == "__main__":
    main()
