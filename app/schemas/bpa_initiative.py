from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BPAInitiativeBase(BaseModel):
    project_code: str
    title: str
    url: Optional[str] = None


class BPAInitiativeCreate(BPAInitiativeBase):
    pass


class BPAInitiativeUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None


class BPAInitiativeInDBBase(BPAInitiativeBase):
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BPAInitiative(BPAInitiativeInDBBase):
    pass
