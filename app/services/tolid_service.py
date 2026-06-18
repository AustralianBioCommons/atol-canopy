from datetime import datetime
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from fastapi.encoders import jsonable_encoder
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
        sample = next((row for row in db.query(Sample).all() if row.id == sample_id), None)
        if not sample:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="sample_not_found",
                message=f"Sample {sample_id} not found",
            )
        return sample

    def _get_scientific_name(self, db: Session, taxon_id: int) -> Optional[str]:
        organism = next((row for row in db.query(Organism).all() if row.taxon_id == taxon_id), None)
        return organism.scientific_name if organism else None

    def _find_row(self, db: Session, sample_id: UUID) -> Optional[TolidRequest]:
        return next((row for row in db.query(TolidRequest).all() if row.sample_id == sample_id), None)

    def _fallback_external_id(self, db: Session, sample: Sample) -> Optional[str]:
        submissions = db.query(SampleSubmission).all()
        for submission in submissions:
            if submission.sample_id == sample.id and submission.accession:
                return submission.accession
        return sample.biosample_accession

    def _find_sample_by_accession(self, db: Session, specimen_id: str) -> Optional[Sample]:
        for submission in db.query(SampleSubmission).all():
            if submission.accession != specimen_id or submission.sample_id is None:
                continue
            sample = next(
                (row for row in db.query(Sample).all() if row.id == submission.sample_id),
                None,
            )
            if sample is not None:
                return sample

        return next(
            (row for row in db.query(Sample).all() if row.biosample_accession == specimen_id),
            None,
        )

    def _sample_payload(self, sample: Sample) -> Dict:
        return jsonable_encoder(
            {column.name: getattr(sample, column.name) for column in sample.__table__.columns}
        )

    def _resolved_scientific_name(
        self, *, db: Session, sample: Sample, row: Optional[TolidRequest]
    ) -> Optional[str]:
        if row is not None and row.scientific_name:
            return row.scientific_name
        organism = getattr(sample, "organism", None)
        if organism is not None and organism.scientific_name:
            return organism.scientific_name
        return self._get_scientific_name(db, sample.taxon_id)

    def _to_broker_view(
        self,
        *,
        db: Session,
        sample: Sample,
        specimen_id: str,
        row: Optional[TolidRequest],
    ) -> TolidRequestBrokerView:
        return TolidRequestBrokerView(
            sample_id=sample.id,
            specimen_id=specimen_id,
            taxon_id=sample.taxon_id,
            scientific_name=self._resolved_scientific_name(db=db, sample=sample, row=row),
            status=(
                self._status_value(row) if row is not None else TolidRequestStatus.NOT_REQUESTED.value
            ),
            request_id=(row.request_id if row is not None else None),
            tolid=(row.tolid if row is not None else None),
            last_requested_at=(row.last_requested_at if row is not None else None),
            error_message=(row.error_message if row is not None else None),
            kind=sample.kind.value if hasattr(sample.kind, "value") else sample.kind,
            sample_payload=self._sample_payload(sample),
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

        return [
            self._to_broker_view(
                db=db,
                sample=row.sample,
                specimen_id=row.tolid_external_id,
                row=row,
            )
            for row in filtered[skip : skip + limit]
        ]

    def get_row_for_sample(self, db: Session, sample_id: UUID) -> TolidRequestBrokerView:
        sample = self._get_sample(db, sample_id)
        if not self._is_specimen(sample):
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="tolid_request_not_found",
                message=f"ToLID request for sample {sample_id} not found",
            )

        row = self._find_row(db, sample_id)
        specimen_id = row.tolid_external_id if row is not None else self._fallback_external_id(db, sample)
        if not specimen_id:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="tolid_request_not_found",
                message=f"ToLID request for sample {sample_id} not found",
            )
        return self._to_broker_view(db=db, sample=sample, specimen_id=specimen_id, row=row)

    def get_by_specimen_accession(self, db: Session, specimen_id: str) -> TolidRequestBrokerView:
        sample = self._find_sample_by_accession(db, specimen_id)
        if sample is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="sample_accession_not_found",
                message=f"No sample found for specimen accession {specimen_id}",
            )
        if not self._is_specimen(sample):
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="tolid_not_specimen",
                message="ToLID requests are only supported for specimen samples",
            )

        row = self._find_row(db, sample.id)
        return self._to_broker_view(db=db, sample=sample, specimen_id=specimen_id, row=row)

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
            row = TolidRequest(
                sample_id=sample.id,
                tolid_external_id=tolid_external_id,
                taxon_id=sample.taxon_id,
                scientific_name=self._get_scientific_name(db, sample.taxon_id),
            )

        row.sample = sample
        row.tolid_external_id = self._fallback_external_id(db, sample) or row.tolid_external_id
        row.taxon_id = sample.taxon_id
        row.scientific_name = row.scientific_name or self._get_scientific_name(db, sample.taxon_id)
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
        specimen_id = row.tolid_external_id or self._fallback_external_id(db, sample)
        return self._to_broker_view(db=db, sample=sample, specimen_id=specimen_id, row=row)


tolid_request_service = TolidRequestService()
