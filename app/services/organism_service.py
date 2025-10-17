from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.organism import Organism
from app.schemas.organism import OrganismCreate, OrganismUpdate
from app.services.base_service import BaseService


class OrganismService(BaseService[Organism, OrganismCreate, OrganismUpdate]):
    """Service for Organism operations."""
    
    def get_by_scientific_name(self, db: Session, scientific_name: str) -> Optional[Organism]:
        """Get organism by scientific name."""
        return db.query(Organism).filter(Organism.scientific_name == scientific_name).first()
    
    def get_by_tax_id(self, db: Session, tax_id: str) -> Optional[Organism]:
        """Get organism by taxon ID."""
        return db.query(Organism).filter(Organism.tax_id == tax_id).first()
    
    def get_by_grouping_key(self, db: Session, grouping_key: str) -> Optional[Organism]:
        """Get organism by grouping_key."""
        return db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
    
    def get_multi_with_filters(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        scientific_name: Optional[str] = None,
        tax_id: Optional[str] = None,
        grouping_key: Optional[str] = None
    ) -> List[Organism]:
        """Get organisms with filters."""
        query = db.query(Organism)
        if scientific_name:
            query = query.filter(Organism.scientific_name.ilike(f"%{scientific_name}%"))
        if tax_id:
            query = query.filter(Organism.tax_id == tax_id)
        if grouping_key:
            query = query.filter(Organism.grouping_key == grouping_key)
        return query.offset(skip).limit(limit).all()


organism_service = OrganismService(Organism)
