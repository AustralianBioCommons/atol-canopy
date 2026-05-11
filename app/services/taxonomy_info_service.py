from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.organism import Organism
from app.models.taxonomy_info import TaxonomyInfo
from app.schemas.bulk_import import BulkImportResponse
from app.schemas.taxonomy_info import TaxonomyInfoCreate, TaxonomyInfoUpdate


class TaxonomyInfoService:
    """Service for TaxonomyInfo CRUD and bulk import operations."""

    def get(self, db: Session, taxon_id: int) -> Optional[TaxonomyInfo]:
        return db.query(TaxonomyInfo).filter(TaxonomyInfo.taxon_id == taxon_id).first()

    def list(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[TaxonomyInfo]:
        return db.query(TaxonomyInfo).offset(skip).limit(limit).all()

    def create(self, db: Session, *, ti_in: TaxonomyInfoCreate) -> TaxonomyInfo:
        organism = db.query(Organism).filter(Organism.taxon_id == ti_in.taxon_id).first()
        if not organism:
            raise ValueError(f"Organism with taxon_id {ti_in.taxon_id} does not exist")

        existing = db.query(TaxonomyInfo).filter(TaxonomyInfo.taxon_id == ti_in.taxon_id).first()
        if existing:
            raise ValueError(f"TaxonomyInfo for taxon_id {ti_in.taxon_id} already exists")

        ti = TaxonomyInfo(**ti_in.model_dump())
        db.add(ti)
        db.commit()
        db.refresh(ti)
        return ti

    def update(
        self, db: Session, *, taxon_id: int, ti_in: TaxonomyInfoUpdate
    ) -> Optional[TaxonomyInfo]:
        ti = db.query(TaxonomyInfo).filter(TaxonomyInfo.taxon_id == taxon_id).first()
        if not ti:
            return None
        for field, value in ti_in.model_dump(exclude_unset=True).items():
            setattr(ti, field, value)
        db.add(ti)
        db.commit()
        db.refresh(ti)
        return ti

    def delete(self, db: Session, *, taxon_id: int) -> Optional[TaxonomyInfo]:
        ti = db.query(TaxonomyInfo).filter(TaxonomyInfo.taxon_id == taxon_id).first()
        if not ti:
            return None
        db.delete(ti)
        db.commit()
        return ti

    def bulk_import(self, db: Session, *, data: Dict[str, Dict[str, Any]]) -> BulkImportResponse:
        created_count = 0
        skipped_count = 0
        errors: List[str] = []

        for key, row in data.items():
            try:
                # Resolve taxon_id from top-level key
                try:
                    taxon_id = int(key)
                except (ValueError, TypeError):
                    errors.append(f"{key}: top-level key is not a valid integer taxon_id")
                    skipped_count += 1
                    continue

                # If inner object also supplies taxon_id it must match the key
                inner_taxon_id = row.get("taxon_id")
                if inner_taxon_id is not None and int(inner_taxon_id) != taxon_id:
                    errors.append(
                        f"{key}: inner taxon_id ({inner_taxon_id}) does not match top-level key"
                    )
                    skipped_count += 1
                    continue

                # Validate organism exists
                organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
                if not organism:
                    errors.append(f"{key}: organism with taxon_id {taxon_id} does not exist")
                    skipped_count += 1
                    continue

                # Reject duplicates
                existing = db.query(TaxonomyInfo).filter(TaxonomyInfo.taxon_id == taxon_id).first()
                if existing:
                    errors.append(f"{key}: taxonomy_info for taxon_id {taxon_id} already exists")
                    skipped_count += 1
                    continue

                ti = TaxonomyInfo(
                    taxon_id=taxon_id,
                    busco_odb10_dataset_name=row.get("busco_odb10_dataset_name"),
                    busco_odb12_dataset_name=row.get("busco_odb12_dataset_name"),
                    find_plastid=row.get("find_plastid"),
                    hic_motif=row.get("hic_motif"),
                    mitochondrial_genetic_code_id=row.get("mitochondrial_genetic_code_id"),
                    mitohifi_reference_species=row.get("mitohifi_reference_species"),
                    oatk_hmm_name=row.get("oatk_hmm_name"),
                    defined_class=row.get("defined_class"),
                    augustus_dataset_name=row.get("augustus_dataset_name"),
                    genetic_code_id=row.get("genetic_code_id"),
                )
                db.add(ti)
                db.commit()
                created_count += 1
            except Exception as e:
                errors.append(f"{key}: {str(e)}")
                db.rollback()
                skipped_count += 1

        return BulkImportResponse(
            created_count=created_count,
            skipped_count=skipped_count,
            message=f"TaxonomyInfo import complete. Created: {created_count}, Skipped: {skipped_count}",
            errors=errors if errors else None,
        )


taxonomy_info_service = TaxonomyInfoService()
