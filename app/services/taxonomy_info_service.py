import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.organism import Organism
from app.models.taxonomy_info import TaxonomyInfo
from app.schemas.bulk_import import BulkImportResponse
from app.schemas.taxonomy_info import TaxonomyInfoCreate, TaxonomyInfoUpdate
from app.services.ncbi_taxonomy_service import fetch_taxonomy_for_taxon_ids
from app.services.organism_service import sync_organism_scientific_name

logger = logging.getLogger(__name__)


class TaxonomyInfoService:
    """Service for TaxonomyInfo CRUD and bulk import operations."""

    @staticmethod
    def _apply_payload_values(ti: TaxonomyInfo, values: Dict[str, Any]) -> None:
        for field, value in values.items():
            if field == "taxon_id":
                continue
            setattr(ti, field, value)

    @staticmethod
    def _apply_ncbi_values(ti: TaxonomyInfo, mapped: Dict[str, Any]) -> List[str]:
        mapped_columns = {column.name for column in TaxonomyInfo.__table__.columns}
        applied_fields: list[str] = []
        for field, value in mapped.items():
            if field not in mapped_columns or field == "taxon_id":
                continue
            setattr(ti, field, value)
            applied_fields.append(field)
        return applied_fields

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

        ti = self.populate_from_ncbi_lookup(
            db,
            taxon_id=ti_in.taxon_id,
            scientific_name=getattr(organism, "bpa_scientific_name", None),
            organism=organism,
            commit=False,
        )
        if ti is None:
            ti = TaxonomyInfo(taxon_id=ti_in.taxon_id)
            db.add(ti)

        self._apply_payload_values(ti, ti_in.model_dump(exclude_unset=True))
        sync_organism_scientific_name(
            organism,
            ncbi_scientific_name=getattr(ti, "ncbi_scientific_name", None),
        )
        db.commit()
        db.refresh(ti)
        return ti

    def populate_from_ncbi_lookup(
        self,
        db: Session,
        *,
        taxon_id: int,
        scientific_name: Optional[str] = None,
        organism: Optional[Organism] = None,
        commit: bool = False,
    ) -> Optional[TaxonomyInfo]:
        if organism is None:
            organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
        if not organism:
            raise ValueError(f"Organism with taxon_id {taxon_id} does not exist")

        logger.info("Starting NCBI taxonomy enrichment for organism taxon_id=%s", taxon_id)
        mapped_dict, unmapped = fetch_taxonomy_for_taxon_ids({taxon_id: scientific_name})
        mapped = mapped_dict.get(taxon_id)
        if not mapped:
            logger.warning(
                "NCBI enrichment returned no mapped taxonomy for taxon_id=%s; unmapped=%s",
                taxon_id,
                unmapped,
            )
            return None

        ti = db.query(TaxonomyInfo).filter(TaxonomyInfo.taxon_id == taxon_id).first()
        created = False
        if not ti:
            ti = TaxonomyInfo(taxon_id=taxon_id)
            db.add(ti)
            created = True

        applied_fields = self._apply_ncbi_values(ti, mapped)
        ti.ncbi_last_synced_at = datetime.now(timezone.utc)
        sync_organism_scientific_name(
            organism,
            ncbi_scientific_name=ti.ncbi_scientific_name,
        )
        db.flush()
        logger.info(
            "NCBI taxonomy enrichment %s taxonomy_info for taxon_id=%s; applied_fields=%s",
            "created" if created else "updated",
            taxon_id,
            applied_fields,
        )

        if commit:
            db.commit()
            db.refresh(ti)

        return ti

    def update(
        self, db: Session, *, taxon_id: int, ti_in: TaxonomyInfoUpdate
    ) -> Optional[TaxonomyInfo]:
        ti = db.query(TaxonomyInfo).filter(TaxonomyInfo.taxon_id == taxon_id).first()
        if not ti:
            return None
        organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
        for field, value in ti_in.model_dump(exclude_unset=True).items():
            setattr(ti, field, value)
        if organism:
            sync_organism_scientific_name(
                organism,
                ncbi_scientific_name=ti.ncbi_scientific_name,
            )
            db.add(organism)
        db.add(ti)
        db.commit()
        db.refresh(ti)
        return ti

    def delete(self, db: Session, *, taxon_id: int) -> Optional[TaxonomyInfo]:
        ti = db.query(TaxonomyInfo).filter(TaxonomyInfo.taxon_id == taxon_id).first()
        if not ti:
            return None
        organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
        if organism:
            sync_organism_scientific_name(organism, ncbi_scientific_name=None)
            db.add(organism)
        db.delete(ti)
        db.commit()
        return ti

    """def upsert_info_from_ncbi(self, db: Session, *, taxon_id: int) -> Optional[TaxonomyInfo]:
        organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
        if not organism:
            raise ValueError(f"Organism with taxon_id {taxon_id} does not exist")

        if """

    def bulk_import(
        self, db: Session, *, data: Dict[int, TaxonomyInfoUpdate]
    ) -> BulkImportResponse:
        created_count = 0
        skipped_count = 0
        errors: List[str] = []
        candidates: List[tuple[int, TaxonomyInfoUpdate, Organism]] = []

        for taxon_id, row in data.items():
            try:
                organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
                if not organism:
                    errors.append(f"{taxon_id}: organism with taxon_id {taxon_id} does not exist")
                    skipped_count += 1
                    continue
                existing = db.query(TaxonomyInfo).filter(TaxonomyInfo.taxon_id == taxon_id).first()
                if existing:
                    errors.append(
                        f"{taxon_id}: taxonomy_info for taxon_id {taxon_id} already exists"
                    )
                    skipped_count += 1
                    continue

            except Exception as e:
                errors.append(f"{taxon_id}: {str(e)}")
                db.rollback()
                skipped_count += 1
                continue

            candidates.append((taxon_id, row, organism))

        scientific_names_by_taxon_id = {
            taxon_id: getattr(organism, "bpa_scientific_name", None)
            for taxon_id, _, organism in candidates
        }
        ncbi_by_taxon_id, unmapped = fetch_taxonomy_for_taxon_ids(scientific_names_by_taxon_id)
        if unmapped:
            logger.warning("NCBI bulk enrichment returned unmapped taxon_ids: %s", unmapped)

        for taxon_id, row, organism in candidates:
            try:
                ti = TaxonomyInfo(taxon_id=taxon_id)
                db.add(ti)

                mapped = ncbi_by_taxon_id.get(taxon_id)
                if mapped:
                    applied_fields = self._apply_ncbi_values(ti, mapped)
                    ti.ncbi_last_synced_at = datetime.now(timezone.utc)
                    logger.info(
                        "NCBI taxonomy enrichment %s taxonomy_info for taxon_id=%s; applied_fields=%s",
                        "created",
                        taxon_id,
                        applied_fields,
                    )
                else:
                    logger.warning(
                        "NCBI enrichment returned no mapped taxonomy during bulk import for taxon_id=%s",
                        taxon_id,
                    )

                self._apply_payload_values(ti, row.model_dump(exclude_unset=True))
                sync_organism_scientific_name(
                    organism,
                    ncbi_scientific_name=ti.ncbi_scientific_name,
                )
                db.add(organism)
                db.commit()
                created_count += 1
            except Exception as e:
                errors.append(f"{taxon_id}: {str(e)}")
                db.rollback()
                skipped_count += 1

        return BulkImportResponse(
            created_count=created_count,
            skipped_count=skipped_count,
            message=f"TaxonomyInfo import complete. Created: {created_count}, Skipped: {skipped_count}",
            errors=errors if errors else None,
        )


taxonomy_info_service = TaxonomyInfoService()
