from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.policy import policy
from app.models.user import User
from app.services.broker_service import expire_leases

router = APIRouter()


@router.post("/leases/expire")
@policy("admin:expire_leases")
def expire_all_leases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Dict[str, int]]:
    """
    Expire all broker leases whose locks have passed. Admin-only.
    """
    expired = expire_leases(db)
    db.commit()
    return {"expired_counts": expired}
