from datetime import datetime
from typing import Iterable, List, Optional
from uuid import UUID

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.organism import Organism
from app.models.sample import Sample, SampleSubmission
from app.models.tolid_request import TolidRequest
from app.schemas.common import SampleKind
from app.schemas.tolid import TolidRequestBrokerView, TolidRequestReport, TolidRequestStatus


class TolidRequestService:
    """Service helpers for durable ToLID request state."""

    @staticmethod
    def _is_specimen(sample: Optional[Sample]) -> bool:
        if sample is None:
            return False
        return sample.kind == SampleKind.SPECIMEN or sample.kind == SampleKind.SPECIMEN.value

    @staticmethod
    def _status_value(row: TolidRequest) -> str:
        return row.status.value if hasattr(row.status, "value") else row.status

    def _get_sample(self, db: Session, sample_id: UUID) -> Sample:
        sample = db.query(Sample).filter(Sample.id == sample_id).first()
        if not sample:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="sample_not_found",
                message=f"Sample {sample_id} not found",
            )
        return sample

    def _get_scientific_name(self, db: Session, taxon_id: int) -> Optional[str]:
        organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
        return organism.scientific_name if organism else None

    def _find_row(self, db: Session, sample_id: UUID) -> Optional[TolidRequest]:
        return db.query(TolidRequest).filter(TolidRequest.sample_id == sample_id).first()

    def _fallback_external_id(self, db: Session, sample: Sample) -> Optional[str]:
        submissions = db.query(SampleSubmission).filter(SampleSubmission.sample_id == sample.id).all()
        for submission in submissions:
            if submission.accession:
                return submission.accession
        return sample.biosample_accession

    def _to_broker_view(self, row: TolidRequest) -> TolidRequestBrokerView:
        specimen_id = row.sample.specimen_id if getattr(row, "sample", None) else None
        return TolidRequestBrokerView(
            sample_id=row.sample_id,
            specimen_id=specimen_id,
            tolid_external_id=row.tolid_external_id,
            taxon_id=row.taxon_id,
            scientific_name=row.scientific_name,
            status=row.status,
            request_id=row.request_id,
            tolid=row.tolid,
            last_requested_at=row.last_requested_at,
            error_message=row.error_message,
        )

    def list_rows(
        self,
        db: Session,
        *,
        row_status: TolidRequestStatus,
        taxon_id: Optional[int] = None,
        sample_id: Optional[UUID] = None,
        sample_ids: Optional[Iterable[UUID]] = None,
        requested_before: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TolidRequestBrokerView]:
        rows = db.query(TolidRequest).all()
        sample_ids_set = set(sample_ids) if sample_ids else None
        filtered = []
        for row in rows:
            sample = getattr(row, "sample", None)
            if not self._is_specimen(sample):
                continue
            if self._status_value(row) != row_status.value:
                continue
            if taxon_id is not None and row.taxon_id != taxon_id:
                continue
            if sample_id is not None and row.sample_id != sample_id:
                continue
            if sample_ids_set is not None and row.sample_id not in sample_ids_set:
                continue
            if requested_before is not None:
                if row.last_requested_at is None or row.last_requested_at >= requested_before:
                    continue
            filtered.append(row)

        return [self._to_broker_view(row) for row in filtered[skip : skip + limit]]

    def get_row_for_sample(self, db: Session, sample_id: UUID) -> TolidRequestBrokerView:
        row = self._find_row(db, sample_id)
        if not row:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="tolid_request_not_found",
                message=f"ToLID request for sample {sample_id} not found",
            )
        if not self._is_specimen(getattr(row, "sample", None)):
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="tolid_request_not_found",
                message=f"ToLID request for sample {sample_id} not found",
            )
        return self._to_broker_view(row)

    def ensure_row_for_sample(
        self,
        db: Session,
        *,
        sample_id: UUID,
        tolid_external_id: str,
        scientific_name: Optional[str] = None,
    ) -> Optional[TolidRequest]:
        sample = self._get_sample(db, sample_id)
        if not self._is_specimen(sample):
            return None

        row = self._find_row(db, sample_id)
        if scientific_name is None:
            scientific_name = self._get_scientific_name(db, sample.taxon_id)

        if row:
            row.tolid_external_id = tolid_external_id
            row.taxon_id = sample.taxon_id
            row.scientific_name = scientific_name
            row.sample = sample
            db.add(row)
            return row

        row = TolidRequest(
            sample_id=sample.id,
            tolid_external_id=tolid_external_id,
            taxon_id=sample.taxon_id,
            scientific_name=scientific_name,
            status=TolidRequestStatus.NOT_REQUESTED.value,
        )
        row.sample = sample
        db.add(row)
        return row

    def report_result(
        self,
        db: Session,
        *,
        sample_id: UUID,
        report: TolidRequestReport,
    ) -> TolidRequestBrokerView:
        sample = self._get_sample(db, sample_id)
        if not self._is_specimen(sample):
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="tolid_not_specimen",
                message="ToLID requests are only supported for specimen samples",
            )

        row = self._find_row(db, sample_id)
        if row is None:
            tolid_external_id = self._fallback_external_id(db, sample)
            if not tolid_external_id:
                raise AppError(
                    status_code=status.HTTP_409_CONFLICT,
                    code="tolid_external_id_missing",
                    message="Cannot create ToLID request row before an ENA sample accession is known",
                )
            row = self.ensure_row_for_sample(
                db,
                sample_id=sample_id,
                tolid_external_id=tolid_external_id,
            )
            if row is None:
                raise AppError(
                    status_code=status.HTTP_409_CONFLICT,
                    code="tolid_not_specimen",
                    message="ToLID requests are only supported for specimen samples",
                )

        row.sample = sample
        row.status = report.status.value
        row.last_requested_at = report.last_requested_at

        if report.status == TolidRequestStatus.ASSIGNED:
            row.tolid = report.tolid
            row.request_id = report.request_id
            row.error_message = None
            sample.tolid = report.tolid
            db.add(sample)
        elif report.status == TolidRequestStatus.PENDING:
            row.request_id = report.request_id
            row.error_message = None
        elif report.status == TolidRequestStatus.FAILED:
            row.request_id = report.request_id
            row.error_message = report.error_message

        db.add(row)
        return self._to_broker_view(row)


tolid_request_service = TolidRequestService()
