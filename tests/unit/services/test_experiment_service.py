from uuid import uuid4

from app.models.experiment import Experiment, ExperimentSubmission
from app.models.project import Project
from app.models.sample import Sample
from app.schemas.experiment import ExperimentUpdate
from app.services.experiment_service import experiment_service


class _Query:
    def __init__(self, data):
        self.data = list(data)

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def first(self):
        return self.data[0] if self.data else None


class _Session:
    def __init__(self, data_map):
        self.data_map = data_map

    def query(self, model):
        return _Query(self.data_map.get(model, []))

    def add(self, obj):
        self.data_map.setdefault(type(obj), [])
        if obj not in self.data_map[type(obj)]:
            self.data_map[type(obj)].append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def test_update_experiment_recreates_submission_without_removed_fields():
    original_sample_id = uuid4()
    replacement_sample_id = uuid4()
    original_project_id = uuid4()
    replacement_project_id = uuid4()
    experiment_id = uuid4()

    experiment = Experiment(
        id=experiment_id,
        sample_id=original_sample_id,
        project_id=original_project_id,
        bpa_package_id="pkg-1",
        design_description="Existing design",
        library_strategy="AMPLICON",
    )
    accepted_submission = ExperimentSubmission(
        id=uuid4(),
        experiment_id=experiment_id,
        authority="ENA",
        status="accepted",
        accession="ERX000001",
        prepared_payload={"design_description": "Existing design", "library_strategy": "AMPLICON"},
    )
    replacement_sample = Sample(id=replacement_sample_id, taxon_id=172942, kind="specimen")
    replacement_project = Project(
        id=replacement_project_id,
        taxon_id=172942,
        project_type="genomic_data",
        study_type="WGS",
        alias="genomic-data",
        title="Genomic data",
        description="Project",
        status="draft",
        authority="ENA",
    )
    db = _Session(
        {
            Experiment: [experiment],
            ExperimentSubmission: [accepted_submission],
            Sample: [replacement_sample],
            Project: [replacement_project],
        }
    )

    updated = experiment_service.update_experiment(
        db,
        experiment_id=experiment_id,
        experiment_in=ExperimentUpdate(
            sample_id=replacement_sample_id,
            library_strategy="WGS",
        ),
    )

    assert updated is experiment
    assert experiment.sample_id == replacement_sample_id
    assert experiment.project_id == replacement_project_id
    assert accepted_submission.status == "replaced"

    submissions = db.data_map[ExperimentSubmission]
    assert len(submissions) == 2
    draft_submission = submissions[-1]
    assert draft_submission.status == "draft"
    assert draft_submission.accession == "ERX000001"
    assert draft_submission.prepared_payload["design_description"] == "Existing design"
    assert draft_submission.prepared_payload["library_strategy"] == "WGS"


def test_update_experiment_updates_current_submission_payload_in_place():
    experiment_id = uuid4()
    experiment = Experiment(
        id=experiment_id,
        sample_id=uuid4(),
        project_id=uuid4(),
        bpa_package_id="pkg-1",
        design_description="Existing design",
        library_strategy="AMPLICON",
    )
    draft_submission = ExperimentSubmission(
        id=uuid4(),
        experiment_id=experiment_id,
        authority="ENA",
        status="draft",
        prepared_payload={"design_description": "Existing design", "library_strategy": "AMPLICON"},
    )
    db = _Session({Experiment: [experiment], ExperimentSubmission: [draft_submission]})

    updated = experiment_service.update_experiment(
        db,
        experiment_id=experiment_id,
        experiment_in=ExperimentUpdate(library_strategy="WGS"),
    )

    assert updated.library_strategy == "WGS"
    assert draft_submission.status == "draft"
    assert draft_submission.prepared_payload["design_description"] == "Existing design"
    assert draft_submission.prepared_payload["library_strategy"] == "WGS"
